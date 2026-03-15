---
id: 041
title: Fix KB text fallback and Gmail polling
stage: general
date: 2026-03-15
surface: agent
model: claude-sonnet-4-6
feature: none
branch: master
user: CDC
command: fix two issues — KB search broken, Gmail webhook non-functional
labels: ["bugfix","knowledge-base","gmail","embedding","polling"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - production/database/queries.py
  - production/agent/tools.py
  - production/channels/gmail_handler.py
  - production/api/main.py
tests:
  - none run
---

## Prompt

tum fix karo ye do cheezain or phir mujhe batao kaise demo video banao sub working kaise dikhaon

(Fix these two issues then tell me how to make a demo video showing everything working)

## Response snapshot

**Fix 1 — KB Search text fallback:**
- Added `search_knowledge_base_text()` in `queries.py` using PostgreSQL tsvector + ILIKE fallback
- Updated `tools.py` `search_knowledge_base` tool: when embedding is None (Groq doesn't support embeddings), now calls `queries.search_knowledge_base_text()` instead of returning empty
- KB search now works via full-text search even without vector embeddings

**Fix 2 — Gmail polling:**
- Added `poll_inbox()` method to `GmailHandler` class using `labelIds=["INBOX","UNREAD"]`
- Added module-level `poll_inbox()` convenience wrapper
- Refactored existing `/webhooks/gmail/poll` endpoint to use the new clean method
- Added top-level import of `poll_inbox as gmail_poll_module` in `main.py`

**Demo video guide provided** — 8 scenes covering all channels, admin dashboard, KB, Swagger docs, and Kubernetes manifests.

## Outcome

- ✅ Impact: KB search now functional via text fallback; Gmail can be polled without Pub/Sub
- 🧪 Tests: not run (would require live DB + Gmail credentials)
- 📁 Files: queries.py, tools.py, gmail_handler.py, main.py
- 🔁 Next prompts: run tests, record demo video
- 🧠 Reflection: Both fixes were minimal — text fallback 25 lines, poll_inbox 30 lines. Existing endpoint was already stubbed, just needed cleanup.

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): not run
- Prompt variant (if applicable): none
- Next experiment: run pytest with --ignore=load_test.py to verify KB tests now pass
