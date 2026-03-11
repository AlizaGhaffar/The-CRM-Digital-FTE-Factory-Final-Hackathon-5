"""
production/channels/web_form_handler.py

Web Form channel handler — Exercise 2.2.
Implements SupportFormSubmission with Pydantic validation, FastAPI router
with POST /support/submit and GET /support/ticket/{ticket_id} endpoints,
Kafka publishing, and ticket DB record creation.

Flow:
  Browser POST /support/submit → validate → create DB ticket → publish to Kafka
  Agent processes Kafka event → send_confirmation_email() → customer email

Setup:
  1. Mount this router in api/main.py: app.include_router(router)
  2. Set env vars: KAFKA_BOOTSTRAP_SERVERS, POSTGRES_*, SMTP_*

Developer audience (D-007): allow code snippets, error messages, technical depth.
Business-impact detection (D-008): keywords bump priority to "high".
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import smtplib
import ssl
import uuid
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import structlog
from aiokafka import AIOKafkaProducer
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, field_validator

from production.database import queries

log = structlog.get_logger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC_WEB_FORM", "fte.tickets.incoming")

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
FROM_EMAIL = os.getenv("SUPPORT_FROM_EMAIL", "support@nimbusflow.io")

VALID_CATEGORIES = ["general", "technical", "billing", "feedback", "bug_report"]

# Business-impact keywords that bump priority to "high" (D-008)
HIGH_PRIORITY_SIGNALS: list[str] = [
    "ci/cd", "ci cd", "pipeline", "production environment",
    "production down", "affecting our team", "affecting all users",
    "evaluating nimbusflow", "200+ employees", "200 employees",
    "enterprise", "migration", "data loss",
]

# ── FastAPI router ─────────────────────────────────────────────────────────────

router = APIRouter(prefix="/support", tags=["support-form"])


# ── Pydantic models ───────────────────────────────────────────────────────────

class SupportFormSubmission(BaseModel):
    """
    Validated web support form submission.

    Required fields: name, email, subject, category, message.
    Optional fields: priority, attachments, honeypot (anti-spam).

    Validators enforce:
    - name: minimum 2 characters after stripping whitespace
    - message: minimum 10 characters after stripping whitespace
    - category: must be one of the valid categories list
    - honeypot: must be empty (bot-trap field)
    - message: script tags stripped (XSS guard at system boundary)
    """

    name: str
    email: EmailStr
    subject: str
    category: str                              # 'general', 'technical', 'billing', 'feedback', 'bug_report'
    message: str
    priority: Optional[str] = "medium"
    attachments: Optional[list[str]] = []
    honeypot: Optional[str] = None             # Anti-spam: must be empty if present

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        if not v or len(v.strip()) < 2:
            raise ValueError("Name must be at least 2 characters")
        return v.strip()

    @field_validator("message")
    @classmethod
    def message_must_have_content(cls, v: str) -> str:
        if not v or len(v.strip()) < 10:
            raise ValueError("Message must be at least 10 characters")
        # Strip script tags — XSS guard at system boundary
        cleaned = re.sub(
            r"<\s*script[^>]*>.*?<\s*/\s*script\s*>",
            "",
            v.strip(),
            flags=re.IGNORECASE | re.DOTALL,
        )
        return cleaned

    @field_validator("category")
    @classmethod
    def category_must_be_valid(cls, v: str) -> str:
        if v not in VALID_CATEGORIES:
            raise ValueError(f"Category must be one of: {VALID_CATEGORIES}")
        return v

    @field_validator("honeypot")
    @classmethod
    def no_honeypot(cls, v: Optional[str]) -> Optional[str]:
        if v:
            raise ValueError("Spam detected")
        return v


class SupportFormResponse(BaseModel):
    """Response returned to the browser after successful form submission."""

    ticket_id: str
    message: str
    estimated_response_time: str


class TicketStatusResponse(BaseModel):
    """Response for GET /support/ticket/{ticket_id}."""

    ticket_id: str
    status: str
    category: Optional[str]
    priority: Optional[str]
    created_at: str
    resolved_at: Optional[str]
    resolution_notes: Optional[str]


# ── Kafka helper ──────────────────────────────────────────────────────────────

async def publish_to_kafka(topic: str, message_data: dict) -> bool:
    """
    Publish a message dict to a Kafka topic.

    Creates a short-lived producer per call so the router has no startup
    dependency on a shared producer being ready. For high-throughput use
    the shared producer in api/main.py instead.

    Args:
        topic: Kafka topic name.
        message_data: Dict to serialize as JSON.

    Returns:
        True on success, False on any error (agent still gets DB record).
    """
    producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    try:
        await producer.start()
        await producer.send_and_wait(topic, message_data)
        log.info("web_form.kafka_published", topic=topic, ticket_id=message_data.get("channel_message_id"))
        return True
    except Exception as exc:
        log.error("web_form.kafka_publish_failed", topic=topic, error=str(exc))
        return False
    finally:
        await producer.stop()


# ── DB helper ─────────────────────────────────────────────────────────────────

async def create_ticket_record(ticket_id: str, message_data: dict) -> bool:
    """
    Persist the web form submission as a ticket in PostgreSQL.

    Creates or finds the customer record first, then inserts a ticket row
    linked to a new conversation. Failures are logged but do not abort the
    HTTP response — the Kafka event is the primary delivery mechanism.

    Args:
        ticket_id: UUID string for the new ticket.
        message_data: Normalized channel payload from the form submission.

    Returns:
        True on success, False on DB error.
    """
    try:
        pool = await queries.get_pool()
        async with pool.acquire() as conn:
            # 1. Find or create customer
            customer_id = await queries.find_or_create_customer(
                email=message_data.get("customer_email"),
                name=message_data.get("customer_name"),
                channel="web_form",
            )

            # 2. Create conversation record
            conversation_id = await conn.fetchval(
                """
                INSERT INTO conversations (customer_id, initial_channel, status)
                VALUES ($1, 'web_form', 'active')
                RETURNING id
                """,
                customer_id,
            )

            # 3. Create ticket record
            await conn.execute(
                """
                INSERT INTO tickets (id, conversation_id, customer_id, source_channel,
                                     category, priority, status)
                VALUES ($1::uuid, $2, $3, 'web_form', $4, $5, 'open')
                """,
                ticket_id,
                conversation_id,
                customer_id,
                message_data.get("category", "general"),
                message_data.get("priority", "medium"),
            )

            # 4. Store the inbound message
            await conn.execute(
                """
                INSERT INTO messages (conversation_id, channel, direction, role,
                                      content, channel_message_id)
                VALUES ($1, 'web_form', 'inbound', 'customer', $2, $3)
                """,
                conversation_id,
                message_data.get("content", ""),
                ticket_id,
            )

        log.info("web_form.ticket_created", ticket_id=ticket_id, customer_id=str(customer_id))
        return True

    except Exception as exc:
        log.error("web_form.ticket_create_failed", ticket_id=ticket_id, error=str(exc))
        return False


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/submit", response_model=SupportFormResponse)
async def submit_support_form(submission: SupportFormSubmission) -> SupportFormResponse:
    """
    Accept a web support form submission, create a ticket, and publish to Kafka.

    Steps:
      1. Pydantic validates the request body (name, email, message, category).
      2. Generate a unique ticket_id (UUID4).
      3. Detect business-impact signals and set priority accordingly.
      4. Publish the normalized message to the Kafka inbound topic.
      5. Persist a ticket row to PostgreSQL.
      6. Return ticket_id and estimated response time to the browser.

    The agent picks up the Kafka event asynchronously and sends a reply via
    the customer's email address.
    """
    ticket_id = str(uuid.uuid4())
    received_at = datetime.utcnow().isoformat()

    # Detect high-priority business-impact signals (D-008)
    body_lower = submission.message.lower()
    priority = submission.priority or "medium"
    for signal in HIGH_PRIORITY_SIGNALS:
        if signal in body_lower:
            priority = "high"
            log.info("web_form.priority_upgraded", signal=signal, ticket_id=ticket_id)
            break

    message_data = {
        "channel": "web_form",
        "channel_message_id": ticket_id,
        "customer_email": str(submission.email),
        "customer_name": submission.name,
        "subject": submission.subject,
        "content": submission.message,
        "category": submission.category,
        "priority": priority,
        "received_at": received_at,
        "metadata": {
            "form_version": "1.0",
            "attachments": submission.attachments or [],
        },
    }

    # Publish to Kafka (primary) and create DB record (secondary) concurrently
    kafka_ok, db_ok = await asyncio.gather(
        publish_to_kafka(KAFKA_TOPIC, message_data),
        create_ticket_record(ticket_id, message_data),
        return_exceptions=False,
    )

    if not kafka_ok and not db_ok:
        log.error("web_form.both_storage_failed", ticket_id=ticket_id)
        raise HTTPException(
            status_code=503,
            detail="Service temporarily unavailable. Please try again in a moment.",
        )

    log.info(
        "web_form.submission_accepted",
        ticket_id=ticket_id,
        category=submission.category,
        priority=priority,
        kafka_ok=kafka_ok,
        db_ok=db_ok,
    )

    return SupportFormResponse(
        ticket_id=ticket_id,
        message="Thank you for contacting us! Our AI assistant will respond shortly.",
        estimated_response_time="Usually within 5 minutes",
    )


@router.get("/ticket/{ticket_id}", response_model=TicketStatusResponse)
async def get_ticket_status(ticket_id: str) -> TicketStatusResponse:
    """
    Retrieve the current status of a support ticket by ID.

    Returns ticket status, category, priority, timestamps, and resolution
    notes if the ticket has been resolved.

    Raises 404 if the ticket_id does not exist.
    Raises 503 if the database is unavailable.
    """
    try:
        pool = await queries.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, status, category, priority,
                       created_at, resolved_at, resolution_notes
                FROM tickets
                WHERE id = $1::uuid
                """,
                ticket_id,
            )
    except Exception as exc:
        log.error("web_form.ticket_fetch_failed", ticket_id=ticket_id, error=str(exc))
        raise HTTPException(status_code=503, detail="Database temporarily unavailable.")

    if not row:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found.")

    return TicketStatusResponse(
        ticket_id=str(row["id"]),
        status=row["status"],
        category=row["category"],
        priority=row["priority"],
        created_at=row["created_at"].isoformat(),
        resolved_at=row["resolved_at"].isoformat() if row["resolved_at"] else None,
        resolution_notes=row["resolution_notes"],
    )


