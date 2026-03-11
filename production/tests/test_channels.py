"""
production/tests/test_channels.py
Unit tests for all three channel handlers.

Tests cover:
  - Gmail: Pub/Sub push parsing, body extraction, message normalization
  - WhatsApp: Twilio webhook parsing, compliance triggers, length limits
  - Web Form: validation, XSS stripping, honeypot, priority detection

Run:
    pytest production/tests/test_channels.py -v
"""

import base64
import json

import pytest
from pydantic import ValidationError

from production.channels.gmail_handler import parse_pubsub_push, _extract_body
from production.channels.whatsapp_handler import (
    parse_twilio_webhook,
    TWILIO_COMPLIANCE_KEYWORDS,
)
from production.channels.web_form_handler import parse_web_form, WebFormSubmission


# ── Gmail handler tests ───────────────────────────────────────────────────────

class TestGmailHandler:

    def _make_pubsub_push(self, history_id: str, email: str) -> dict:
        data = json.dumps({"historyId": history_id, "emailAddress": email})
        encoded = base64.urlsafe_b64encode(data.encode()).decode()
        return {"message": {"data": encoded, "messageId": "pub-123", "publishTime": "2026-03-07T10:00:00Z"}}

    def test_parse_pubsub_push_valid(self):
        body = self._make_pubsub_push("99999", "alice@corp.com")
        result = parse_pubsub_push(body)
        assert result is not None
        assert result["history_id"] == "99999"
        assert result["email_address"] == "alice@corp.com"

    def test_parse_pubsub_push_missing_data(self):
        result = parse_pubsub_push({"message": {}})
        assert result is None

    def test_parse_pubsub_push_missing_history_id(self):
        data = json.dumps({"emailAddress": "test@test.com"})  # No historyId
        encoded = base64.urlsafe_b64encode(data.encode()).decode()
        body = {"message": {"data": encoded}}
        result = parse_pubsub_push(body)
        assert result is None

    def test_parse_pubsub_push_malformed_json(self):
        encoded = base64.urlsafe_b64encode(b"NOT JSON").decode()
        body = {"message": {"data": encoded}}
        result = parse_pubsub_push(body)
        assert result is None

    def test_extract_body_plain_text(self):
        text = "Hello, this is the email body."
        encoded = base64.urlsafe_b64encode(text.encode()).decode()
        payload = {"mimeType": "text/plain", "body": {"data": encoded}, "parts": []}
        result = _extract_body(payload)
        assert result == text

    def test_extract_body_multipart(self):
        text = "Plain text part"
        encoded = base64.urlsafe_b64encode(text.encode()).decode()
        payload = {
            "mimeType": "multipart/alternative",
            "body": {},
            "parts": [
                {"mimeType": "text/plain", "body": {"data": encoded}, "parts": []},
                {"mimeType": "text/html", "body": {"data": encoded}, "parts": []},
            ],
        }
        result = _extract_body(payload)
        assert result == text

    def test_extract_body_no_content_returns_empty(self):
        payload = {"mimeType": "text/plain", "body": {}, "parts": []}
        result = _extract_body(payload)
        assert result == ""


# ── WhatsApp handler tests ────────────────────────────────────────────────────

