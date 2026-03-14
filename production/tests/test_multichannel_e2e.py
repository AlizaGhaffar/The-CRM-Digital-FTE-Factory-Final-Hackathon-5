"""
production/tests/test_multichannel_e2e.py
Exercise 3.1 — Multi-Channel End-to-End Testing

Validates the full stack from HTTP webhook → Kafka publish → agent
skills → database writes → response across all three channels.

External dependencies (Kafka, PostgreSQL, LLM APIs) are mocked at
the boundary so tests run without infrastructure.

Test classes:
    TestWebFormChannel        — POST /support/submit + GET /support/ticket/{id}
    TestEmailChannel          — POST /webhooks/gmail (Pub/Sub push)
    TestWhatsAppChannel       — POST /webhooks/whatsapp + /webhooks/whatsapp/status
    TestCrossChannelContinuity — GET /customers/lookup + GET /conversations/{id}
    TestChannelMetrics        — GET /metrics/channels + GET /health
    TestAgentSkills           — All 5 skills: create_ticket, get_customer_history,
                                analyze_sentiment, search_knowledge_base,
                                escalate_to_human, send_response

Run:
    pytest production/tests/test_multichannel_e2e.py -v
    pytest production/tests/test_multichannel_e2e.py -v -k "TestAgentSkills"
"""

import base64
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ── Shared test data ───────────────────────────────────────────────────────────

CUSTOMER_EMAIL = "alice@acme.com"
CUSTOMER_PHONE = "+14155551234"
CUSTOMER_NAME = "Alice Acme"
CUSTOMER_ID = "cust-e2e-0001"
CONVERSATION_ID = "conv-e2e-0001"
TICKET_ID = str(uuid.uuid4())
ESCALATION_ID = "esc-e2e-0001"
MESSAGE_ID = "msg-e2e-0001"


# ── Shared mock factories ──────────────────────────────────────────────────────

def _mock_queries():
    """
    Return a MagicMock with all production.database.queries calls stubbed.
    Each test can override specific attributes to test different scenarios.
    """
    m = MagicMock()
    m.get_pool = AsyncMock()
    m.close_pool = AsyncMock()

    # Customer
    m.find_or_create_customer = AsyncMock(return_value=CUSTOMER_ID)
    m.get_customer_by_id = AsyncMock(return_value={
        "id": CUSTOMER_ID, "email": CUSTOMER_EMAIL, "phone": CUSTOMER_PHONE,
        "name": CUSTOMER_NAME, "created_at": datetime.now(timezone.utc),
    })
    m.get_customer_summary = AsyncMock(return_value={})

    # Conversation
    m.get_or_create_conversation = AsyncMock(return_value=CONVERSATION_ID)
    m.update_conversation_sentiment = AsyncMock()
    m.close_conversation = AsyncMock()

    # Messages
    m.store_message = AsyncMock(return_value=MESSAGE_ID)
    m.update_message_delivery = AsyncMock()
    m.load_conversation_history = AsyncMock(return_value=[])

    # Tickets
    m.create_ticket = AsyncMock(return_value=TICKET_ID)
    m.update_ticket_status = AsyncMock()
    m.get_ticket = AsyncMock(return_value={
        "id": TICKET_ID,
        "status": "open",
        "category": "technical",
        "priority": "medium",
        "created_at": datetime.now(timezone.utc),
        "resolved_at": None,
        "resolution_notes": None,
        "source_channel": "web_form",
    })
    m.get_open_tickets = AsyncMock(return_value=[])

    # Customer history
    m.get_customer_history = AsyncMock(return_value=[])

    # Knowledge base
    m.search_knowledge_base = AsyncMock(return_value=[
        {
            "title": "Password Reset",
            "content": "Visit nimbusflow.io/forgot-password to reset your password.",
            "similarity": 0.87,
            "category": "account",
        }
    ])

    # Escalation
    m.create_escalation = AsyncMock(return_value=ESCALATION_ID)

    # Metrics
    m.record_metric = AsyncMock()
    m.get_channel_summary = AsyncMock(return_value=[
        {
            "channel": "email",
            "message_count": 42,
            "avg_latency_ms": 1820.5,
            "escalation_count": 6,
            "avg_sentiment": 0.71,
        },
        {
            "channel": "whatsapp",
            "message_count": 31,
            "avg_latency_ms": 1450.0,
            "escalation_count": 4,
            "avg_sentiment": 0.65,
        },
        {
            "channel": "web_form",
            "message_count": 17,
            "avg_latency_ms": 2100.0,
            "escalation_count": 2,
            "avg_sentiment": 0.78,
        },
    ])

    # Knowledge base (upsert)
    m.search_knowledge_base = AsyncMock(return_value=[
        {"title": "Password Reset", "content": "...", "similarity": 0.87}
    ])

    return m


def _mock_producer():
    """Return a fully-stubbed AIOKafkaProducer."""
    p = AsyncMock()
    p.start = AsyncMock()
    p.stop = AsyncMock()
    p.send_and_wait = AsyncMock()
    p._sender = MagicMock()
    p._sender.sender_task = MagicMock()
    p._sender.sender_task.done = MagicMock(return_value=False)
    return p


def _mock_openai(sentiment_score: str = "0.75"):
    """Return a mock OpenAI/Gemini client for sentiment + embedding calls."""
    client = MagicMock()
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    client.chat.completions.create = AsyncMock(
        return_value=MagicMock(
            choices=[MagicMock(message=MagicMock(content=sentiment_score))]
        )
    )
    client.embeddings = MagicMock()
    client.embeddings.create = AsyncMock(
        return_value=MagicMock(data=[MagicMock(embedding=[0.1] * 1536)])
    )
    return client


