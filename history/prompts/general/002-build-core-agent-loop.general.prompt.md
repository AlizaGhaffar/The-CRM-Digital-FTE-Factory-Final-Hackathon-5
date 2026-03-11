---
id: 002
title: Build Core Agent Loop Exercise 1.2
stage: general
date: 2026-03-06
surface: agent
model: claude-sonnet-4-6
feature: none
branch: master
user: CDC
command: inline
labels: ["core-loop","prototype","incubation","exercise-1.2","customer-success-fte"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - src/agent/core.py
  - tests/test_core.py
tests:
  - tests/test_core.py (63 tests — 63 passed)
---

## Prompt

Following Exercise 1.2 from hackathon, build prototype core loop:

/src/agent/core.py with:
1. Take customer message + channel metadata
2. Normalize message regardless of source
3. Search product-docs.md for relevant info
4. Generate helpful response
5. Format for channel (email vs WhatsApp style)
6. Decide if escalation needed using escalation-rules.md

Use company-profile.md and brand-voice.md for context.
Test with sample-tickets.json.

## Response snapshot

Created `src/agent/core.py` — a clean six-step pipeline:

1. **Normalize** (`normalize_message`): Canonical `InboundMessage` dataclass from any raw payload. Handles email (`content`), WhatsApp (`content`), and web_form (`message`) field differences. Collapses whitespace.

2. **Search** (`search_docs`): Keyword-based relevance search over product-docs.md sections. Title match = 3x weight. Two-pass retry on no hits.

3. **Sentiment** (`score_sentiment`): Keyword + caps-ratio scoring. 0.0–1.0 scale.

4. **Escalate** (`check_escalation`): Hard trigger table covering legal, security, chargeback, data loss, refund, human-request, compliance, account-level actions, pricing negotiation. Sentiment < 0.2 soft trigger. Short-circuits before generation.

5. **Generate** (`generate_response`): OpenAI gpt-4o call with full system prompt built from company-profile.md + brand-voice.md + escalation-rules.md. Graceful fallback to KB snippet when `OPENAI_API_KEY` is absent.

6. **Format** (`format_for_channel`): Per brand-voice.md — email (greeting + sign-off + ticket ref), WhatsApp (markdown stripped, ≤280 chars), web-form (medium, closing). Escalation messages use SLA-aware handoff template.

Orchestrated by `run_core_loop(raw_payload, channel) -> AgentResponse`.

Created `tests/test_core.py` — 63 tests across all six steps + sample-tickets.json end-to-end coverage. **63/63 pass**.

CLI: `python src/agent/core.py --ticket T-001` / `--all-tickets` / `--channel whatsapp --message "..."`

## Outcome

- Impact: Exercise 1.2 core loop complete; all 55 sample tickets produce a response; critical escalation tickets correctly trigger escalation; simple FAQ tickets resolve without escalation.
- Tests: 63/63 PASS (0.47s)
- Files: src/agent/core.py (new), tests/test_core.py (new)
- Next prompts: Exercise 1.3 (memory/state), Exercise 2.x (production agent with OpenAI Agents SDK + FastAPI)
- Reflection: KB fallback produces acceptable but shallow responses; adding OPENAI_API_KEY will unlock brand-voice-aware generation. Sentiment scoring is keyword-heuristic; production should delegate to LLM.

## Evaluation notes (flywheel)

- Failure modes observed: Two test helpers missing `channel` arg (caught + fixed during test run)
- Graders run and results (PASS/FAIL): pytest tests/test_core.py — 63 PASS
- Prompt variant (if applicable): none
- Next experiment: Add OpenAI API key and verify brand-voice compliance on generated responses
