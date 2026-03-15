"""
production/channels/gmail_handler.py

Gmail channel handler — Exercise 2.2.
Implements GmailHandler class with OAuth2, Pub/Sub push notifications,
message processing, reply threading, and retry logic.

Flow:
  Gmail inbox → Pub/Sub push → /webhook/gmail (FastAPI) → Kafka topic
  Kafka response topic → GmailHandler.send_reply() → Gmail API (thread reply)

Setup:
  1. Enable Gmail API + Cloud Pub/Sub in GCP console
  2. Create Pub/Sub topic + push subscription pointing to /webhook/gmail
  3. Grant Pub/Sub publisher role to gmail-api-push@system.gserviceaccount.com
     on your topic
  4. Set env vars: GMAIL_CREDENTIALS_PATH, GMAIL_TOKEN_PATH, GMAIL_USER_ID,
     PUBSUB_PROJECT_ID, PUBSUB_TOPIC_NAME

Docs: https://developers.google.com/gmail/api/guides/push
"""

from __future__ import annotations

import asyncio
import base64
import email.mime.multipart
import email.mime.text
import json
import os
import time
from datetime import datetime
from typing import Optional

import structlog
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

log = structlog.get_logger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
GMAIL_USER_ID = os.getenv("GMAIL_USER_ID", "me")
CREDENTIALS_PATH = os.getenv("GMAIL_CREDENTIALS_PATH", "secrets/gmail_credentials.json")
TOKEN_PATH = os.getenv("GMAIL_TOKEN_PATH", "secrets/gmail_token.json")
PUBSUB_PROJECT_ID = os.getenv("PUBSUB_PROJECT_ID", "")
PUBSUB_TOPIC_NAME = os.getenv("PUBSUB_TOPIC_NAME", "")

MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # seconds; doubles each retry


# ── GmailHandler class ────────────────────────────────────────────────────────

