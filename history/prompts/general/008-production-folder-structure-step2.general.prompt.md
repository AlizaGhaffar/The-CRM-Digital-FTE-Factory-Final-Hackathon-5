---
id: 008
title: Production Folder Structure Step 2
stage: general
date: 2026-03-07
surface: agent
model: claude-sonnet-4-6
feature: customer-success-fte
branch: master
user: CDC
command: create production/ folder structure (Step 2)
labels: ["production","architecture","fastapi","kafka","channels","tests","agents-sdk"]
links:
  spec: specs/customer-success-fte-spec.md
  ticket: null
  adr: null
  pr: null
files:
  - production/agent/prompts.py
  - production/agent/formatters.py
  - production/channels/gmail_handler.py
  - production/channels/whatsapp_handler.py
  - production/channels/web_form_handler.py
  - production/workers/metrics_collector.py
  - production/api/main.py
  - production/tests/test_agent.py
  - production/tests/test_channels.py
  - production/tests/test_e2e.py
tests:
  - test_agent.py: 25 tests (formatters, prompts, tool unit tests)
  - test_channels.py: 20 tests (Gmail, WhatsApp, Web Form handlers)
  - test_e2e.py: 15 edge cases + API endpoint tests
---

## Prompt

Following "Step 2: Map Prototype Code to Production Components":

Create production folder structure exactly as in document:

production/
├── agent/
│   ├── __init__.py
│   ├── customer_success_agent.py
│   ├── tools.py (ALL 5 skills as @function_tool)
│   ├── prompts.py
│   └── formatters.py
├── channels/
│   ├── __init__.py
│   ├── gmail_handler.py
│   ├── whatsapp_handler.py
│   └── web_form_handler.py
├── workers/
│   ├── __init__.py
│   ├── message_processor.py
│   └── metrics_collector.py
├── api/
│   ├── __init__.py
│   └── main.py
├── database/
│   ├── schema.sql
│   ├── migrations/
│   └── queries.py
├── tests/
│   ├── test_agent.py
│   ├── test_channels.py
│   └── test_e2e.py
├── k8s/
├── Dockerfile
├── docker-compose.yml
└── requirements.txt

## Response snapshot

Read all existing files before writing to avoid duplication. Pre-existing files:
customer_success_agent.py, tools.py, message_processor.py, queries.py, schema.sql, Dockerfile, docker-compose.yml, requirements.txt, all __init__.py, k8s/.gitkeep

Created 10 missing files:
- prompts.py: SYSTEM_PROMPT, escalation templates, SLA map, team-by-reason map, get_escalation_message()
- formatters.py: format_response(), _strip_filler(), _strip_markdown_for_whatsapp(), CHANNEL_PARAMS, EMPATHY_OPENERS with channel thresholds
- gmail_handler.py: Pub/Sub push parsing, Gmail API message fetch, reply-to-thread send, async wrappers
- whatsapp_handler.py: Twilio webhook parsing, signature validation, COMPLIANCE_KEYWORDS, send_message(), send_split_message()
- web_form_handler.py: Pydantic validation, XSS stripping, honeypot, business-impact priority detection, SMTP confirmation email
- metrics_collector.py: compute_rolling_metrics(), compute_daily_summary(), MetricsCollector worker loop, target violation alerts
- main.py: FastAPI app with lifespan, /webhook/gmail, /webhook/whatsapp, /api/support, /api/tickets, /health, /ready
- test_agent.py: 25 unit tests for formatters, prompts, and all 6 tools
- test_channels.py: 20 unit tests for all 3 channel handlers
- test_e2e.py: 15 edge cases (all from transition-checklist §4) + API endpoint tests

## Outcome

- Impact: Complete production/ folder structure — all 19 files present, structure matches hackathon spec exactly
- Tests: 60+ test functions across 3 test files, all 15 edge cases covered
- Files: 10 new files created; 9 pre-existing files preserved unchanged
- Next prompts: pytest run, docker-compose up, Stage 2 production deployment
- Reflection: Read all existing files first to avoid duplicating tools.py logic in formatters.py (format_response was already in tools.py as _format_for_channel; extracted cleanly)

## Evaluation notes (flywheel)

- Failure modes observed: None — existing files were well-structured and consistent
- Graders run and results (PASS/FAIL): static review — PASS (no placeholders, consistent imports, Pydantic v2)
- Prompt variant (if applicable): none
- Next experiment: run pytest to validate all 60+ tests pass against actual implementations
