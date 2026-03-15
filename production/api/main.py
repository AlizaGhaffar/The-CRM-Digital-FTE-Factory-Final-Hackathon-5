"""
production/api/main.py
Exercise 2.6 — FastAPI Service with Channel Endpoints

All entry points for the NimbusFlow Customer Success FTE:
    POST /webhooks/gmail              — Google Pub/Sub push for inbound email
    POST /webhooks/whatsapp           — Twilio webhook for WhatsApp messages
    POST /webhooks/whatsapp/status    — Twilio delivery status callback
    POST /support/submit              — Web form submission (via web_form_router)
    GET  /support/ticket/{ticket_id}  — Ticket status  (via web_form_router)
    GET  /conversations/{id}          — Conversation history
    GET  /customers/lookup            — Customer lookup by email or phone
    GET  /metrics/channels            — Channel-specific 24 h performance summary
    GET  /api/metrics                 — Admin dashboard: system metrics summary
    GET  /api/tickets                 — Admin dashboard: recent tickets list
    GET  /api/activity                — Admin dashboard: recent activity feed
    GET  /health                      — Liveness probe with channel status
    GET  /ready                       — Readiness probe (DB + Kafka)
    POST /api/send-whatsapp           — Landing page: send WhatsApp via Twilio (no Kafka)
    POST /api/send-email              — Landing page: send email ack via Gmail (no Kafka)

Run locally:
    uvicorn production.api.main:app --reload --port 8000
"""

import json
import logging
import os
import random
import string
from contextlib import asynccontextmanager
from typing import Optional

from dotenv import load_dotenv

load_dotenv()  # Must be before handler imports so module-level os.getenv() picks up .env

from aiokafka import AIOKafkaProducer
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Request,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from production.channels.gmail_handler import (
    GmailHandler,
    parse_pubsub_push,
    fetch_new_messages,
    poll_inbox as gmail_poll_module,
)
from production.channels.whatsapp_handler import (
    WhatsAppHandler,
    parse_twilio_webhook,
    validate_twilio_signature,
)
from production.channels.web_form_handler import router as web_form_router
from production.database import queries

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPIC_EMAIL = "nimbusflow.messages.email"
TOPIC_WHATSAPP = "nimbusflow.messages.whatsapp"
TOPIC_WEB_FORM = "nimbusflow.messages.web_form"

# CORS origins — include localhost ports for web form development
_DEFAULT_CORS = "http://localhost:3000,http://localhost:8080,http://localhost:5173"
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", _DEFAULT_CORS).split(",")
    if o.strip()
]


# ── Lifespan: startup / shutdown ──────────────────────────────────────────────

_producer: Optional[AIOKafkaProducer] = None


async def get_producer() -> AIOKafkaProducer:
    global _producer
    if _producer is None:
        raise HTTPException(
            status_code=503,
            detail="Kafka unavailable — this endpoint requires a running Kafka broker.",
        )
    return _producer


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _producer
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    logger.info("Starting NimbusFlow Customer Success FTE API")

    try:
        _producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP,
            compression_type="gzip",
            acks="all",
            enable_idempotence=True,
        )
        await _producer.start()
        logger.info("Kafka producer ready, bootstrap=%s", KAFKA_BOOTSTRAP)
    except Exception as exc:
        logger.warning(
            "Kafka unavailable (%s) — starting without Kafka. "
            "Webhook endpoints will return 503 until Kafka is reachable.",
            exc,
        )
        _producer = None

    yield

    if _producer is not None:
        await _producer.stop()
    await queries.close_pool()
    logger.info("API shutdown complete")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="NimbusFlow Customer Success FTE",
    description=(
        "24/7 AI-powered customer support across Email, WhatsApp, and Web Form.\n\n"
        "**Exercise 2.6** — Production FastAPI service with channel endpoints."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

# CORS: allow web form origin to POST /support/submit and poll /support/ticket/*
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Mount web form endpoints: POST /support/submit + GET /support/ticket/{ticket_id}
app.include_router(web_form_router)


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _publish(topic: str, payload: dict, producer: AIOKafkaProducer) -> None:
    """Serialize payload as JSON and publish to Kafka with customer key."""
    key = (payload.get("from_email") or payload.get("customer_email")
           or payload.get("from_phone") or payload.get("customer_phone") or "").encode()
    await producer.send_and_wait(topic, json.dumps(payload).encode(), key=key)
    logger.info("Published to %s | keys=%s", topic, list(payload.keys()))


# ── 1. POST /webhooks/gmail ───────────────────────────────────────────────────

@app.post("/webhooks/gmail", tags=["channels"])
async def gmail_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    producer: AIOKafkaProducer = Depends(get_producer),
):
    """
    Receive a Google Cloud Pub/Sub push notification for new Gmail messages.

    Google sends a POST to this endpoint whenever new mail arrives in the
    watched inbox. The push body contains a base64-encoded historyId.

    Flow:
      1. Parse the Pub/Sub push to extract historyId.
      2. In background: fetch full messages from Gmail API (avoids Pub/Sub timeout).
      3. Publish each email payload to nimbusflow.messages.email.

    Returns 200 immediately — Pub/Sub re-delivers if it does not receive 200.
    """
    body = await request.json()
    parsed = parse_pubsub_push(body)

    if not parsed:
        # ACK to prevent Pub/Sub retry storm on malformed push
        return {"status": "ignored"}

    history_id = parsed["history_id"]

    async def _fetch_and_publish():
        try:
            messages = await fetch_new_messages(history_id=history_id)
            for msg in messages:
                try:
                    await _publish(TOPIC_EMAIL, msg, producer)
                except Exception as exc:
                    logger.error("gmail_webhook: publish failed: %s", exc)
        except Exception as exc:
            logger.error("gmail_webhook: fetch_new_messages failed: %s", exc, exc_info=True)

    background_tasks.add_task(_fetch_and_publish)
    return {"status": "accepted", "history_id": history_id}


