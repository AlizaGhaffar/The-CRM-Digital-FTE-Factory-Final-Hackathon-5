---
id: 014
title: Web Form Handler Exercise 2.2
stage: general
date: 2026-03-07
surface: agent
model: claude-sonnet-4-6
feature: customer-success-fte
branch: master
user: CDC
command: rewrite production/channels/web_form_handler.py with SupportFormSubmission validators, POST /support/submit, Kafka publish, create_ticket_record, GET /support/ticket/{ticket_id}
labels: ["web-form","fastapi","pydantic","kafka","postgres","exercise-2-2","router"]
links:
  spec: specs/customer-success-fte-spec.md
  ticket: null
  adr: null
  pr: null
files:
  - production/channels/web_form_handler.py
tests:
  - production/tests/test_channels.py TestWebFormHandler
---

## Prompt

Following Exercise 2.2, create /production/channels/web_form_handler.py:
1. Pydantic models with validation (name min 2 chars, message min 10 chars, valid email)
2. POST /support/submit endpoint
3. Create ticket and publish to Kafka
4. GET /support/ticket/{ticket_id} endpoint
Follow the document example exactly.

## Response snapshot

Full rewrite. Previous file had no FastAPI router, no endpoints, no Kafka — only Pydantic models and SMTP email helpers.

**SupportFormSubmission (document pattern, Pydantic v2 field_validator):**
- `name_must_not_be_empty` → strips whitespace, raises if len < 2
- `message_must_have_content` → strips whitespace, raises if len < 10, strips <script> tags (XSS guard at boundary)
- `category_must_be_valid` → validates against VALID_CATEGORIES list
- `no_honeypot` → raises if honeypot field is non-empty (bot trap)
- Fields: name, email (EmailStr), subject, category, message, priority, attachments, honeypot

**SupportFormResponse:** ticket_id, message, estimated_response_time

**TicketStatusResponse:** ticket_id, status, category, priority, created_at, resolved_at, resolution_notes

**router = APIRouter(prefix="/support", tags=["support-form"])**

**POST /support/submit:**
1. Pydantic validates body (name/message/category validators run automatically)
2. Generates ticket_id = uuid4()
3. Detects HIGH_PRIORITY_SIGNALS in message → upgrades priority to "high" (D-008)
4. Builds message_data dict with channel="web_form", channel_message_id=ticket_id
5. asyncio.gather(publish_to_kafka(), create_ticket_record()) — concurrent
6. Raises 503 only if BOTH kafka and DB fail simultaneously
7. Returns SupportFormResponse

**publish_to_kafka(topic, message_data) → bool:**
- Creates short-lived AIOKafkaProducer per call (no shared producer dependency)
- start() → send_and_wait() → stop() in finally block
- Returns False on any exception (does not raise)

**create_ticket_record(ticket_id, message_data) → bool:**
- Calls queries.find_or_create_customer(email, name, channel="web_form")
- INSERT INTO conversations (customer_id, initial_channel, status)
- INSERT INTO tickets (id, conversation_id, customer_id, source_channel, category, priority, status)
- INSERT INTO messages (conversation_id, channel, direction, role, content, channel_message_id)
- Returns False on exception (does not raise)

**GET /support/ticket/{ticket_id}:**
- SELECT from tickets WHERE id = $1::uuid
- Returns TicketStatusResponse
- Raises 404 if not found, 503 if DB unavailable

**Backward compat preserved:**
- WebFormSubmission (legacy model) with no_honeypot + no_script_injection validators
- parse_web_form(form_data) → channel payload dict (used by api/main.py)
- send_confirmation_email() + send_confirmation_email_async() (SMTP)
- structlog replaces standard logging

## Outcome

- Impact: web_form_handler now has complete FastAPI router matching document Exercise 2.2 — browser can submit forms, Kafka event is published, DB ticket is created, and status can be retrieved via GET
- Tests: test_channels.py TestWebFormHandler covers existing parse/validation tests; endpoint tests need adding in test_e2e.py
- Files: production/channels/web_form_handler.py (full rewrite)
- Next prompts: mount router in api/main.py (app.include_router(router)), run pytest
- Reflection: asyncio.gather for Kafka + DB concurrent write is the key design — neither should block the other; 503 only when both fail ensures maximum availability

## Evaluation notes (flywheel)

- Failure modes observed: previous version had no endpoints at all; missing Kafka publish; no GET ticket status
- Graders run and results (PASS/FAIL): static review PASS — all 4 user requirements present, document example followed exactly, backward compat preserved
- Prompt variant (if applicable): none
- Next experiment: test 503 path by mocking both publish_to_kafka and create_ticket_record to return False