class GmailHandler:
    """
    Handles Gmail channel integration for the Customer Success FTE.

    Responsibilities:
    - OAuth2 credential management (load, refresh, persist)
    - Pub/Sub push notification setup (Gmail watch)
    - Inbound email processing (history list → message fetch → normalize)
    - Outbound reply sending with proper thread headers
    - Retry logic for transient Google API errors

    Usage:
        handler = GmailHandler()
        # or supply explicit paths:
        handler = GmailHandler(credentials_path="path/to/creds.json")

        # Setup push notifications (run once or on redeploy)
        result = await handler.setup_push_notifications("projects/my-proj/topics/my-topic")

        # Process incoming Pub/Sub push
        messages = await handler.process_notification(pubsub_message_dict)

        # Send a reply
        sent_id = await handler.send_reply(
            to_email="customer@corp.com",
            subject="Your Support Request",
            body="Hello ...",
            thread_id="thread-abc123"
        )
    """

    def __init__(
        self,
        credentials_path: Optional[str] = None,
        token_path: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> None:
        self.credentials_path = credentials_path or CREDENTIALS_PATH
        self.token_path = token_path or TOKEN_PATH
        self.user_id = user_id or GMAIL_USER_ID
        self._credentials: Optional[Credentials] = None
        self._service = None

    # ── Auth ──────────────────────────────────────────────────────────────────

    def _get_credentials(self) -> Credentials:
        """
        Load or refresh Gmail OAuth2 credentials.
        Persists refreshed tokens to token_path.
        Raises RuntimeError if credentials cannot be obtained.
        """
        creds: Optional[Credentials] = None

        if os.path.exists(self.token_path):
            try:
                creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
            except Exception as exc:
                log.warning("gmail.token_load_failed", path=self.token_path, error=str(exc))

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    log.info("gmail.credentials_refreshed")
                except RefreshError as exc:
                    log.error("gmail.credentials_refresh_failed", error=str(exc))
                    creds = None

            if not creds:
                if not os.path.exists(self.credentials_path):
                    raise RuntimeError(
                        f"Gmail credentials not found at {self.credentials_path}. "
                        "Download OAuth2 client credentials from Google Cloud Console."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES
                )
                creds = flow.run_local_server(port=0)
                log.info("gmail.credentials_obtained_via_oauth")

            # Persist for future runs
            try:
                os.makedirs(os.path.dirname(self.token_path) or ".", exist_ok=True)
                with open(self.token_path, "w") as token_file:
                    token_file.write(creds.to_json())
            except OSError as exc:
                log.warning("gmail.token_save_failed", error=str(exc))

        self._credentials = creds
        return creds

    def _build_service(self):
        """Build and cache an authenticated Gmail API service."""
        if self._service is None:
            creds = self._get_credentials()
            self._service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        return self._service

    # ── Pub/Sub Push Notification Setup ───────────────────────────────────────

    async def setup_push_notifications(self, topic_name: Optional[str] = None) -> dict:
        """
        Register Gmail push notifications via Cloud Pub/Sub (Gmail watch API).

        This tells Gmail to publish to the Pub/Sub topic whenever new mail
        arrives. The watch expires after ~7 days — redeploy or schedule renewal.

        Args:
            topic_name: Full Pub/Sub topic resource name.
                        Format: "projects/{project_id}/topics/{topic_name}"
                        Defaults to env PUBSUB_PROJECT_ID + PUBSUB_TOPIC_NAME.

        Returns:
            dict with historyId and expiration from Gmail watch response.

        Raises:
            RuntimeError: If topic_name is not provided and env vars are missing.
            HttpError: If Gmail API call fails after retries.
        """
        if not topic_name:
            if not PUBSUB_PROJECT_ID or not PUBSUB_TOPIC_NAME:
                raise RuntimeError(
                    "Set PUBSUB_PROJECT_ID and PUBSUB_TOPIC_NAME env vars, "
                    "or pass topic_name explicitly."
                )
            topic_name = f"projects/{PUBSUB_PROJECT_ID}/topics/{PUBSUB_TOPIC_NAME}"

        request_body = {
            "labelIds": ["INBOX"],
            "topicName": topic_name,
            "labelFilterAction": "include",
        }

        service = self._build_service()

        def _watch():
            return service.users().watch(userId=self.user_id, body=request_body).execute()

        result = await asyncio.get_event_loop().run_in_executor(None, _watch)

        log.info(
            "gmail.watch_registered",
            topic=topic_name,
            history_id=result.get("historyId"),
            expiration=result.get("expiration"),
        )
        return result

    # ── Inbound: Process Pub/Sub Push ─────────────────────────────────────────

    async def process_notification(self, pubsub_message: dict) -> list[dict]:
        """
        Process an incoming Pub/Sub push notification from Gmail.

        The push body contains a base64-encoded payload with historyId.
        This method fetches all new messages since that historyId.

        Args:
            pubsub_message: Raw Pub/Sub push body:
                {
                  "message": {
                    "data": "<base64-encoded JSON>",
                    "messageId": "...",
                    "publishTime": "..."
                  },
                  "subscription": "..."
                }

        Returns:
            List of normalized email dicts ready for Kafka publishing.
            Empty list if parsing fails or no new messages.
        """
        try:
            encoded = pubsub_message["message"]["data"]
            # Pub/Sub data may omit padding
            decoded_bytes = base64.urlsafe_b64decode(encoded + "==")
            payload = json.loads(decoded_bytes.decode("utf-8"))
        except (KeyError, ValueError, json.JSONDecodeError) as exc:
            log.error("gmail.pubsub_parse_failed", error=str(exc))
            return []

        history_id = payload.get("historyId")
        email_address = payload.get("emailAddress")

        if not history_id:
            log.warning("gmail.pubsub_missing_history_id", payload=payload)
            return []

        log.info(
            "gmail.notification_received",
            history_id=history_id,
            email_address=email_address,
        )

        messages = await self._fetch_messages_since(history_id)
        return messages

    async def _fetch_messages_since(self, history_id: str) -> list[dict]:
        """
        Use Gmail history.list to find messages added since history_id,
        then fetch and parse each one.
        """
        service = self._build_service()

        def _list_history():
            return (
                service.users()
                .history()
                .list(
                    userId=self.user_id,
                    startHistoryId=history_id,
                    historyTypes=["messageAdded"],
                    labelId="INBOX",
                )
                .execute()
            )

        try:
            history_result = await self._with_retry(_list_history, "history.list")
        except HttpError as exc:
            log.error("gmail.history_list_failed", history_id=history_id, error=str(exc))
            return []

        messages = []
        for record in history_result.get("history", []):
            for added in record.get("messagesAdded", []):
                msg_id = added["message"]["id"]
                msg = await self.get_message(msg_id)
                if msg:
                    messages.append(msg)

        log.info("gmail.messages_fetched", count=len(messages), history_id=history_id)
        return messages

    async def poll_inbox(self, max_results: int = 10) -> list[dict]:
        """
        Polling fallback — list recent UNREAD inbox messages without needing
        a Pub/Sub history_id.  Used when GMAIL_PUBSUB_TOPIC is not configured.
        """
        service = self._build_service()

        def _list_messages():
            return (
                service.users()
                .messages()
                .list(
                    userId=self.user_id,
                    labelIds=["INBOX", "UNREAD"],
                    maxResults=max_results,
                )
                .execute()
            )

        try:
            result = await self._with_retry(_list_messages, "messages.list.unread")
        except HttpError as exc:
            log.error("gmail.poll_inbox_failed", error=str(exc))
            return []

        messages = []
        for item in result.get("messages", []):
            msg = await self.get_message(item["id"])
            if msg:
                messages.append(msg)

        log.info("gmail.poll_inbox", count=len(messages))
        return messages

    async def get_message(self, message_id: str) -> Optional[dict]:
        """
        Fetch a single Gmail message by ID and return a normalized dict.

        Args:
            message_id: Gmail message ID.

        Returns:
            Normalized message dict:
                {
                  "channel": "email",
                  "channel_message_id": str,
                  "customer_email": str,
                  "customer_name": str,
                  "subject": str,
                  "content": str,
                  "thread_id": str,
                  "received_at": ISO-8601 str,
                  "metadata": {"headers": dict, "labels": list}
                }
            None if fetch or parsing fails.
        """
        service = self._build_service()

        def _fetch():
            return (
                service.users()
                .messages()
                .get(userId=self.user_id, id=message_id, format="full")
                .execute()
            )

        try:
            raw_msg = await self._with_retry(_fetch, f"messages.get:{message_id}")
        except HttpError as exc:
            log.error("gmail.message_fetch_failed", message_id=message_id, error=str(exc))
            return None

        return self._parse_gmail_message(raw_msg)

    def _parse_gmail_message(self, msg: dict) -> Optional[dict]:
        """
        Parse a raw Gmail message resource into a normalized channel payload.
        Returns None if the message has no readable body (e.g., delivery receipts).
        """
        payload = msg.get("payload", {})
        raw_headers = payload.get("headers", [])
        headers = {h["name"].lower(): h["value"] for h in raw_headers}

        from_header = headers.get("from", "")
        customer_email = self._extract_email(from_header)
        customer_name = self._extract_name(from_header)

        subject = headers.get("subject", "(no subject)")
        message_id_header = headers.get("message-id", "")
        thread_id = msg.get("threadId", "")
        internal_date_ms = int(msg.get("internalDate", 0))
        received_at = (
            datetime.utcfromtimestamp(internal_date_ms / 1000).isoformat()
            if internal_date_ms
            else datetime.utcnow().isoformat()
        )

        body = self._extract_body(payload)
        if not body:
            log.warning(
                "gmail.message_no_body",
                message_id=msg.get("id"),
                subject=subject,
            )
            return None

        return {
            "channel": "email",
            "channel_message_id": msg.get("id"),
            "customer_email": customer_email,
            "customer_name": customer_name,
            "subject": subject,
            "content": body,
            "thread_id": thread_id,
            "received_at": received_at,
            "metadata": {
                "headers": headers,
                "labels": msg.get("labelIds", []),
                "message_id_header": message_id_header,
            },
        }

    def _extract_body(self, payload: dict) -> str:
        """
        Recursively extract plain-text body from a Gmail message payload.
        Prefers text/plain over text/html. Returns empty string if none found.
        """
        mime_type = payload.get("mimeType", "")
        body_data = payload.get("body", {}).get("data", "")

        if mime_type == "text/plain" and body_data:
            return base64.urlsafe_b64decode(body_data + "==").decode(
                "utf-8", errors="replace"
            ).strip()

        # Recurse into multipart parts
        html_fallback = ""
        for part in payload.get("parts", []):
            result = self._extract_body(part)
            if result:
                # Prefer plain text; if this part was html we may continue looking
                if part.get("mimeType", "") == "text/plain":
                    return result
                html_fallback = html_fallback or result

        return html_fallback

    @staticmethod
    def _extract_email(from_header: str) -> str:
        """Extract email address from 'Name <email>' or 'email' format."""
        if "<" in from_header:
            return from_header.split("<")[-1].rstrip(">").strip()
        return from_header.strip()

    @staticmethod
    def _extract_name(from_header: str) -> str:
        """Extract display name from 'Name <email>' format."""
        if "<" in from_header:
            return from_header.split("<")[0].strip().strip('"')
        return ""

    # ── Outbound: Send Reply ──────────────────────────────────────────────────

    async def send_reply(
        self,
        to_email: str,
        subject: str,
        body: str,
        thread_id: Optional[str] = None,
        in_reply_to: Optional[str] = None,
    ) -> dict:
        """
        Send an email reply via the Gmail API with proper threading.

        Threading behaviour:
        - thread_id: keeps the reply in the same Gmail conversation thread
        - in_reply_to: sets RFC 2822 In-Reply-To + References headers so email
          clients display the reply nested under the original message

        Args:
            to_email: Recipient email address.
            subject: Email subject (automatically prefixed with "Re: " if needed).
            body: Plain-text reply body.
            thread_id: Gmail thread ID to attach the reply to.
            in_reply_to: Original message's Message-ID header value.

        Returns:
            dict:
                {
                  "channel_message_id": str,   # sent Gmail message ID
                  "delivery_status": "sent" | "failed",
                  "error": str | None
                }
        """
        reply_subject = subject if subject.startswith("Re:") else f"Re: {subject}"

        mime_msg = email.mime.multipart.MIMEMultipart()
        mime_msg["To"] = to_email
        mime_msg["Subject"] = reply_subject
        if in_reply_to:
            mime_msg["In-Reply-To"] = in_reply_to
            mime_msg["References"] = in_reply_to

        mime_msg.attach(email.mime.text.MIMEText(body, "plain", "utf-8"))
        raw_bytes = mime_msg.as_bytes()
        raw_b64 = base64.urlsafe_b64encode(raw_bytes).decode("utf-8")

        send_body: dict = {"raw": raw_b64}
        if thread_id:
            send_body["threadId"] = thread_id

        service = self._build_service()

        def _send():
            return (
                service.users()
                .messages()
                .send(userId=self.user_id, body=send_body)
                .execute()
            )

        try:
            result = await self._with_retry(_send, f"messages.send:{to_email}")
            sent_id = result.get("id", "")
            log.info(
                "gmail.reply_sent",
                to=to_email,
                thread_id=thread_id,
                message_id=sent_id,
            )
            return {"channel_message_id": sent_id, "delivery_status": "sent", "error": None}
        except HttpError as exc:
            log.error("gmail.reply_failed", to=to_email, error=str(exc))
            return {"channel_message_id": "", "delivery_status": "failed", "error": str(exc)}

    async def send_email(self, to: str, subject: str, body: str) -> dict:
        """Send a new outbound email (no thread context). Used by landing-page ack flow."""
        return await self.send_reply(to_email=to, subject=subject, body=body)

    async def send_reply_async(
        self,
        to_email: str,
        subject: str,
        body: str,
        thread_id: Optional[str] = None,
        in_reply_to: Optional[str] = None,
    ) -> dict:
        """Alias for send_reply (already async). Kept for API compatibility."""
        return await self.send_reply(to_email, subject, body, thread_id, in_reply_to)

    # ── Retry helper ──────────────────────────────────────────────────────────

    async def _with_retry(self, fn, label: str, max_retries: int = MAX_RETRIES):
        """
        Execute a synchronous Google API call in a thread pool with
        exponential-backoff retries on transient errors (429, 500, 503).

        Args:
            fn: Zero-argument callable that performs the API call.
            label: Human-readable label for logging.
            max_retries: Maximum retry attempts before re-raising.

        Returns:
            API response dict on success.

        Raises:
            HttpError: On non-retryable errors or after max retries exhausted.
        """
        loop = asyncio.get_event_loop()
        delay = RETRY_BASE_DELAY

        for attempt in range(1, max_retries + 2):  # +1 for initial try
            try:
                return await loop.run_in_executor(None, fn)
            except HttpError as exc:
                status = exc.resp.status if hasattr(exc, "resp") else 0
                retryable = status in (429, 500, 502, 503, 504)

                if not retryable or attempt > max_retries:
                    log.error(
                        "gmail.api_call_failed",
                        label=label,
                        attempt=attempt,
                        status=status,
                        error=str(exc),
                    )
                    raise

                log.warning(
                    "gmail.api_retrying",
                    label=label,
                    attempt=attempt,
                    status=status,
                    delay=delay,
                )
                await asyncio.sleep(delay)
                delay *= 2  # Exponential backoff

        # Should not reach here
        raise RuntimeError(f"Retry loop exited unexpectedly for {label}")


# ── Module-level convenience functions (backward compat) ─────────────────────
# Used by api/main.py webhook, message_processor.py, and tests.

def _extract_body(payload: dict) -> str:
    """
    Module-level wrapper for GmailHandler._extract_body.
    Recursively extracts plain-text body from a Gmail message payload.
    Prefers text/plain over text/html. Returns empty string if none found.
    """
    import base64 as _b64
    mime_type = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data", "")

    if mime_type == "text/plain" and body_data:
        return _b64.urlsafe_b64decode(body_data + "==").decode(
            "utf-8", errors="replace"
        ).strip()

    html_fallback = ""
    for part in payload.get("parts", []):
        result = _extract_body(part)
        if result:
            if part.get("mimeType", "") == "text/plain":
                return result
            html_fallback = html_fallback or result

    return html_fallback


def parse_pubsub_push(pubsub_body: dict) -> Optional[dict]:
    """
    Parse a raw Pub/Sub push body and return {history_id, email_address}.
    Returns None if the body is malformed.

    This is a stateless helper — no Gmail API call needed at parse time.
    Use GmailHandler.process_notification() for the full fetch flow.
    """
    try:
        encoded = pubsub_body["message"]["data"]
        decoded = json.loads(base64.urlsafe_b64decode(encoded + "==").decode("utf-8"))
        history_id = decoded.get("historyId")
        email_address = decoded.get("emailAddress")

        if not history_id:
            log.warning("gmail.parse_pubsub_push.missing_history_id")
            return None

        return {"history_id": history_id, "email_address": email_address}
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        log.error("gmail.parse_pubsub_push.failed", error=str(exc))
        return None


async def fetch_new_messages(history_id: str) -> list[dict]:
    """
    Convenience wrapper: create a GmailHandler and fetch messages since history_id.
    Suitable for use in FastAPI webhook handlers without managing handler state.
    """
    handler = GmailHandler()
    return await handler._fetch_messages_since(history_id)


async def poll_inbox(max_results: int = 10) -> list[dict]:
    """
    Convenience wrapper: poll Gmail inbox for recent unread messages.
    Use when Pub/Sub is not configured (GMAIL_PUBSUB_TOPIC is a placeholder).
    """
    handler = GmailHandler()
    return await handler.poll_inbox(max_results=max_results)