# ── 1b. GET /webhooks/gmail/poll ─────────────────────────────────────────────

@app.get("/webhooks/gmail/poll", tags=["channels"])
async def gmail_poll(
    background_tasks: BackgroundTasks,
    producer: AIOKafkaProducer = Depends(get_producer),
    max_results: int = 5,
):
    """
    Manually poll Gmail INBOX for unread messages and push them to Kafka.
    Use this for demo/testing when Google Cloud Pub/Sub is not configured.

    Flow:
      1. Fetch up to max_results unread messages from INBOX.
      2. Publish each to nimbusflow.messages.email for the worker.
      3. Returns list of fetched message subjects.
    """
    try:
        messages = await gmail_poll_module(max_results=max_results)
    except Exception as exc:
        logger.error("gmail_poll: failed: %s", exc)
        raise HTTPException(status_code=503, detail=f"Gmail API error: {exc}")

    if not messages:
        return {"status": "no_new_messages", "fetched": 0}

    subjects = []
    for msg in messages:
        subjects.append(msg.get("subject", "(no subject)"))
        try:
            await _publish(TOPIC_EMAIL, msg, producer)
        except Exception as exc:
            logger.error("gmail_poll: publish failed: %s", exc)

    return {"status": "published", "fetched": len(subjects), "subjects": subjects}


# ── 2. POST /webhooks/whatsapp ────────────────────────────────────────────────

@app.post("/webhooks/whatsapp", tags=["channels"])
async def whatsapp_webhook(
    request: Request,
    producer: AIOKafkaProducer = Depends(get_producer),
    x_twilio_signature: Optional[str] = Header(None),
):
    """
    Receive a Twilio WhatsApp webhook for an inbound customer message.

    Validates the X-Twilio-Signature header, normalises the Twilio form
    fields, then publishes to nimbusflow.messages.whatsapp for the worker.

    Returns 200 immediately — Twilio requires a response within 15 seconds.
    Compliance keywords (STOP/START/HELP) are passed through in the payload;
    the worker skips agent processing for opt-out events.
    """
    form_data = dict(await request.form())

    if os.getenv("TWILIO_VALIDATE_SIGNATURE", "true").lower() == "true":
        url = str(request.url)
        sig = x_twilio_signature or ""
        if not validate_twilio_signature(url, form_data, sig):
            logger.warning("whatsapp_webhook: invalid Twilio signature")
            raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    payload = parse_twilio_webhook(form_data)
    if not payload:
        return {"status": "ignored"}

    try:
        await _publish(TOPIC_WHATSAPP, payload, producer)
    except Exception as exc:
        logger.error("whatsapp_webhook: publish failed: %s", exc)
        # Return 200 to Twilio regardless — prevents automatic retry storm
        return {"status": "error_queued"}

    return {"status": "accepted"}


# ── 3. POST /webhooks/whatsapp/status ────────────────────────────────────────