class TestWhatsAppHandler:

    def _make_webhook(self, body: str, phone: str = "+14155551234") -> dict:
        return {
            "MessageSid": "SM123",
            "From": f"whatsapp:{phone}",
            "To": "whatsapp:+14155238886",
            "Body": body,
            "NumMedia": "0",
        }

    def test_parse_valid_message(self):
        payload = parse_twilio_webhook(self._make_webhook("how do I reset my password"))
        assert payload is not None
        assert payload["channel"] == "whatsapp"
        assert payload["from_phone"] == "+14155551234"
        assert payload["body"] == "how do I reset my password"

    def test_parse_strips_whatsapp_prefix(self):
        payload = parse_twilio_webhook(self._make_webhook("hi", "+447700900000"))
        assert payload["from_phone"] == "+447700900000"
        assert "whatsapp:" not in payload["from_phone"]

    def test_parse_empty_body(self):
        # Edge case T-046: empty message
        payload = parse_twilio_webhook(self._make_webhook(""))
        assert payload is not None
        assert payload["body"] == ""

    def test_parse_missing_from_returns_none(self):
        result = parse_twilio_webhook({"Body": "hello", "To": "whatsapp:+1"})
        assert result is None

    def test_compliance_trigger_stop(self):
        payload = parse_twilio_webhook(self._make_webhook("STOP"))
        assert payload["is_compliance_trigger"] is True

    def test_compliance_trigger_human(self):
        payload = parse_twilio_webhook(self._make_webhook("HUMAN"))
        assert payload["is_compliance_trigger"] is True

    def test_compliance_trigger_agent(self):
        payload = parse_twilio_webhook(self._make_webhook("AGENT"))
        assert payload["is_compliance_trigger"] is True

    def test_normal_message_not_compliance_trigger(self):
        payload = parse_twilio_webhook(self._make_webhook("how do I add a user"))
        assert payload["is_compliance_trigger"] is False

    def test_compliance_keywords_set_contents(self):
        assert "STOP" in TWILIO_COMPLIANCE_KEYWORDS
        assert "HUMAN" in TWILIO_COMPLIANCE_KEYWORDS
        assert "AGENT" in TWILIO_COMPLIANCE_KEYWORDS


# ── Web Form handler tests ────────────────────────────────────────────────────

class TestWebFormHandler:

    def _valid_form(self, **overrides) -> dict:
        base = {
            "email": "alice@corp.com",
            "name": "Alice",
            "subject": "GitHub integration not working",
            "message": "Our GitHub webhook stopped firing after we updated the repo settings. Error code 404.",
        }
        base.update(overrides)
        return base

    def test_valid_submission_parses(self):
        result = parse_web_form(self._valid_form())
        assert result["channel"] == "web_form"
        assert result["from_email"] == "alice@corp.com"
        assert result["from_name"] == "Alice"

    def test_invalid_email_raises(self):
        with pytest.raises(Exception):
            parse_web_form(self._valid_form(email="not-an-email"))

    def test_missing_subject_raises(self):
        data = self._valid_form()
        data.pop("subject")
        with pytest.raises(Exception):
            parse_web_form(data)

    def test_short_message_raises(self):
        with pytest.raises(Exception):
            parse_web_form(self._valid_form(message="short"))

    def test_honeypot_filled_raises(self):
        with pytest.raises(Exception):
            parse_web_form(self._valid_form(honeypot="i am a bot"))

    def test_honeypot_empty_passes(self):
        result = parse_web_form(self._valid_form(honeypot=""))
        assert result is not None

    def test_xss_stripped(self):
        xss_message = (
            "How do I do X? <script>alert('xss')</script> "
            "Also the webhook isn't working and returns 500 errors."
        )
        result = parse_web_form(self._valid_form(message=xss_message))
        assert "<script>" not in result["body"]
        assert "How do I do X?" in result["body"]

    def test_priority_default_medium(self):
        result = parse_web_form(self._valid_form())
        assert result["suggested_priority"] == "medium"

    def test_priority_bump_cicd(self):
        result = parse_web_form(
            self._valid_form(message="Our CI/CD pipeline is broken and webhooks stopped. " * 3)
        )
        assert result["suggested_priority"] == "high"

    def test_priority_bump_production(self):
        result = parse_web_form(
            self._valid_form(
                message="This is affecting our production environment and all 15 users. " * 3
            )
        )
        assert result["suggested_priority"] == "high"

    def test_priority_bump_evaluating(self):
        result = parse_web_form(
            self._valid_form(
                message="We are evaluating NimbusFlow for our 200+ employees and need SSO. " * 2
            )
        )
        assert result["suggested_priority"] == "high"

    def test_optional_name_allowed(self):
        data = self._valid_form()
        data.pop("name")
        result = parse_web_form(data)
        assert result["from_name"] == ""