# ── Backward-compat helpers (used by api/main.py) ────────────────────────────

class WebFormSubmission(BaseModel):
    """Legacy model used by parse_web_form() called from api/main.py."""

    email: EmailStr
    name: Optional[str] = None
    subject: str
    message: str
    session_id: Optional[str] = None
    honeypot: Optional[str] = None

    @field_validator("honeypot")
    @classmethod
    def no_honeypot(cls, v: Optional[str]) -> Optional[str]:
        if v:
            raise ValueError("Spam detected")
        return v

    @field_validator("message")
    @classmethod
    def no_script_injection(cls, v: str) -> str:
        cleaned = re.sub(
            r"<\s*script[^>]*>.*?<\s*/\s*script\s*>",
            "", v, flags=re.IGNORECASE | re.DOTALL,
        )
        return cleaned


def parse_web_form(form_data: dict) -> dict:
    """
    Validate and normalize a web form dict into a channel payload.
    Used by api/main.py webhook handler before Kafka publish.
    Raises pydantic.ValidationError if required fields are invalid.
    """
    submission = WebFormSubmission(**form_data)

    body_lower = submission.message.lower()
    priority = "medium"
    for signal in HIGH_PRIORITY_SIGNALS:
        if signal in body_lower:
            priority = "high"
            break

    return {
        "channel": "web_form",
        "channel_message_id": submission.session_id or "",
        "customer_email": str(submission.email),
        "customer_name": submission.name or "",
        "subject": submission.subject,
        "content": submission.message,
        "session_id": submission.session_id,
        "priority": priority,
    }


