"""
production/channels/whatsapp_handler.py

WhatsApp channel handler via Twilio WhatsApp Business API — Exercise 2.2.
Implements WhatsAppHandler class with webhook validation, inbound processing,
outbound sending with message splitting, and delivery status handling.

Flow:
  WhatsApp → Twilio webhook → /webhook/whatsapp (FastAPI) → Kafka topic
  Kafka response → WhatsAppHandler.send_message() → Twilio API → WhatsApp

Setup:
  1. Create Twilio account at https://console.twilio.com
  2. Enable WhatsApp Sandbox (Messaging → Try it out → Send a WhatsApp message)
  3. Set webhook URL: https://your-domain/webhook/whatsapp (POST)
  4. Set delivery status callback: https://your-domain/webhook/whatsapp/status
  5. Set env vars: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_NUMBER

Docs: https://www.twilio.com/docs/whatsapp
      https://www.twilio.com/docs/usage/webhooks/webhooks-security
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime
from typing import Optional

import structlog
from fastapi import Request
from twilio.base.exceptions import TwilioRestException
from twilio.request_validator import RequestValidator
from twilio.rest import Client

log = structlog.get_logger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")

# WhatsApp hard limit per message (Twilio enforces this)
WHATSAPP_MAX_CHARS = 1600
# Preferred length before splitting — matches discovery-log D-004 / CHANNEL_PARAMS
WHATSAPP_PREFERRED_CHARS = 300

# Twilio compliance opt-out/opt-in keywords — must never block these
COMPLIANCE_KEYWORDS = {"STOP", "STOPALL", "UNSUBSCRIBE", "CANCEL", "END", "QUIT", "UNSTOP", "START", "HELP"}
# Keywords that require immediate escalation to a human agent
HUMAN_REQUEST_KEYWORDS = {"HUMAN", "AGENT", "REPRESENTATIVE", "PERSON", "SUPPORT"}


# ── format_response — message splitting ──────────────────────────────────────

def format_response(body: str, max_chars: int = WHATSAPP_MAX_CHARS) -> list[str]:
    """
    Split a long WhatsApp response into chunks that respect the character limit.

    Splitting strategy (in priority order):
      1. If body <= max_chars → return as single-element list.
      2. Split at sentence boundaries (". ", "! ", "? ") closest to max_chars.
      3. Fall back to word boundary (last space before max_chars).
      4. Hard-cut at max_chars if no boundary found.

    Each chunk is stripped of leading/trailing whitespace.
    Continuation marker " (cont.)" is appended when more than 2 parts result.

    Args:
        body: Full response text.
        max_chars: Maximum characters per chunk. Default: 1600 (Twilio hard limit).

    Returns:
        List of string chunks, each <= max_chars characters.

    Examples:
        >>> format_response("Hello world.", 1600)
        ['Hello world.']

        >>> format_response("A" * 900 + ". " + "B" * 900, 1600)
        ['A' * 900 + '.', 'B' * 900]
    """
    if not body:
        return [""]

    body = body.strip()

    if len(body) <= max_chars:
        return [body]

    chunks: list[str] = []
    remaining = body

    while len(remaining) > max_chars:
        window = remaining[:max_chars]

        # 1. Sentence boundary: look for ". ", "! ", "? " within the window
        split_at = -1
        for delimiter in (". ", "! ", "? "):
            pos = window.rfind(delimiter)
            if pos > split_at:
                split_at = pos + len(delimiter) - 1  # keep the punctuation

        # 2. Word boundary fallback
        if split_at <= 0:
            split_at = window.rfind(" ")

        # 3. Hard cut — no boundary found at all
        if split_at <= 0:
            split_at = max_chars - 1

        chunk = remaining[: split_at + 1].strip()
        remaining = remaining[split_at + 1 :].strip()

        if chunk:
            chunks.append(chunk)

    if remaining:
        chunks.append(remaining)

    # Append continuation marker if response needed 3+ parts
    if len(chunks) > 2:
        chunks = [
            c + " (cont.)" if i < len(chunks) - 1 else c
            for i, c in enumerate(chunks)
        ]

    return chunks


# ── WhatsAppHandler class ─────────────────────────────────────────────────────

class WhatsAppHandler:
    """
    Handles WhatsApp channel integration for the Customer Success FTE.

    Responsibilities:
    - Twilio client and RequestValidator setup
    - Webhook signature validation (X-Twilio-Signature)
    - Inbound message processing and normalization
    - Outbound message sending (single + split for long responses)
    - Delivery status webhook processing
    - Compliance keyword detection (STOP/UNSTOP/HELP)

    Usage:
        handler = WhatsAppHandler()

        # In FastAPI webhook endpoint
        is_valid = await handler.validate_webhook(request)
        form_data = dict(await request.form())
        message = await handler.process_webhook(form_data)

        # Send a reply
        result = await handler.send_message("+1234567890", "Hello!")

        # Send a long reply (auto-splits)
        results = await handler.send_split_message("+1234567890", long_text)
    """

    def __init__(
        self,
        account_sid: Optional[str] = None,
        auth_token: Optional[str] = None,
        whatsapp_number: Optional[str] = None,
    ) -> None:
        self.account_sid = account_sid or TWILIO_ACCOUNT_SID
        self.auth_token = auth_token or TWILIO_AUTH_TOKEN
        self.whatsapp_number = whatsapp_number or TWILIO_WHATSAPP_NUMBER

        if not self.whatsapp_number.startswith("whatsapp:"):
            self.whatsapp_number = f"whatsapp:{self.whatsapp_number}"

        self.client = Client(self.account_sid, self.auth_token)
        self.validator = RequestValidator(self.auth_token)

    # ── Inbound: Webhook Signature Validation ─────────────────────────────────

    async def validate_webhook(self, request: Request) -> bool:
        """
        Validate the X-Twilio-Signature header to confirm the request is from Twilio.
        Prevents spoofed or replayed webhook calls.

        Args:
            request: FastAPI Request object. Must be read before body consumption.

        Returns:
            True if signature is valid (or TWILIO_AUTH_TOKEN is unset in dev mode).
            False if signature check fails.

        Security note:
            In production, always reject requests where this returns False.
            The validator uses HMAC-SHA1 over sorted form parameters.
        """
        if not self.auth_token:
            log.warning("whatsapp.signature_validation_skipped", reason="no_auth_token")
            return True  # Fail-open in dev only

        signature = request.headers.get("X-Twilio-Signature", "")
        url = str(request.url)

        try:
            form_data = await request.form()
            params = dict(form_data)
        except Exception as exc:
            log.error("whatsapp.form_parse_failed", error=str(exc))
            return False

        is_valid = self.validator.validate(url, params, signature)

        if not is_valid:
            log.warning(
                "whatsapp.signature_invalid",
                url=url,
                signature=signature[:20] + "...",
            )

        return is_valid

    # ── Inbound: Process Webhook ──────────────────────────────────────────────

    async def process_webhook(self, form_data: dict) -> Optional[dict]:
        """
        Process an incoming WhatsApp message from a Twilio webhook POST.

        Normalizes the raw Twilio form fields into a standard channel payload
        for Kafka publishing and agent processing.

        Compliance keywords (STOP, UNSTOP, HELP, etc.) are flagged in the
        payload — the worker must handle opt-out without calling the agent.

        Human request keywords (HUMAN, AGENT, etc.) are flagged for immediate
        escalation without agent processing.

        Args:
            form_data: dict of Twilio form POST fields.

        Returns:
            Normalized message dict or None if the message should be ignored
            (e.g., delivery receipts, status callbacks, empty From field).
        """
        from_raw = form_data.get("From", "")
        customer_phone = from_raw.replace("whatsapp:", "").strip()

        if not customer_phone:
            log.warning("whatsapp.webhook_missing_from")
            return None

        message_sid = form_data.get("MessageSid", "")
        body = form_data.get("Body", "").strip()
        body_upper = body.upper()

        is_compliance = body_upper in COMPLIANCE_KEYWORDS
        is_human_request = body_upper in HUMAN_REQUEST_KEYWORDS

        if is_compliance:
            log.info(
                "whatsapp.compliance_keyword_received",
                keyword=body,
                phone=customer_phone,
            )

        payload = {
            "channel": "whatsapp",
            "channel_message_id": message_sid,
            "customer_phone": customer_phone,
            "customer_name": form_data.get("ProfileName"),
            "content": body,
            "received_at": datetime.utcnow().isoformat(),
            "is_compliance_trigger": is_compliance,
            "is_human_request": is_human_request,
            "metadata": {
                "num_media": form_data.get("NumMedia", "0"),
                "profile_name": form_data.get("ProfileName"),
                "wa_id": form_data.get("WaId"),
                "sms_status": form_data.get("SmsStatus"),
                "account_sid": form_data.get("AccountSid"),
                "media_url": form_data.get("MediaUrl0"),
                "media_content_type": form_data.get("MediaContentType0"),
            },
        }

        log.info(
            "whatsapp.message_received",
            phone=customer_phone,
            length=len(body),
            is_compliance=is_compliance,
            is_human_request=is_human_request,
        )

        return payload

    # ── Outbound: Send Message ────────────────────────────────────────────────

    async def send_message(self, to_phone: str, body: str) -> dict:
        """
        Send a single WhatsApp message via Twilio.

        Enforces the 1600-character hard limit by truncating with "..." if needed.
        For content that should be split gracefully, use send_split_message().

        Args:
            to_phone: Recipient phone number. "whatsapp:" prefix is added automatically.
            body: Message text. Hard-truncated at 1600 characters.

        Returns:
            dict:
                {
                  "channel_message_id": str,       # Twilio MessageSid
                  "delivery_status": str,           # e.g. "queued", "sent", "failed"
                  "error": str | None
                }
        """
        if not to_phone.startswith("whatsapp:"):
            to_phone = f"whatsapp:{to_phone}"

        # Hard limit enforcement
        if len(body) > WHATSAPP_MAX_CHARS:
            log.warning(
                "whatsapp.message_truncated",
                original_length=len(body),
                truncated_to=WHATSAPP_MAX_CHARS,
            )
            body = body[: WHATSAPP_MAX_CHARS - 3] + "..."

        def _create():
            return self.client.messages.create(
                body=body,
                from_=self.whatsapp_number,
                to=to_phone,
            )

        try:
            message = await asyncio.get_event_loop().run_in_executor(None, _create)
            log.info(
                "whatsapp.message_sent",
                to=to_phone,
                sid=message.sid,
                status=message.status,
                length=len(body),
            )
            return {
                "channel_message_id": message.sid,
                "delivery_status": message.status,
                "error": None,
            }
        except TwilioRestException as exc:
            log.error(
                "whatsapp.send_failed",
                to=to_phone,
                code=exc.code,
                error=str(exc.msg),
            )
            return {
                "channel_message_id": "",
                "delivery_status": "failed",
                "error": f"Twilio error {exc.code}: {exc.msg}",
            }
        except Exception as exc:
            log.error("whatsapp.send_unexpected_error", to=to_phone, error=str(exc))
            return {
                "channel_message_id": "",
                "delivery_status": "failed",
                "error": str(exc),
            }

    async def send_split_message(self, to_phone: str, body: str) -> list[dict]:
        """
        Send a long WhatsApp response, splitting it into chunks at sentence
        boundaries using format_response().

        Messages are sent sequentially (not in parallel) to preserve order.
        WhatsApp delivery order is not guaranteed in parallel sends.

        Args:
            to_phone: Recipient phone number.
            body: Full response text. May exceed 1600 characters.

        Returns:
            List of result dicts, one per chunk sent. Each has the same
            shape as send_message() return value.
        """
        chunks = format_response(body, max_chars=WHATSAPP_MAX_CHARS)

        if len(chunks) > 1:
            log.info(
                "whatsapp.splitting_message",
                total_chars=len(body),
                num_chunks=len(chunks),
                to=to_phone,
            )

        results: list[dict] = []
        for i, chunk in enumerate(chunks):
            result = await self.send_message(to_phone, chunk)
            results.append(result)

            # Small delay between parts to preserve delivery order
            if i < len(chunks) - 1:
                await asyncio.sleep(0.3)

        return results

    # ── Delivery Status ───────────────────────────────────────────────────────

    async def handle_delivery_status(self, form_data: dict) -> dict:
        """
        Process a Twilio delivery status callback.

        Twilio sends status updates to the StatusCallback URL when a message
        transitions: queued → sent → delivered (or failed/undelivered).

        Configure in Twilio Console or pass statusCallback parameter when
        creating messages.

        Args:
            form_data: dict of Twilio status callback POST fields.

        Returns:
            dict:
                {
                  "message_sid": str,
                  "status": str,           # "delivered", "failed", "undelivered", etc.
                  "to": str,
                  "error_code": str | None,
                  "error_message": str | None,
                  "timestamp": str
                }
        """
        message_sid = form_data.get("MessageSid", "")
        status = form_data.get("MessageStatus", form_data.get("SmsStatus", "unknown"))
        to_phone = form_data.get("To", "").replace("whatsapp:", "")
        error_code = form_data.get("ErrorCode")
        error_message = form_data.get("ErrorMessage")

        log.info(
            "whatsapp.delivery_status",
            sid=message_sid,
            status=status,
            to=to_phone,
            error_code=error_code,
        )

        if status in ("failed", "undelivered"):
            log.warning(
                "whatsapp.delivery_failed",
                sid=message_sid,
                to=to_phone,
                error_code=error_code,
                error_message=error_message,
            )

        return {
            "message_sid": message_sid,
            "status": status,
            "to": to_phone,
            "error_code": error_code,
            "error_message": error_message,
            "timestamp": datetime.utcnow().isoformat(),
        }


# ── Module-level convenience functions (backward compat) ─────────────────────
# Used by api/main.py and message_processor.py before class refactor.

def parse_twilio_webhook(form_data: dict) -> Optional[dict]:
    """
    Stateless parse of Twilio webhook form data.
    Returns normalized payload or None. No Twilio client needed.
    Use WhatsAppHandler.process_webhook() for full class-based flow.
    """
    from_raw = form_data.get("From", "")
    customer_phone = from_raw.replace("whatsapp:", "").strip()

    if not customer_phone:
        log.warning("whatsapp.parse_webhook_missing_from")
        return None

    body = form_data.get("Body", "").strip()
    body_upper = body.upper()

    return {
        "channel": "whatsapp",
        "channel_message_id": form_data.get("MessageSid", ""),
        "customer_phone": customer_phone,
        "customer_name": form_data.get("ProfileName"),
        "content": body,
        "received_at": datetime.utcnow().isoformat(),
        "is_compliance_trigger": body_upper in COMPLIANCE_KEYWORDS,
        "is_human_request": body_upper in HUMAN_REQUEST_KEYWORDS,
        "metadata": {
            "num_media": form_data.get("NumMedia", "0"),
            "profile_name": form_data.get("ProfileName"),
            "wa_id": form_data.get("WaId"),
            "sms_status": form_data.get("SmsStatus"),
            "media_url": form_data.get("MediaUrl0"),
        },
    }


def validate_twilio_signature(
    url: str,
    params: dict,
    signature: str,
    auth_token: str = TWILIO_AUTH_TOKEN,
) -> bool:
    """
    Stateless signature validation using Twilio RequestValidator.
    Use WhatsAppHandler.validate_webhook() for the async FastAPI version.
    """
    if not auth_token:
        log.warning("whatsapp.signature_validation_skipped", reason="no_auth_token")
        return True

    validator = RequestValidator(auth_token)
    return validator.validate(url, params, signature)