@app.post("/webhooks/whatsapp/status", tags=["channels"])
async def whatsapp_status_webhook(request: Request):
    """
    Receive Twilio delivery status callbacks for outbound WhatsApp messages.

    Twilio POSTs to this URL when a message transitions:
      queued → sent → delivered  (or failed / undelivered)

    The delivery status is persisted to the messages table so dashboards
    and agents can detect delivery failures. Twilio expects a 200 response.

    Configure in Twilio Console → WhatsApp Sandbox Settings →
    Status Callback URL: https://your-domain/webhooks/whatsapp/status
    """
    form_data = dict(await request.form())

    handler = WhatsAppHandler()
    status_data = await handler.handle_delivery_status(form_data)

    message_sid = status_data.get("message_sid")
    delivery_status = status_data.get("status", "unknown")
    to_phone = status_data.get("to", "")

    # Persist delivery status update (best-effort, non-blocking)
    if message_sid:
        try:
            await queries.update_message_delivery(
                channel_message_id=message_sid,
                delivery_status=delivery_status,
                error=status_data.get("error_message"),
            )
        except Exception as exc:
            logger.warning("whatsapp_status: DB update failed: %s", exc)

    logger.info(
        "whatsapp_status: sid=%s status=%s to=%s",
        message_sid, delivery_status, to_phone,
    )
    return {"status": "ok"}


# ── 4. GET /conversations/{conversation_id} ───────────────────────────────────

@app.get("/conversations/{conversation_id}", tags=["conversations"])
async def get_conversation(conversation_id: str):
    """
    Return a conversation record with its full message history.

    Response shape:
        {
          "conversation_id": str,
          "customer_id": str,
          "initial_channel": str,
          "current_channel": str,
          "status": str,
          "sentiment_score": float | null,
          "started_at": ISO-8601,
          "ended_at": ISO-8601 | null,
          "messages": [{role, content, channel, direction, created_at}, ...]
        }

    Raises 404 if the conversation_id does not exist.
    Raises 503 if the database is unavailable.
    """
    try:
        pool = await queries.get_pool()
        async with pool.acquire() as conn:
            conv_row = await conn.fetchrow(
                """
                SELECT id, customer_id, initial_channel, current_channel,
                       status, sentiment_score, sentiment_trend,
                       started_at, ended_at
                FROM conversations
                WHERE id = $1::uuid
                """,
                conversation_id,
            )

            if not conv_row:
                raise HTTPException(
                    status_code=404,
                    detail=f"Conversation {conversation_id} not found.",
                )

            msg_rows = await conn.fetch(
                """
                SELECT role, content, channel, direction,
                       created_at, delivery_status, tool_calls
                FROM messages
                WHERE conversation_id = $1::uuid
                ORDER BY created_at ASC
                """,
                conversation_id,
            )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("get_conversation: DB error: %s", exc, exc_info=True)
        raise HTTPException(status_code=503, detail="Database temporarily unavailable.")

    messages = [
        {
            "role": r["role"],
            "content": r["content"],
            "channel": r["channel"],
            "direction": r["direction"],
            "created_at": r["created_at"].isoformat(),
            "delivery_status": r["delivery_status"],
        }
        for r in msg_rows
    ]

    return {
        "conversation_id": str(conv_row["id"]),
        "customer_id": str(conv_row["customer_id"]),
        "initial_channel": conv_row["initial_channel"],
        "current_channel": conv_row["current_channel"],
        "status": conv_row["status"],
        "sentiment_score": float(conv_row["sentiment_score"]) if conv_row["sentiment_score"] is not None else None,
        "sentiment_trend": conv_row["sentiment_trend"],
        "started_at": conv_row["started_at"].isoformat(),
        "ended_at": conv_row["ended_at"].isoformat() if conv_row["ended_at"] else None,
        "message_count": len(messages),
        "messages": messages,
    }


# ── 5. GET /customers/lookup ──────────────────────────────────────────────────