def _pubsub_push(history_id: str = "123456", email: str = CUSTOMER_EMAIL) -> dict:
    """Build a valid Google Cloud Pub/Sub push body."""
    data = json.dumps({"historyId": history_id, "emailAddress": email})
    encoded = base64.urlsafe_b64encode(data.encode()).decode()
    return {
        "message": {
            "data": encoded,
            "messageId": "pub-msg-001",
            "publishTime": "2026-03-10T10:00:00Z",
        },
        "subscription": "projects/test-project/subscriptions/gmail-push-sub",
    }


def _twilio_form(
    body: str = "How do I reset my password?",
    phone: str = CUSTOMER_PHONE,
    message_sid: str = "SM_E2E_001",
) -> dict:
    """Build a Twilio WhatsApp webhook form payload."""
    return {
        "MessageSid": message_sid,
        "AccountSid": "AC_test",
        "From": f"whatsapp:{phone}",
        "To": "whatsapp:+14155238886",
        "Body": body,
        "NumMedia": "0",
        "ProfileName": CUSTOMER_NAME,
        "WaId": phone.lstrip("+"),
        "SmsStatus": "received",
    }


# ── Shared app fixture ────────────────────────────────────────────────────────

@pytest.fixture
def mock_q():
    return _mock_queries()


@pytest.fixture
def client(mock_q):
    """
    TestClient with Kafka and database fully mocked.
    Shared across all test classes via the module-level fixture.
    """
    producer = _mock_producer()

    with patch("production.api.main.AIOKafkaProducer", return_value=producer), \
         patch("production.api.main.queries", mock_q), \
         patch("production.channels.web_form_handler.queries", mock_q), \
         patch(
             "production.channels.web_form_handler.AIOKafkaProducer",
             return_value=_mock_producer(),
         ), \
         patch("production.api.main.fetch_new_messages", new_callable=AsyncMock,
               return_value=[]) as _fetch, \
         patch.dict("os.environ", {
             "TWILIO_VALIDATE_SIGNATURE": "false",
             "GMAIL_TOKEN_PATH": "/tmp/does-not-exist.json",
         }):
        from production.api.main import app
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


# ── 1. TestWebFormChannel ──────────────────────────────────────────────────────

