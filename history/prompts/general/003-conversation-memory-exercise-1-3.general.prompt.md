---
id: 003
title: Conversation Memory Exercise 1.3
stage: general
date: 2026-03-06
surface: agent
model: claude-sonnet-4-6
feature: none
branch: master
user: CDC
command: inline
labels: ["memory","conversation","identity-resolution","channel-switch","sentiment","incubation","exercise-1.3"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - src/agent/memory.py
  - tests/test_memory.py
tests:
  - tests/test_memory.py (58 tests — 58 passed)
---

## Prompt

Following Exercise 1.3, add conversation memory:

/src/agent/memory.py with:
1. Track conversation context across messages
2. Handle channel switches (same customer from email to WhatsApp)
3. Track sentiment per interaction
4. Track topics discussed
5. Track resolution status
6. Use email as primary customer identifier

All state should work with our database schema.

## Response snapshot

Created `src/agent/memory.py` with `MemoryStore` class — all six features implemented.

Field names and types mirror production/database/schema.sql exactly for a clean Stage 2 swap to asyncpg.

**Feature coverage:**
1. `get_or_create_conversation` + `add_message` — tracks full message history with role/direction/sentiment per message; `get_conversation_history` returns `[{role, content}]` for agent context window
2. Channel switch: `get_or_create_conversation` detects channel change, appends `{from, to, switched_at}` to `channel_switches` (mirrors conversations.channel_switches JSONB), updates `current_channel`, preserves `conversation_id`
3. `update_sentiment` — rolling per-message history; computes `improving/stable/declining` trend using configurable delta threshold against SENTIMENT_HISTORY_WINDOW rolling average
4. `add_topic` — case-insensitive dedup list; surfaced in `build_agent_context`
5. `create_ticket` + `update_ticket` — full status lifecycle (open→responded→escalated→resolved→closed); `open_tickets` counter decrements on resolve; `lifetime_tickets` increments per ticket
6. `find_or_create_customer` — email normalised to lowercase as primary key; phone as E.164 secondary; `_identifier_index` reproduces customer_identifiers table; email wins over phone in lookup priority; merges identifiers when both provided

`process_inbound(email, phone, name, channel, body)` convenience wrapper performs all six steps in one call matching the production `queries.py` interface.

`build_agent_context(customer_id)` returns full 360° summary dict for agent prompt injection.

**58/58 tests pass.**

## Outcome

- Impact: Exercise 1.3 complete. MemoryStore is a drop-in prototype for production asyncpg calls. Channel switches, identity resolution, and sentiment tracking all work correctly.
- Tests: 58/58 PASS (0.44s)
- Files: src/agent/memory.py (new), tests/test_memory.py (new)
- Next prompts: Exercise 1.4 (MCP server integration with memory), wire memory into core.py run_core_loop
- Reflection: `_active_convs` uses a single slot per customer — sufficient for incubation; production will query by customer_id + status + started_at window. Sentiment trend uses simple rolling average; production could use LLM-scored sentiment from the message itself.

## Evaluation notes (flywheel)

- Failure modes observed: none — 58/58 first run
- Graders run and results (PASS/FAIL): pytest tests/test_memory.py — 58 PASS
- Prompt variant (if applicable): none
- Next experiment: Wire memory.process_inbound into core.run_core_loop; add memory.build_agent_context output to generate_response system prompt
