---
name: Backend pipeline fix — 59 tests passing
description: Full backend debug session fixing tools.py, queries.py, worker, docker-compose to get end-to-end working
type: general
stage: general
date: 2026-03-13
surface: agent
model: claude-sonnet-4-6
feature: none
branch: master
---

## Prompt

im back ab batao kiya remainig hai backend to running hogayi thi is ki ye dekho & 'c:\Users\CDC\Videos\2026-03-13 15-19-32.mp4'

(follow-up): main kaise karu tum step by step batao or complete karo sub

## What Was Done

### State at start
- Schema applied to NeonDB ✅
- Knowledge base seeded (11 rows with Gemini embeddings) ✅
- All Docker containers defined but worker crashing, API starting

### Fixes applied (in order)

1. **tools.py — `@function_tool` wrapping broke tests**
   - `FunctionTool` objects not directly `await`-able
   - Fix: kept raw async functions callable, created `_xxx_tool = function_tool(xxx)` wrappers for `ALL_TOOLS`
   - Added `__name__` attribute to FunctionTool objects for test introspection

2. **tools.py — KB search used httpx directly (unmockable)**
   - Changed `search_knowledge_base` to use `_get_openai().embeddings.create()` so tests can mock via `_get_openai`

3. **tools.py — Critical keyword cap at 0.1 not triggering immediate_escalate**
   - Changed `min(score, 0.1)` → `min(score, 0.09)` so `score < 0.1` fires

4. **tools.py — Added "legal counsel" / "retained counsel" to CRITICAL_KEYWORDS**

5. **tests/test_transition.py — `_make_queries(kb_results=[])` bug**
   - `kb_results or [default]` → `kb_results if kb_results is not None else [default]`

6. **workers/message_processor.py — Missing `_extract_fields` function**
   - Added module-level normaliser mapping `body`/`content`, `from_email`/`customer_email`, etc.
   - Used in `process_message` to handle field variants across channels

7. **docker-compose.yml — Worker command**
   - `python production/workers/message_processor.py` → `python -m production.workers.message_processor`
   - Fixes `ModuleNotFoundError: No module named 'production'`

8. **database/queries.py — JSONB fields need JSON strings**
   - `tool_calls or []` → `json.dumps(tool_calls or [])`
   - `dimensions or {}` → `json.dumps(dimensions or {})`

9. **database/queries.py — NeonDB SSL connection**
   - Added `DATABASE_URL` DSN path (preferred) with SSL included
   - Without SSL, NeonDB connections fail → `create_ticket` falls back to temp IDs

10. **customer_success_agent.py — RunConfig overriding Gemini with gpt-4o**
    - `RunConfig(model="gpt-4o", ...)` was forcing default OpenAI provider
    - Fix: removed `model` from RunConfig, set `tracing_disabled=True`

11. **.env — Kafka topic alignment**
    - Added `KAFKA_TOPIC_WEB_FORM=nimbusflow.messages.web_form` so web form handler publishes to same topic worker listens on

### Final state
- 59/59 tests passing (`pytest production/tests/test_transition.py`)
- API running at `http://localhost:8000` (Docker)
- Worker connected to Kafka + NeonDB, processing messages
- Full e2e flow: `POST /support/submit` → Kafka → Worker → Gemini agent → NeonDB → `/ticket/{id}/messages`
- Blocked only by Gemini free tier daily limit (20 req/day exhausted during testing)

### Remaining
- Gemini free tier limit reset (midnight) OR enable billing on AI Studio
- Gmail OAuth token present at `secrets/token.json` ✅
- Frontend wiring to API (separate task)