@app.get("/customers/lookup", tags=["customers"])
async def lookup_customer(
    email: Optional[str] = None,
    phone: Optional[str] = None,
):
    """
    Look up a customer by email or phone number. Does NOT create a new record.

    Query parameters (at least one required):
        ?email=alice@acme.com
        ?phone=+1234567890
        ?email=alice@acme.com&phone=+1234567890   (AND — must match both)

    Response:
        {
          "customer_id": str,
          "email": str | null,
          "phone": str | null,
          "name": str | null,
          "created_at": ISO-8601,
          "conversation_count": int,
          "open_ticket_count": int,
          "channels_used": [str, ...]
        }

    Raises 400 if neither email nor phone is supplied.
    Raises 404 if no matching customer is found.
    """
    if not email and not phone:
        raise HTTPException(
            status_code=400,
            detail="Provide at least one of: email, phone",
        )

    try:
        pool = await queries.get_pool()
        async with pool.acquire() as conn:
            # Build WHERE clause dynamically
            conditions = []
            params: list = []
            idx = 1
            if email:
                conditions.append(f"LOWER(email) = LOWER(${idx})")
                params.append(email)
                idx += 1
            if phone:
                conditions.append(f"phone = ${idx}")
                params.append(phone)
                idx += 1

            where = " AND ".join(conditions)
            row = await conn.fetchrow(
                f"SELECT id, email, phone, name, created_at FROM customers WHERE {where}",
                *params,
            )

            if not row:
                raise HTTPException(
                    status_code=404,
                    detail="No customer found for the supplied identifier(s).",
                )

            customer_id = str(row["id"])

            # Aggregate conversation + ticket counts in a single query
            stats = await conn.fetchrow(
                """
                SELECT
                    COUNT(DISTINCT c.id)                              AS conversation_count,
                    COUNT(DISTINCT t.id) FILTER (WHERE t.status = 'open') AS open_ticket_count,
                    ARRAY_AGG(DISTINCT c.initial_channel)             AS channels_used
                FROM conversations c
                LEFT JOIN tickets t ON t.customer_id = c.customer_id
                WHERE c.customer_id = $1::uuid
                """,
                customer_id,
            )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("lookup_customer: DB error: %s", exc, exc_info=True)
        raise HTTPException(status_code=503, detail="Database temporarily unavailable.")

    return {
        "customer_id": customer_id,
        "email": row["email"],
        "phone": row["phone"],
        "name": row["name"],
        "created_at": row["created_at"].isoformat(),
        "conversation_count": stats["conversation_count"] or 0,
        "open_ticket_count": stats["open_ticket_count"] or 0,
        "channels_used": [c for c in (stats["channels_used"] or []) if c],
    }


# ── 6. GET /metrics/channels ──────────────────────────────────────────────────

@app.get("/metrics/channels", tags=["metrics"])
async def channel_metrics():
    """
    Return last-24-hour performance summary broken down by channel.

    Response:
        {
          "period": "last_24h",
          "channels": [
            {
              "channel": "email",
              "message_count": int,
              "avg_latency_ms": float | null,
              "escalation_count": int,
              "escalation_rate": float,   // 0.0–1.0
              "avg_sentiment": float | null
            },
            ...
          ]
        }

    Falls back to an empty channels list if the DB is unavailable so dashboards
    degrade gracefully rather than returning 5xx.
    """
    try:
        rows = await queries.get_channel_summary()
    except Exception as exc:
        logger.error("channel_metrics: DB error: %s", exc)
        rows = []

    channels = []
    for row in rows:
        msg_count = row.get("message_count") or 0
        esc_count = row.get("escalation_count") or 0
        channels.append({
            "channel": row.get("channel"),
            "message_count": msg_count,
            "avg_latency_ms": float(row["avg_latency_ms"]) if row.get("avg_latency_ms") is not None else None,
            "escalation_count": esc_count,
            "escalation_rate": round(esc_count / msg_count, 4) if msg_count else 0.0,
            "avg_sentiment": float(row["avg_sentiment"]) if row.get("avg_sentiment") is not None else None,
        })

    return {"period": "last_24h", "channels": channels}


# ── 6a. GET /api/metrics ──────────────────────────────────────────────────────

