---
id: 027
title: Unified Message Processor Exercise 2.4
stage: green
date: 2026-03-10
surface: agent
model: claude-sonnet-4-6
feature: customer-success-fte
branch: master
user: CDC
command: manual
labels: ["kafka","worker","message-processor","exercise-2-4","production"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - production/workers/message_processor.py
tests:
  - none
---

## Prompt

Following Exercise 2.4, create /production/workers/message_processor.py:

Class UnifiedMessageProcessor with:
1. start() - initialize and consume
2. process_message() - main logic
3. resolve_customer() - find/create from email/phone
4. get_or_create_conversation()
5. store_message()
6. load_conversation_history()
7. run_agent() - execute with ALL 5 skills
8. handle_error() - graceful failure

Flow exactly as document example.

## Response snapshot

Rewrote `production/workers/message_processor.py` to implement `UnifiedMessageProcessor` class following Exercise 2.4's exact 8-method pattern.

Key design decisions:
- `start()` initialises aiokafka producer + consumer (idempotent, gzip, acks=all) and drives the consume loop
- `process_message()` orchestrates the 7-step flow: extract → resolve_customer → get_or_create_conversation → store_message → load_conversation_history → run_agent → publish response
- `resolve_customer()` delegates to `queries.find_or_create_customer()` with email/phone/channel
- `get_or_create_conversation()` delegates to `queries.get_or_create_conversation()` with 24h active-window logic
- `store_message()` delegates to `queries.store_message()` for all message persistence
- `load_conversation_history()` delegates to `queries.load_conversation_history()` returning `[{role, content}]`
- `run_agent()` wraps `production.agent.customer_success_agent.run_agent` and surfaces all 5 skills: create_ticket, get_customer_history, analyze_sentiment, search_knowledge_base, send_response
- `handle_error()` logs + records `processing_failure` metric to `agent_metrics` table
- Internal `_consume_with_retry()` provides exponential backoff (MAX_RETRIES=3, RETRY_BACKOFF_S=2.0) before dead-lettering
- Graceful shutdown via SIGINT/SIGTERM → `stop()` drains Kafka clients and closes DB pool

## Outcome

- ✅ Impact: Full Exercise 2.4 UnifiedMessageProcessor class implemented; replaces prior procedural functions with OOP class matching document specification
- 🧪 Tests: None run yet; manual testing requires Kafka + PostgreSQL
- 📁 Files: production/workers/message_processor.py (rewritten)
- 🔁 Next prompts: Exercise 2.5 Kafka event streaming; Exercise 2.6 FastAPI service; integration tests
- 🧠 Reflection: Existing file already had partial implementation; rewrote cleanly to match exact class/method structure from Exercise 2.4 document while preserving production-grade patterns (idempotent Kafka, retry logic, signal handling)

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): none
- Prompt variant (if applicable): none
- Next experiment (smallest change to try): add unit tests with mocked queries + aiokafka