# ── Outbound: confirmation email ──────────────────────────────────────────────

def send_confirmation_email(
    to_email: str,
    customer_name: Optional[str],
    ticket_id: str,
    response_body: str,
    subject: str = "Your NimbusFlow Support Request",
) -> bool:
    """
    Send the agent's response to the customer's email address via SMTP.
    Used after the agent processes the Kafka event and produces a reply.

    Returns True on success, False on failure.
    """
    if not SMTP_USER or not SMTP_PASSWORD:
        log.error("web_form.smtp_not_configured")
        return False

    full_subject = f"Re: {subject} [Ticket {ticket_id}]"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = full_subject
    msg["From"] = f"NimbusFlow Support <{FROM_EMAIL}>"
    msg["To"] = to_email
    msg.attach(MIMEText(response_body, "plain"))

    ctx = ssl.create_default_context()
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls(context=ctx)
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(FROM_EMAIL, to_email, msg.as_string())
        log.info("web_form.confirmation_sent", to=to_email, ticket_id=ticket_id)
        return True
    except smtplib.SMTPException as exc:
        log.error("web_form.smtp_send_failed", error=str(exc))
        return False


async def send_confirmation_email_async(
    to_email: str,
    customer_name: Optional[str],
    ticket_id: str,
    response_body: str,
    subject: str = "Your NimbusFlow Support Request",
) -> bool:
    """Async wrapper around send_confirmation_email for use in async contexts."""
    return await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: send_confirmation_email(to_email, customer_name, ticket_id, response_body, subject),
    )