@app.get("/api/metrics", tags=["admin"])
async def api_metrics():
    """Admin dashboard: system-wide metrics summary. Falls back to zeros if DB unavailable."""
    try:
        rows = await queries.get_channel_summary()
    except Exception:
        rows = []

    total = sum((r.get("message_count") or 0) for r in rows)
    escalations = sum((r.get("escalation_count") or 0) for r in rows)
    avg_latency = None
    latencies = [float(r["avg_latency_ms"]) for r in rows if r.get("avg_latency_ms") is not None]
    if latencies:
        avg_latency = round(sum(latencies) / len(latencies), 1)

    channels = {}
    for row in rows:
        ch = row.get("channel")
        if ch:
            msg_count = row.get("message_count") or 0
            esc_count = row.get("escalation_count") or 0
            channels[ch] = {
                "count": msg_count,
                "avg_sentiment": float(row["avg_sentiment"]) if row.get("avg_sentiment") is not None else None,
                "escalation_rate": round(esc_count / msg_count * 100, 1) if msg_count else 0.0,
                "avg_response_ms": float(row["avg_latency_ms"]) if row.get("avg_latency_ms") is not None else None,
            }

    return {
        "total_tickets": total,
        "total_tickets_trend": 0.0,
        "avg_response_time_ms": avg_latency,
        "response_time_target": 2000,
        "active_conversations": 0,
        "escalations_count": escalations,
        "escalation_rate": round(escalations / total * 100, 1) if total else 0.0,
        "channels": channels,
    }


# ── 6b. GET /api/tickets ──────────────────────────────────────────────────────

@app.get("/api/tickets", tags=["admin"])
async def api_tickets(limit: int = 20):
    """Admin dashboard: recent tickets list. Returns empty list if DB unavailable."""
    try:
        pool = await queries.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT t.id AS ticket_id, t.subject, t.status, t.priority,
                       t.channel, t.created_at,
                       c.email AS customer_email, c.phone AS customer_phone
                FROM tickets t
                LEFT JOIN customers c ON c.id = t.customer_id
                ORDER BY t.created_at DESC
                LIMIT $1
                """,
                limit,
            )
        tickets = [
            {
                "ticket_id": str(r["ticket_id"]),
                "subject": r["subject"],
                "status": r["status"],
                "priority": r["priority"],
                "channel": r["channel"],
                "created_at": r["created_at"].isoformat(),
                "customer_email": r["customer_email"],
                "customer_phone": r["customer_phone"],
            }
            for r in rows
        ]
        return {"tickets": tickets}
    except Exception as exc:
        logger.error("api_tickets: DB error: %s", exc)
        return {"tickets": []}


# ── 6c. GET /api/activity ─────────────────────────────────────────────────────

@app.get("/api/activity", tags=["admin"])
async def api_activity(limit: int = 20):
    """Admin dashboard: recent activity feed. Returns empty list if DB unavailable."""
    try:
        pool = await queries.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT m.id, m.channel, m.direction, m.role, m.content,
                       m.created_at, c.email AS customer_email
                FROM messages m
                LEFT JOIN conversations cv ON cv.id = m.conversation_id
                LEFT JOIN customers c ON c.id = cv.customer_id
                ORDER BY m.created_at DESC
                LIMIT $1
                """,
                limit,
            )
        activity = [
            {
                "id": str(r["id"]),
                "type": "reply_sent" if r["direction"] == "outbound" else "ticket_opened",
                "channel": r["channel"],
                "message": f'{r["customer_email"] or "customer"} — {(r["content"] or "")[:80]}',
                "time": r["created_at"].isoformat(),
            }
            for r in rows
        ]
        return activity
    except Exception as exc:
        logger.error("api_activity: DB error: %s", exc)
        return []


# ── Helper: ticket ID generator ───────────────────────────────────────────────

def _gen_ticket_id(prefix: str, length: int = 7) -> str:
    chars = string.ascii_uppercase + string.digits
    suffix = ''.join(random.choices(chars, k=length))
    return f"{prefix}-{suffix}"


# ── 6a. POST /api/send-whatsapp ───────────────────────────────────────────────

@app.post("/api/send-whatsapp", tags=["public"])
async def api_send_whatsapp(request: Request):
    """
    Landing-page WhatsApp channel: customer submits name, phone, message.
    Sends an acknowledgment WhatsApp message via Twilio sandbox and returns a ticket ID.
    No Kafka or AI pipeline required — direct Twilio send for the demo.
    """
    data = await request.json()
    name    = (data.get("name") or "Customer").strip()
    phone   = (data.get("phone") or "").strip()
    message = (data.get("message") or "").strip()

    if not phone:
        raise HTTPException(status_code=422, detail="phone is required")
    if not message:
        raise HTTPException(status_code=422, detail="message is required")

    ticket_id = _gen_ticket_id("WA")

    # Normalise phone — add + if missing
    if not phone.startswith("+"):
        phone = "+" + phone.lstrip("0").lstrip("+")

    try:
        wa = WhatsAppHandler()
        ack = (
            f"Hi {name}! Your NimbusFlow support ticket *{ticket_id}* has been received.\n\n"
            f"Your message: \"{message[:120]}\"\n\n"
            f"Our AI agent is processing your request and will reply here on WhatsApp shortly. "
            f"You can also track your ticket at our website using this ID."
        )
        await wa.send_message(phone, ack)
        logger.info("api_send_whatsapp: sent ack to %s ticket=%s", phone, ticket_id)
    except Exception as exc:
        logger.error("api_send_whatsapp: Twilio error: %s", exc)
        # Return the ticket ID even if WhatsApp send fails — demo resilience
        return {"ticket_id": ticket_id, "status": "queued", "warning": str(exc)}

    return {"ticket_id": ticket_id, "status": "sent", "channel": "whatsapp"}


