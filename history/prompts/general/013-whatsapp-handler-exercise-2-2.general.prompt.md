---
id: 013
title: WhatsApp Handler Exercise 2.2
stage: general
date: 2026-03-07
surface: agent
model: claude-sonnet-4-6
feature: customer-success-fte
branch: master
user: CDC
command: create/rewrite production/channels/whatsapp_handler.py with WhatsAppHandler class, Twilio client, webhook validation, message splitting, delivery status
labels: ["whatsapp","twilio","channel","webhook","signature","message-split","delivery-status","exercise-2-2"]
links:
  spec: specs/customer-success-fte-spec.md
  ticket: null
  adr: null
  pr: null
files:
  - production/channels/whatsapp_handler.py
tests:
  - production/tests/test_channels.py TestWhatsAppHandler
---

## Prompt

Following Exercise 2.2, create /production/channels/whatsapp_handler.py:
1. Twilio client setup
2. Webhook signature validation
3. Process incoming WhatsApp messages
4. Send messages with proper formatting
5. Split long responses (max 1600 chars)
6. Handle delivery status
Include format_response function for message splitting.

## Response snapshot

Full rewrite of whatsapp_handler.py. Previous version had a critical bug (base64 imported at bottom after use → NameError), used raw httpx instead of Twilio SDK, and had no class structure.

**format_response(body, max_chars=1600) — module-level function:**
- Returns single-element list if len(body) <= max_chars
- Splits at sentence boundaries (". ", "! ", "? ") using rfind within window
- Falls back to word boundary (last space before max_chars)
- Hard-cuts if no boundary found
- Appends " (cont.)" marker on chunks when 3+ parts needed
- Returns list[str], each chunk <= max_chars

**WhatsAppHandler class:**
- `__init__(account_sid, auth_token, whatsapp_number)` — creates Twilio Client + RequestValidator; auto-adds "whatsapp:" prefix to number
- `validate_webhook(request: Request) → bool` — async; reads form data from FastAPI Request; calls RequestValidator.validate(url, params, signature); logs and returns False on invalid signature; fail-open if auth_token unset (dev mode)
- `process_webhook(form_data) → dict | None` — normalizes Twilio POST fields; detects COMPLIANCE_KEYWORDS (STOP/UNSTOP/HELP/etc.) and HUMAN_REQUEST_KEYWORDS (HUMAN/AGENT/etc.); returns None if From missing; adds is_compliance_trigger + is_human_request flags
- `send_message(to_phone, body) → dict` — runs client.messages.create() in executor; hard-truncates at 1600 with "..."; returns {channel_message_id, delivery_status, error}; catches TwilioRestException with error code
- `send_split_message(to_phone, body) → list[dict]` — calls format_response(); sends chunks sequentially with 0.3s delay between parts (preserves delivery order); returns list of result dicts
- `handle_delivery_status(form_data) → dict` — processes Twilio status callback (queued→sent→delivered/failed); logs warnings on failed/undelivered; returns {message_sid, status, to, error_code, error_message, timestamp}

**Constants:**
- WHATSAPP_MAX_CHARS = 1600 (Twilio hard limit)
- WHATSAPP_PREFERRED_CHARS = 300 (discovery-log D-004)
- COMPLIANCE_KEYWORDS = STOP/STOPALL/UNSUBSCRIBE/CANCEL/END/QUIT/UNSTOP/START/HELP
- HUMAN_REQUEST_KEYWORDS = HUMAN/AGENT/REPRESENTATIVE/PERSON/SUPPORT

**Backward compat module functions:**
- parse_twilio_webhook(form_data) — stateless, no Twilio client
- validate_twilio_signature(url, params, signature, auth_token) — uses RequestValidator

## Outcome

- Impact: WhatsAppHandler class matches document Exercise 2.2 pattern; all 6 features implemented; critical NameError bug fixed; sequential sends preserve message order
- Tests: test_channels.py TestWhatsAppHandler covers unit tests; delivery status test may need adding
- Files: production/channels/whatsapp_handler.py (full rewrite)
- Next prompts: web_form_handler.py (Exercise 2.2 last channel), then pytest
- Reflection: Sequential send in send_split_message is the most important design decision — parallel asyncio.gather sends arrive out of order on WhatsApp, which breaks multi-part responses

## Evaluation notes (flywheel)

- Failure modes observed: previous version imported base64 after use (NameError), used httpx not Twilio SDK, sent split messages in parallel (order not guaranteed)
- Graders run and results (PASS/FAIL): static review PASS — all 6 features present, format_response implemented, delivery status handler added
- Prompt variant (if applicable): none
- Next experiment: test format_response with exactly 1600, 1601, and 3200 char inputs to verify boundary splitting