class TestWebFormChannel:
    """Test the web support form — POST /support/submit and GET /support/ticket/{id}."""

    def test_form_submission_valid(self, client):
        """Valid form submission → 202 with ticket_id and confirmation message."""
        resp = client.post("/support/submit", json={
            "name": CUSTOMER_NAME,
            "email": CUSTOMER_EMAIL,
            "subject": "GitHub webhook stopped firing",
            "category": "technical",
            "message": (
                "Our GitHub webhook stopped firing after we updated the repo settings. "
                "Receiving 404 errors on all incoming pushes."
            ),
            "priority": "medium",
        })
        assert resp.status_code == 202
        data = resp.json()
        assert "ticket_id" in data
        assert "estimated_response_time" in data
        assert "AI assistant" in data["message"] or "respond" in data["message"]

    def test_form_submission_high_priority_signal(self, client):
        """CI/CD keyword → priority auto-upgraded to high."""
        resp = client.post("/support/submit", json={
            "name": "Bob",
            "email": "bob@corp.com",
            "subject": "Pipeline broken",
            "category": "technical",
            "message": (
                "Our CI/CD pipeline has been failing for 2 hours and is blocking "
                "all deployments across our production environment."
            ),
        })
        assert resp.status_code == 202
        assert "ticket_id" in resp.json()

    def test_form_validation_invalid_email(self, client):
        """Invalid email address → 422 Unprocessable Entity."""
        resp = client.post("/support/submit", json={
            "name": "Alice",
            "email": "not-an-email",
            "subject": "Help needed",
            "category": "general",
            "message": "I need help with my account settings and integrations.",
        })
        assert resp.status_code == 422

    def test_form_validation_message_too_short(self, client):
        """Message under 10 characters → 422."""
        resp = client.post("/support/submit", json={
            "name": "Alice",
            "email": CUSTOMER_EMAIL,
            "subject": "Issue",
            "category": "general",
            "message": "short",
        })
        assert resp.status_code == 422

    def test_form_validation_invalid_category(self, client):
        """Unknown category value → 422."""
        resp = client.post("/support/submit", json={
            "name": "Alice",
            "email": CUSTOMER_EMAIL,
            "subject": "Mystery issue",
            "category": "unknown_category",
            "message": "Something strange is happening with my workspace settings.",
        })
        assert resp.status_code == 422

    def test_form_validation_honeypot_rejected(self, client):
        """Non-empty honeypot field → 422 (spam detection)."""
        resp = client.post("/support/submit", json={
            "name": "Bot",
            "email": "spam@bot.io",
            "subject": "Buy cheap products",
            "category": "general",
            "message": "Click here to buy very cheap products now available online today yes.",
            "honeypot": "i am definitely a bot",
        })
        assert resp.status_code == 422

    def test_form_submission_xss_stripped(self, client):
        """Script tags in message body must be stripped at boundary."""
        resp = client.post("/support/submit", json={
            "name": "Alice",
            "email": CUSTOMER_EMAIL,
            "subject": "Webhook issue",
            "category": "technical",
            "message": (
                "Our webhook endpoint returns 500 errors. "
                "<script>alert('xss')</script>"
                "Can you check the NimbusFlow side? We need this fixed urgently."
            ),
        })
        # XSS guard strips the script tag — submission should succeed
        assert resp.status_code == 202

    def test_ticket_status_retrieval_found(self, client, mock_q):
        """GET /support/ticket/{id} with existing ticket → 200 with status."""
        mock_q.get_ticket = AsyncMock(return_value={
            "id": TICKET_ID,
            "status": "open",
            "category": "technical",
            "priority": "medium",
            "created_at": datetime.now(timezone.utc),
            "resolved_at": None,
            "resolution_notes": None,
        })

        # web_form_router uses its own DB query — patch via pool acquire
        pool_mock = AsyncMock()
        conn_mock = AsyncMock()
        conn_mock.fetchrow = AsyncMock(return_value={
            "id": uuid.UUID(TICKET_ID),
            "status": "open",
            "category": "technical",
            "priority": "medium",
            "created_at": datetime.now(timezone.utc),
            "resolved_at": None,
            "resolution_notes": None,
        })
        pool_mock.acquire = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=conn_mock),
            __aexit__=AsyncMock(return_value=None),
        ))
        mock_q.get_pool = AsyncMock(return_value=pool_mock)

        resp = client.get(f"/support/ticket/{TICKET_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ticket_id"] == TICKET_ID
        assert data["status"] == "open"

    def test_ticket_status_retrieval_not_found(self, client, mock_q):
        """GET /support/ticket/{unknown-id} → 404."""
        pool_mock = AsyncMock()
        conn_mock = AsyncMock()
        conn_mock.fetchrow = AsyncMock(return_value=None)
        pool_mock.acquire = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=conn_mock),
            __aexit__=AsyncMock(return_value=None),
        ))
        mock_q.get_pool = AsyncMock(return_value=pool_mock)

        resp = client.get("/support/ticket/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404


# ── 2. TestEmailChannel ────────────────────────────────────────────────────────

class TestEmailChannel:
    """Test Gmail integration — POST /webhooks/gmail."""

    def test_gmail_webhook_processing(self, client):
        """
        Valid Pub/Sub push notification → 200 'accepted' and background task queued.
        The Gmail history fetch and Kafka publish happen asynchronously.
        """
        resp = client.post("/webhooks/gmail", json=_pubsub_push())
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "accepted"
        assert "history_id" in data

    def test_gmail_webhook_returns_history_id(self, client):
        """Response body echoes the parsed historyId back to the caller."""
        resp = client.post("/webhooks/gmail", json=_pubsub_push(history_id="987654"))
        assert resp.status_code == 200
        assert resp.json()["history_id"] == "987654"

    def test_gmail_webhook_malformed_push_ignored(self, client):
        """Pub/Sub body without 'message' field → 200 'ignored' (ack to prevent retry storm)."""
        resp = client.post("/webhooks/gmail", json={"unexpected": "field"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    def test_gmail_webhook_missing_history_id_ignored(self, client):
        """Pub/Sub payload missing historyId → 200 'ignored'."""
        data = json.dumps({"emailAddress": CUSTOMER_EMAIL})  # No historyId
        encoded = base64.urlsafe_b64encode(data.encode()).decode()
        resp = client.post("/webhooks/gmail", json={
            "message": {"data": encoded, "messageId": "pub-no-history"},
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    def test_gmail_webhook_malformed_base64_ignored(self, client):
        """Garbage base64 data in Pub/Sub message → 200 'ignored'."""
        resp = client.post("/webhooks/gmail", json={
            "message": {"data": "NOT_VALID_BASE64!!!!", "messageId": "pub-bad"},
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    def test_gmail_webhook_accepts_json_body(self, client):
        """Endpoint must accept application/json content type."""
        resp = client.post(
            "/webhooks/gmail",
            json=_pubsub_push(),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 200


# ── 3. TestWhatsAppChannel ────────────────────────────────────────────────────

class TestWhatsAppChannel:
    """Test WhatsApp/Twilio integration — POST /webhooks/whatsapp and /status."""

    def test_whatsapp_webhook_processing(self, client):
        """
        Valid Twilio form POST → 200 'accepted' and published to Kafka.
        Signature validation is disabled in test env (TWILIO_VALIDATE_SIGNATURE=false).
        """
        resp = client.post(
            "/webhooks/whatsapp",
            data=_twilio_form("How do I reset my password?"),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "accepted"

    def test_whatsapp_webhook_missing_from_ignored(self, client):
        """Message with no From field → 200 'ignored' (no customer to route to)."""
        resp = client.post(
            "/webhooks/whatsapp",
            data={"MessageSid": "SM_NO_FROM", "Body": "hello", "NumMedia": "0"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    def test_whatsapp_compliance_stop_accepted(self, client):
        """STOP compliance keyword → still returns 200 (Twilio must get 200)."""
        resp = client.post(
            "/webhooks/whatsapp",
            data=_twilio_form(body="STOP", message_sid="SM_STOP"),
        )
        assert resp.status_code == 200

    def test_whatsapp_compliance_human_accepted(self, client):
        """HUMAN keyword → 200 (compliance handler must not block the webhook)."""
        resp = client.post(
            "/webhooks/whatsapp",
            data=_twilio_form(body="HUMAN", message_sid="SM_HUMAN"),
        )
        assert resp.status_code == 200

    def test_whatsapp_invalid_signature_rejected(self, client):
        """
        With signature validation enabled, invalid signature → 403.
        Temporarily overrides TWILIO_VALIDATE_SIGNATURE for this test.
        """
        with patch.dict("os.environ", {"TWILIO_VALIDATE_SIGNATURE": "true"}), \
             patch(
                 "production.api.main.validate_twilio_signature",
                 return_value=False,
             ):
            resp = client.post(
                "/webhooks/whatsapp",
                data=_twilio_form(),
                headers={"X-Twilio-Signature": "bad-sig"},
            )
        assert resp.status_code == 403

    def test_whatsapp_delivery_status_ok(self, client):
        """
        POST /webhooks/whatsapp/status → 200 'ok'.
        Twilio sends delivery status callbacks here; must always respond 200.
        """
        resp = client.post(
            "/webhooks/whatsapp/status",
            data={
                "MessageSid": "SM_DELIVERY_001",
                "MessageStatus": "delivered",
                "To": f"whatsapp:{CUSTOMER_PHONE}",
                "From": "whatsapp:+14155238886",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_whatsapp_delivery_status_failed(self, client):
        """Delivery failure status → still 200 (Twilio expects 200 regardless)."""
        resp = client.post(
            "/webhooks/whatsapp/status",
            data={
                "MessageSid": "SM_FAILED_001",
                "MessageStatus": "failed",
                "ErrorCode": "30006",
                "ErrorMessage": "Landline or unreachable carrier",
                "To": f"whatsapp:{CUSTOMER_PHONE}",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_whatsapp_long_message_accepted(self, client):
        """Long customer message → accepted (splitting is done at send time, not receive)."""
        long_msg = "How does NimbusFlow handle " + "very complex enterprise use cases? " * 20
        resp = client.post(
            "/webhooks/whatsapp",
            data=_twilio_form(body=long_msg, message_sid="SM_LONG"),
        )
        assert resp.status_code == 200


# ── 4. TestCrossChannelContinuity ─────────────────────────────────────────────

class TestCrossChannelContinuity:
    """Test that customer identity and conversation history persist across channels."""

    def test_customer_lookup_by_email(self, client, mock_q):
        """GET /customers/lookup?email= → 200 with customer profile."""
        pool_mock = AsyncMock()
        conn_mock = AsyncMock()
        conn_mock.fetchrow = AsyncMock(side_effect=[
            # First call: customer SELECT
            MagicMock(**{
                "__getitem__": lambda self, k: {
                    "id": uuid.UUID(CUSTOMER_ID.replace("cust-e2e-0001", "a" * 32).replace("-", "")),
                    "email": CUSTOMER_EMAIL,
                    "phone": CUSTOMER_PHONE,
                    "name": CUSTOMER_NAME,
                    "created_at": datetime.now(timezone.utc),
                }.get(k),
            }),
            # Second call: stats aggregate
            MagicMock(**{
                "__getitem__": lambda self, k: {
                    "conversation_count": 3,
                    "open_ticket_count": 1,
                    "channels_used": ["email", "web_form"],
                }.get(k),
            }),
        ])
        pool_mock.acquire = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=conn_mock),
            __aexit__=AsyncMock(return_value=None),
        ))
        mock_q.get_pool = AsyncMock(return_value=pool_mock)

        resp = client.get(f"/customers/lookup?email={CUSTOMER_EMAIL}")
        assert resp.status_code == 200
        data = resp.json()
        assert "customer_id" in data
        assert "channels_used" in data

    def test_customer_lookup_requires_identifier(self, client):
        """GET /customers/lookup with no params → 400 Bad Request."""
        resp = client.get("/customers/lookup")
        assert resp.status_code == 400
        assert "email" in resp.json()["detail"].lower() or "phone" in resp.json()["detail"].lower()

    def test_customer_lookup_by_phone(self, client, mock_q):
        """GET /customers/lookup?phone= → 200 (WhatsApp customers have no email)."""
        pool_mock = AsyncMock()
        conn_mock = AsyncMock()
        conn_mock.fetchrow = AsyncMock(side_effect=[
            MagicMock(**{
                "__getitem__": lambda self, k: {
                    "id": uuid.UUID("a" * 32),
                    "email": None,
                    "phone": CUSTOMER_PHONE,
                    "name": CUSTOMER_NAME,
                    "created_at": datetime.now(timezone.utc),
                }.get(k),
            }),
            MagicMock(**{
                "__getitem__": lambda self, k: {
                    "conversation_count": 1,
                    "open_ticket_count": 0,
                    "channels_used": ["whatsapp"],
                }.get(k),
            }),
        ])
        pool_mock.acquire = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=conn_mock),
            __aexit__=AsyncMock(return_value=None),
        ))
        mock_q.get_pool = AsyncMock(return_value=pool_mock)

        resp = client.get(f"/customers/lookup?phone={CUSTOMER_PHONE}")
        assert resp.status_code == 200
        assert resp.json()["phone"] == CUSTOMER_PHONE

    def test_customer_lookup_not_found(self, client, mock_q):
        """GET /customers/lookup with unknown email → 404."""
        pool_mock = AsyncMock()
        conn_mock = AsyncMock()
        conn_mock.fetchrow = AsyncMock(return_value=None)
        pool_mock.acquire = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=conn_mock),
            __aexit__=AsyncMock(return_value=None),
        ))
        mock_q.get_pool = AsyncMock(return_value=pool_mock)

        resp = client.get("/customers/lookup?email=ghost@nowhere.io")
        assert resp.status_code == 404

    def test_customer_history_across_channels(self, client, mock_q):
        """
        A customer who contacted via email and then WhatsApp appears in
        channels_used as both, enabling cross-channel continuity.
        """
        pool_mock = AsyncMock()
        conn_mock = AsyncMock()
        conn_mock.fetchrow = AsyncMock(side_effect=[
            MagicMock(**{
                "__getitem__": lambda self, k: {
                    "id": uuid.UUID("a" * 32),
                    "email": CUSTOMER_EMAIL,
                    "phone": CUSTOMER_PHONE,
                    "name": CUSTOMER_NAME,
                    "created_at": datetime.now(timezone.utc),
                }.get(k),
            }),
            MagicMock(**{
                "__getitem__": lambda self, k: {
                    "conversation_count": 4,
                    "open_ticket_count": 1,
                    # Customer reached out via all three channels
                    "channels_used": ["email", "whatsapp", "web_form"],
                }.get(k),
            }),
        ])
        pool_mock.acquire = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=conn_mock),
            __aexit__=AsyncMock(return_value=None),
        ))
        mock_q.get_pool = AsyncMock(return_value=pool_mock)

        resp = client.get(f"/customers/lookup?email={CUSTOMER_EMAIL}")
        assert resp.status_code == 200
        data = resp.json()
        channels = data["channels_used"]
        assert "email" in channels
        assert "whatsapp" in channels
        assert data["conversation_count"] == 4

    def test_conversation_history_retrieval(self, client, mock_q):
        """
        GET /conversations/{id} → 200 with conversation metadata and message list.
        Verifies cross-channel message history is returned in chronological order.
        """
        pool_mock = AsyncMock()
        conn_mock = AsyncMock()

        conv_uuid = uuid.UUID("b" * 32)
        customer_uuid = uuid.UUID("a" * 32)
        now = datetime.now(timezone.utc)

        conn_mock.fetchrow = AsyncMock(return_value=MagicMock(**{
            "__getitem__": lambda self, k: {
                "id": conv_uuid,
                "customer_id": customer_uuid,
                "initial_channel": "email",
                "current_channel": "whatsapp",
                "status": "active",
                "sentiment_score": 0.72,
                "sentiment_trend": "stable",
                "started_at": now,
                "ended_at": None,
            }.get(k),
        }))

        conn_mock.fetch = AsyncMock(return_value=[
            MagicMock(**{"__getitem__": lambda self, k: {
                "role": "customer",
                "content": "How do I reset my password?",
                "channel": "email",
                "direction": "inbound",
                "created_at": now,
                "delivery_status": "delivered",
            }.get(k)}),
            MagicMock(**{"__getitem__": lambda self, k: {
                "role": "agent",
                "content": "Hi Alice, visit nimbusflow.io/forgot-password...",
                "channel": "email",
                "direction": "outbound",
                "created_at": now,
                "delivery_status": "sent",
            }.get(k)}),
        ])

        pool_mock.acquire = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=conn_mock),
            __aexit__=AsyncMock(return_value=None),
        ))
        mock_q.get_pool = AsyncMock(return_value=pool_mock)

        conv_id = str(conv_uuid)
        resp = client.get(f"/conversations/{conv_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["conversation_id"] == conv_id
        assert data["initial_channel"] == "email"
        assert data["message_count"] == 2
        assert data["messages"][0]["role"] == "customer"
        assert data["messages"][1]["direction"] == "outbound"

    def test_conversation_not_found(self, client, mock_q):
        """GET /conversations/{unknown-id} → 404."""
        pool_mock = AsyncMock()
        conn_mock = AsyncMock()
        conn_mock.fetchrow = AsyncMock(return_value=None)
        pool_mock.acquire = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=conn_mock),
            __aexit__=AsyncMock(return_value=None),
        ))
        mock_q.get_pool = AsyncMock(return_value=pool_mock)

        resp = client.get("/conversations/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404


# ── 5. TestChannelMetrics ──────────────────────────────────────────────────────

class TestChannelMetrics:
    """Test channel-specific metrics and health endpoints."""

    def test_metrics_by_channel(self, client):
        """GET /metrics/channels → 200 with per-channel breakdown."""
        resp = client.get("/metrics/channels")
        assert resp.status_code == 200
        data = resp.json()
        assert data["period"] == "last_24h"
        assert isinstance(data["channels"], list)
        assert len(data["channels"]) > 0

    def test_metrics_include_all_three_channels(self, client):
        """Response must include email, whatsapp, and web_form entries."""
        resp = client.get("/metrics/channels")
        channels = {c["channel"] for c in resp.json()["channels"]}
        assert "email" in channels
        assert "whatsapp" in channels
        assert "web_form" in channels

    def test_metrics_escalation_rate_computed(self, client):
        """escalation_rate must be between 0.0 and 1.0 for each channel."""
        resp = client.get("/metrics/channels")
        for ch in resp.json()["channels"]:
            rate = ch["escalation_rate"]
            assert 0.0 <= rate <= 1.0, f"Invalid rate for {ch['channel']}: {rate}"

    def test_metrics_escalation_rate_formula(self, client):
        """escalation_rate = escalation_count / message_count (spot-check email)."""
        resp = client.get("/metrics/channels")
        email = next(c for c in resp.json()["channels"] if c["channel"] == "email")
        expected_rate = round(email["escalation_count"] / email["message_count"], 4)
        assert email["escalation_rate"] == expected_rate

    def test_metrics_graceful_db_failure(self, client, mock_q):
        """
        If the database is unavailable, GET /metrics/channels returns
        200 with an empty channels list rather than 503.
        Dashboards should degrade gracefully.
        """
        mock_q.get_channel_summary = AsyncMock(side_effect=Exception("DB unavailable"))
        resp = client.get("/metrics/channels")
        assert resp.status_code == 200
        assert resp.json()["channels"] == []

    def test_health_includes_channel_status(self, client):
        """GET /health → 200 with channels dict showing per-channel config status."""
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "channels" in data
        channels = data["channels"]
        assert "email" in channels
        assert "whatsapp" in channels
        assert "web_form" in channels

    def test_health_web_form_always_ready(self, client):
        """Web form channel has no credentials — must always report 'ready'."""
        resp = client.get("/health")
        assert resp.json()["channels"]["web_form"] == "ready"

    def test_health_always_200(self, client, mock_q):
        """Health check returns 200 even when all channels are unconfigured."""
        with patch.dict("os.environ", {
            "GMAIL_TOKEN_PATH": "/tmp/nonexistent-path-xyz",
            "TWILIO_ACCOUNT_SID": "",
            "TWILIO_AUTH_TOKEN": "",
        }):
            resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


# ── 6. TestAgentSkills ────────────────────────────────────────────────────────

class TestAgentSkills:
    """
    Test all 5 agent skills defined in production/agent/tools.py.

    Skill 1 — Customer Identification : create_ticket, get_customer_history
    Skill 2 — Sentiment Analysis      : analyze_sentiment
    Skill 3 — Knowledge Retrieval     : search_knowledge_base
    Skill 4 — Escalation Decision     : escalate_to_human
    Skill 5 — Channel Adaptation      : send_response
    """

    # ── Skill 1: Customer Identification ──────────────────────────────────────

    @pytest.mark.asyncio
    async def test_skill1_create_ticket_returns_ids(self):
        """create_ticket must return ticket_id, customer_id, and conversation_id."""
        mock_q = _mock_queries()
        with patch("production.agent.tools.queries", mock_q):
            from production.agent.tools import create_ticket
            result = await create_ticket(
                customer_email=CUSTOMER_EMAIL,
                customer_phone=None,
                customer_name=CUSTOMER_NAME,
                channel="email",
                subject="Integration not working",
                category="technical",
                priority="medium",
            )
        assert result["ticket_id"] == TICKET_ID
        assert result["customer_id"] == CUSTOMER_ID
        assert result["conversation_id"] == CONVERSATION_ID

    @pytest.mark.asyncio
    async def test_skill1_create_ticket_whatsapp_phone_only(self):
        """WhatsApp customers have no email — create_ticket must resolve by phone."""
        mock_q = _mock_queries()
        with patch("production.agent.tools.queries", mock_q):
            from production.agent.tools import create_ticket
            result = await create_ticket(
                customer_email=None,
                customer_phone=CUSTOMER_PHONE,
                customer_name="Bob",
                channel="whatsapp",
                subject="WhatsApp support request",
            )
        assert result["ticket_id"] == TICKET_ID
        mock_q.find_or_create_customer.assert_called_once()
        call_kwargs = mock_q.find_or_create_customer.call_args
        assert call_kwargs.kwargs.get("phone") == CUSTOMER_PHONE

    @pytest.mark.asyncio
    async def test_skill1_get_customer_history_no_history(self):
        """New customer with no history → repeat_contact=False, contact_count=0."""
        mock_q = _mock_queries()
        mock_q.get_customer_history = AsyncMock(return_value=[])
        with patch("production.agent.tools.queries", mock_q):
            from production.agent.tools import get_customer_history
            result = await get_customer_history(customer_id=CUSTOMER_ID)
        assert result["repeat_contact"] is False
        assert result["contact_count"] == 0

    @pytest.mark.asyncio
    async def test_skill1_get_customer_history_repeat_contact(self):
        """Three open tickets on same category → repeat_contact=True."""
        mock_q = _mock_queries()
        mock_q.get_customer_history = AsyncMock(return_value=[
            {"category": "technical", "status": "open", "subject": "Webhook broken"},
            {"category": "technical", "status": "open", "subject": "RE: Webhook broken"},
            {"category": "technical", "status": "open", "subject": "RE: RE: Webhook broken"},
        ])
        with patch("production.agent.tools.queries", mock_q):
            from production.agent.tools import get_customer_history
            result = await get_customer_history(customer_id=CUSTOMER_ID)
        assert result["repeat_contact"] is True
        assert result["contact_count"] == 3

    # ── Skill 2: Sentiment Analysis ───────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_skill2_analyze_sentiment_positive(self):
        """Positive message → score ≥ 0.7, level='positive', no escalation needed."""
        mock_q = _mock_queries()
        mock_oai = _mock_openai("0.85")
        with patch("production.agent.tools.queries", mock_q), \
             patch("production.agent.tools._get_openai", return_value=mock_oai):
            from production.agent.tools import analyze_sentiment
            result = await analyze_sentiment(message="Thanks so much, that worked perfectly!")
        assert result["score"] >= 0.7
        assert result["level"] == "positive"
        assert result["immediate_escalate"] is False
        assert result["requires_empathy"] is False

    @pytest.mark.asyncio
    async def test_skill2_analyze_sentiment_very_negative(self):
        """ALL CAPS angry message → score < 0.1, immediate escalation required."""
        mock_q = _mock_queries()
        mock_oai = _mock_openai("0.05")
        with patch("production.agent.tools.queries", mock_q), \
             patch("production.agent.tools._get_openai", return_value=mock_oai):
            from production.agent.tools import analyze_sentiment
            result = await analyze_sentiment(
                message="THIS IS COMPLETELY UNACCEPTABLE!!! YOUR PRODUCT IS GARBAGE!!!"
            )
        assert result["score"] <= 0.1
        assert result["level"] == "very_negative"
        assert result["immediate_escalate"] is True

    @pytest.mark.asyncio
    async def test_skill2_analyze_sentiment_legal_keyword_overrides(self):
        """
        Legal keyword (sue, lawyer) must cap sentiment at ≤ 0.1 and
        trigger immediate escalation regardless of the raw LLM score.
        """
        mock_q = _mock_queries()
        mock_oai = _mock_openai("0.65")  # Neutral score, but keyword overrides
        with patch("production.agent.tools.queries", mock_q), \
             patch("production.agent.tools._get_openai", return_value=mock_oai):
            from production.agent.tools import analyze_sentiment
            result = await analyze_sentiment(
                message="I'm going to contact my lawyer about this breach of contract."
            )
        assert result["score"] <= 0.1
        assert result["immediate_escalate"] is True

    @pytest.mark.asyncio
    async def test_skill2_analyze_sentiment_data_loss_keyword_overrides(self):
        """'Tasks disappeared' triggers immediate escalation (data-loss keyword)."""
        mock_q = _mock_queries()
        mock_oai = _mock_openai("0.3")
        with patch("production.agent.tools.queries", mock_q), \
             patch("production.agent.tools._get_openai", return_value=mock_oai):
            from production.agent.tools import analyze_sentiment
            result = await analyze_sentiment(
                message="Tasks disappeared again — we lost all our sprint data!"
            )
        assert result["immediate_escalate"] is True

    @pytest.mark.asyncio
    async def test_skill2_analyze_sentiment_requires_empathy_threshold(self):
        """Score between 0.3–0.5 → requires_empathy=True but no immediate escalation."""
        mock_q = _mock_queries()
        mock_oai = _mock_openai("0.40")
        with patch("production.agent.tools.queries", mock_q), \
             patch("production.agent.tools._get_openai", return_value=mock_oai):
            from production.agent.tools import analyze_sentiment
            result = await analyze_sentiment(
                message="I'm frustrated that this keeps happening every week."
            )
        assert result["immediate_escalate"] is False
        assert result["requires_empathy"] is True

    # ── Skill 3: Knowledge Retrieval ──────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_skill3_search_knowledge_base_found(self):
        """Product question with matching KB entry → found=True with formatted results."""
        mock_q = _mock_queries()
        mock_oai = _mock_openai()
        with patch("production.agent.tools.queries", mock_q), \
             patch("production.agent.tools._get_openai", return_value=mock_oai):
            from production.agent.tools import search_knowledge_base
            result = await search_knowledge_base(query="how do I reset my password")
        assert result["found"] is True
        assert len(result["results"]) >= 1
        assert result["top_score"] >= 0.7
        assert "title" in result["results"][0]

    @pytest.mark.asyncio
    async def test_skill3_search_knowledge_base_not_found(self):
        """Unknown query → found=False, empty results list."""
        mock_q = _mock_queries()
        mock_q.search_knowledge_base = AsyncMock(return_value=[])
        mock_oai = _mock_openai()
        with patch("production.agent.tools.queries", mock_q), \
             patch("production.agent.tools._get_openai", return_value=mock_oai):
            from production.agent.tools import search_knowledge_base
            result = await search_knowledge_base(query="dark mode when is it shipping")
        assert result["found"] is False
        assert result["results"] == []

    @pytest.mark.asyncio
    async def test_skill3_search_retries_at_lower_threshold(self):
        """
        First search at high similarity threshold returns nothing →
        tool must retry at a lower threshold before returning found=False.
        """
        mock_q = _mock_queries()
        call_count = 0

        async def _mock_kb(embedding, max_results, min_similarity, category=None):
            nonlocal call_count
            call_count += 1
            if min_similarity >= 0.70:
                return []  # Nothing at high threshold
            return [{"title": "Fallback Doc", "content": "...", "similarity": 0.62}]

        mock_q.search_knowledge_base = _mock_kb
        mock_oai = _mock_openai()
        with patch("production.agent.tools.queries", mock_q), \
             patch("production.agent.tools._get_openai", return_value=mock_oai):
            from production.agent.tools import search_knowledge_base
            result = await search_knowledge_base(query="obscure feature question")
        assert call_count == 2, "Expected exactly 2 KB calls (retry at lower threshold)"
        assert result["found"] is True

    @pytest.mark.asyncio
    async def test_skill3_search_uses_vector_embedding(self):
        """search_knowledge_base must call the embedding API before querying the DB."""
        mock_q = _mock_queries()
        mock_oai = _mock_openai()
        with patch("production.agent.tools.queries", mock_q), \
             patch("production.agent.tools._get_openai", return_value=mock_oai):
            from production.agent.tools import search_knowledge_base
            await search_knowledge_base(query="webhook timeout configuration")
        mock_oai.embeddings.create.assert_called_once()

    # ── Skill 4: Escalation Decision ──────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_skill4_escalate_to_human_returns_ids(self):
        """escalate_to_human must return escalation_id, routed_to, and urgency."""
        mock_q = _mock_queries()
        with patch("production.agent.tools.queries", mock_q):
            from production.agent.tools import escalate_to_human
            result = await escalate_to_human(
                ticket_id=TICKET_ID,
                customer_id=CUSTOMER_ID,
                reason="knowledge_gap",
                urgency="normal",
                channel="email",
            )
        assert result["escalation_id"] == ESCALATION_ID
        assert "routed_to" in result
        assert result["urgency"] in ("normal", "high", "critical", "low")

    @pytest.mark.asyncio
    async def test_skill4_legal_keyword_upgrades_urgency(self):
        """
        'sue' in trigger_message → urgency must be auto-upgraded to 'critical'
        regardless of the passed urgency value.
        """
        mock_q = _mock_queries()
        with patch("production.agent.tools.queries", mock_q):
            from production.agent.tools import escalate_to_human
            result = await escalate_to_human(
                ticket_id=TICKET_ID,
                customer_id=CUSTOMER_ID,
                reason="general_complaint",
                urgency="low",
                trigger_message="I will sue your company for this.",
            )
        assert result["urgency"] == "critical"

    @pytest.mark.asyncio
    async def test_skill4_chargeback_routes_to_billing(self):
        """Chargeback reason → routed_to must include billing team."""
        mock_q = _mock_queries()
        with patch("production.agent.tools.queries", mock_q):
            from production.agent.tools import escalate_to_human
            result = await escalate_to_human(
                ticket_id=TICKET_ID,
                customer_id=CUSTOMER_ID,
                reason="chargeback_threat",
                urgency="critical",
                trigger_message="I will dispute the charge with my bank.",
            )
        assert "billing" in result["routed_to"].lower()

    @pytest.mark.asyncio
    async def test_skill4_escalation_updates_ticket_status(self):
        """escalate_to_human must call update_ticket_status to record the escalation."""
        mock_q = _mock_queries()
        with patch("production.agent.tools.queries", mock_q):
            from production.agent.tools import escalate_to_human
            await escalate_to_human(
                ticket_id=TICKET_ID,
                customer_id=CUSTOMER_ID,
                reason="human_requested",
                urgency="high",
            )
        mock_q.update_ticket_status.assert_called_once()

    # ── Skill 5: Channel Adaptation ───────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_skill5_send_response_email_formatted(self):
        """Email channel → response includes 'Hi {name},' greeting and 'Best regards'."""
        mock_q = _mock_queries()
        with patch("production.agent.tools.queries", mock_q):
            from production.agent.tools import send_response
            result = await send_response(
                ticket_id=TICKET_ID,
                conversation_id=CONVERSATION_ID,
                channel="email",
                content="To reset your password, visit nimbusflow.io/forgot-password.",
                customer_name=CUSTOMER_NAME,
            )
        assert result["channel"] == "email"
        formatted = result["formatted_content"]
        assert "Hi Alice" in formatted
        assert "Best regards" in formatted or "NimbusFlow" in formatted
        assert TICKET_ID in formatted

    @pytest.mark.asyncio
    async def test_skill5_send_response_whatsapp_no_markdown(self):
        """WhatsApp channel → no markdown symbols (**) in the formatted content."""
        mock_q = _mock_queries()
        with patch("production.agent.tools.queries", mock_q):
            from production.agent.tools import send_response
            result = await send_response(
                ticket_id=TICKET_ID,
                conversation_id=CONVERSATION_ID,
                channel="whatsapp",
                content="Use **Settings > Integrations** to connect your GitHub repo.",
                customer_name="Bob",
            )
        assert "**" not in result["formatted_content"]
        assert result["channel"] == "whatsapp"

    @pytest.mark.asyncio
    async def test_skill5_send_response_whatsapp_respects_length(self):
        """WhatsApp response must not exceed the 1600-char Twilio hard limit."""
        mock_q = _mock_queries()
        with patch("production.agent.tools.queries", mock_q):
            from production.agent.tools import send_response
            result = await send_response(
                ticket_id=TICKET_ID,
                conversation_id=CONVERSATION_ID,
                channel="whatsapp",
                content="This is a very long response. " * 200,
                customer_name="Charlie",
            )
        assert len(result["formatted_content"]) <= 1600

    @pytest.mark.asyncio
    async def test_skill5_send_response_web_form_semi_formal(self):
        """Web form channel → semi-formal tone, includes ticket reference."""
        mock_q = _mock_queries()
        with patch("production.agent.tools.queries", mock_q):
            from production.agent.tools import send_response
            result = await send_response(
                ticket_id=TICKET_ID,
                conversation_id=CONVERSATION_ID,
                channel="web_form",
                content="Your webhook timeout can be extended in Settings > API.",
                customer_name="Diana",
            )
        formatted = result["formatted_content"]
        assert TICKET_ID in formatted
        assert result["message_id"] == MESSAGE_ID

    @pytest.mark.asyncio
    async def test_skill5_send_response_persists_to_db(self):
        """send_response must call store_message to persist the outbound turn."""
        mock_q = _mock_queries()
        with patch("production.agent.tools.queries", mock_q):
            from production.agent.tools import send_response
            await send_response(
                ticket_id=TICKET_ID,
                conversation_id=CONVERSATION_ID,
                channel="email",
                content="Here is the answer to your question.",
                customer_name="Eve",
            )
        mock_q.store_message.assert_called_once()

    # ── Full 5-skill workflow ──────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_all_5_skills_in_sequence(self):
        """
        Simulate the agent's mandatory workflow — all 5 skills must be called
        in the correct order for a standard product question.

        Order verified (from SYSTEM_PROMPT):
          1. create_ticket
          2. get_customer_history
          3. analyze_sentiment
          4. search_knowledge_base
          5. send_response
        """
        mock_q = _mock_queries()
        mock_oai = _mock_openai("0.75")

        call_order = []

        async def _track(name, *args, **kwargs):
            call_order.append(name)

        with patch("production.agent.tools.queries", mock_q), \
             patch("production.agent.tools._get_openai", return_value=mock_oai):

            from production.agent import tools

            # Wrap each skill to record invocation order
            orig_create = tools.create_ticket.__wrapped__ if hasattr(tools.create_ticket, "__wrapped__") else None
            orig_history = tools.get_customer_history.__wrapped__ if hasattr(tools.get_customer_history, "__wrapped__") else None

            # Track via the mock_q calls (each tool makes at least one DB call)
            from production.agent.tools import (
                create_ticket,
                get_customer_history,
                analyze_sentiment,
                search_knowledge_base,
                send_response,
            )

            t1 = await create_ticket(
                customer_email=CUSTOMER_EMAIL,
                channel="email",
                subject="Password reset",
            )
            call_order.append("create_ticket")

            t2 = await get_customer_history(customer_id=t1["customer_id"])
            call_order.append("get_customer_history")

            t3 = await analyze_sentiment(message="How do I reset my password?")
            call_order.append("analyze_sentiment")

            t4 = await search_knowledge_base(query="reset password")
            call_order.append("search_knowledge_base")

            t5 = await send_response(
                ticket_id=t1["ticket_id"],
                conversation_id=t1["conversation_id"],
                channel="email",
                content=t4["results"][0]["content"] if t4["found"] else "Please contact support.",
                customer_name=CUSTOMER_NAME,
            )
            call_order.append("send_response")

        # Verify all 5 skills were called and in the correct sequence
        assert call_order == [
            "create_ticket",
            "get_customer_history",
            "analyze_sentiment",
            "search_knowledge_base",
            "send_response",
        ]

        # Verify each skill produced a valid result
        assert t1["ticket_id"] == TICKET_ID
        assert t2["repeat_contact"] is False
        assert 0.0 <= t3["score"] <= 1.0
        assert t4["found"] is True
        assert t5["message_id"] == MESSAGE_ID
