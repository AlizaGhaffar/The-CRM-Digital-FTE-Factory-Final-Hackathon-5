---
id: 028
title: FastAPI Service Channel Endpoints Exercise 2.6
stage: green
date: 2026-03-10
surface: agent
model: claude-sonnet-4-6
feature: customer-success-fte
branch: master
user: CDC
command: manual
labels: ["fastapi","api","webhooks","channels","exercise-2-6","production"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - production/api/main.py
tests:
  - none
---

## Prompt

Following Exercise 2.6, create /production/api/main.py:

Endpoints:
- POST /webhooks/gmail
- POST /webhooks/whatsapp
- POST /webhooks/whatsapp/status
- GET /conversations/{conversation_id}
- GET /customers/lookup
- GET /metrics/channels
- GET /health

Include CORS for web form and background tasks.

## Response snapshot

Rewrote `production/api/main.py` with all 8 endpoints from Exercise 2.6 specification.

Key implementation decisions:
- Webhook paths corrected to plural `/webhooks/` (matching Exercise 2.6 spec vs prior `/webhook/` singular)
- `POST /webhooks/gmail` — parse_pubsub_push → background_tasks fetch_new_messages → Kafka TOPIC_EMAIL (avoids Pub/Sub 30s timeout)
- `POST /webhooks/whatsapp` — validate_twilio_signature → parse_twilio_webhook → Kafka TOPIC_WHATSAPP; returns 200 always to prevent Twilio retry storms
- `POST /webhooks/whatsapp/status` — WhatsAppHandler.handle_delivery_status → queries.update_message_delivery (best-effort, non-blocking)
- `GET /conversations/{conversation_id}` — JOIN conversations + messages, returns full history with metadata
- `GET /customers/lookup` — read-only lookup by email AND/OR phone, includes conversation_count, open_ticket_count, channels_used aggregates
- `GET /metrics/channels` — delegates to queries.get_channel_summary(), adds computed escalation_rate per channel; degrades gracefully on DB error
- `GET /health` — always 200, includes channel configuration status (gmail token exists, Twilio creds set)
- `GET /ready` — 503 if postgres or kafka unreachable (k8s readiness probe)
- CORS: env-driven origins with localhost defaults (3000, 8080, 5173) for web form development
- web_form_router mounted for POST /support/submit + GET /support/ticket/{id}

## Outcome

- ✅ Impact: All 7 Exercise 2.6 endpoints plus /ready probe implemented; web form CORS enabled; background tasks for Gmail non-blocking fetch
- 🧪 Tests: None run; requires Kafka + PostgreSQL + Twilio/Gmail credentials
- 📁 Files: production/api/main.py (rewritten)
- 🔁 Next prompts: Exercise 2.7 Kubernetes deployment; integration tests (Exercise 3.1)
- 🧠 Reflection: Existing file had good infrastructure (lifespan, Kafka producer, CORS) but used singular /webhook/ paths and was missing 4 endpoints. Rewrite preserves all proven patterns while adding the new endpoints exactly as specified.

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): none
- Prompt variant (if applicable): none
- Next experiment (smallest change to try): add integration tests with TestClient + mock Kafka/DB