# ── 6b. POST /api/send-email ──────────────────────────────────────────────────

@app.post("/api/send-email", tags=["public"])
async def api_send_email(request: Request):
    """
    Landing-page Email channel: customer submits name, email, subject, message.
    Creates a ticket ID and (optionally) sends acknowledgment via Gmail.
    Falls back gracefully if Gmail is not configured.
    """
    data = await request.json()
    name    = (data.get("name") or "Customer").strip()
    email   = (data.get("email") or "").strip()
    subject = (data.get("subject") or "Support Request").strip()
    message = (data.get("message") or "").strip()

    if not email:
        raise HTTPException(status_code=422, detail="email is required")
    if not message:
        raise HTTPException(status_code=422, detail="message is required")

    ticket_id = _gen_ticket_id("EMAIL")

    # Try sending acknowledgment email via Gmail — non-blocking on failure
    try:
        from production.channels.gmail_handler import GmailHandler
        handler = GmailHandler()
        ack_body = (
            f"Hi {name},\n\n"
            f"Thank you for reaching out to NimbusFlow Support!\n\n"
            f"Your ticket *{ticket_id}* has been received.\n"
            f"Subject: {subject}\n"
            f"Message: {message[:200]}\n\n"
            f"Our AI agent will respond to you shortly at this email address.\n\n"
            f"Best regards,\nNimbusFlow AI Support"
        )
        await handler.send_email(
            to=email,
            subject=f"[{ticket_id}] Support Request Received — {subject}",
            body=ack_body,
        )
        logger.info("api_send_email: ack sent to %s ticket=%s", email, ticket_id)
        return {"ticket_id": ticket_id, "status": "sent", "channel": "email"}
    except Exception as exc:
        logger.warning("api_send_email: email send skipped: %s", exc)
        # Return ticket ID anyway — agent will reply async
        return {"ticket_id": ticket_id, "status": "queued", "channel": "email"}


# ── 7. GET /health ────────────────────────────────────────────────────────────

@app.get("/health", tags=["ops"])
async def health():
    """
    Kubernetes liveness probe with channel status summary.

    Always returns 200 while the process is alive. Includes a lightweight
    channel availability check so dashboards can detect partial outages
    without blocking the liveness check itself.

    Response:
        {
          "status": "ok",
          "version": "2.0.0",
          "channels": {
            "email": "configured" | "unconfigured",
            "whatsapp": "configured" | "unconfigured",
            "web_form": "ready"
          }
        }
    """
    gmail_creds = os.path.exists(os.getenv("GMAIL_TOKEN_PATH", "secrets/gmail_token.json"))
    twilio_configured = bool(
        os.getenv("TWILIO_ACCOUNT_SID") and os.getenv("TWILIO_AUTH_TOKEN")
    )

    return {
        "status": "ok",
        "version": app.version,
        "channels": {
            "email": "configured" if gmail_creds else "unconfigured",
            "whatsapp": "configured" if twilio_configured else "unconfigured",
            "web_form": "ready",
        },
    }


# ── 8. GET /ready ─────────────────────────────────────────────────────────────

@app.get("/ready", tags=["ops"])
async def ready():
    """
    Kubernetes readiness probe — checks that DB and Kafka are reachable.
    Returns 503 if either dependency is unavailable so k8s stops routing traffic.
    """
    errors: list[str] = []

    try:
        pool = await queries.get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
    except Exception as exc:
        errors.append(f"postgres: {exc}")

    try:
        producer = await get_producer()
        if not producer._sender.sender_task or producer._sender.sender_task.done():
            errors.append("kafka: producer not running")
    except Exception as exc:
        errors.append(f"kafka: {exc}")

    if errors:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not ready", "errors": errors},
        )

    return {"status": "ready"}
