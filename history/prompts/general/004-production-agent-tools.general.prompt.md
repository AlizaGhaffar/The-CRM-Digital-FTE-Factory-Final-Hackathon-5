---
id: 004
title: Build Production Agent Tools and Agent Definition
stage: general
date: 2026-03-06
surface: agent
model: claude-sonnet-4-6
feature: customer-success-fte
branch: master
user: CDC
command: implementation
labels: ["openai-agents-sdk", "function_tool", "agent", "production", "tools"]
links:
  spec: specs/customer-success-fte-spec.md
  ticket: null
  adr: null
  pr: null
files:
  - production/agent/tools.py
  - production/agent/customer_success_agent.py
tests:
  - none yet
---

## Prompt

[Session continuation — implied next step from previous session]
Build production/agent/tools.py with @function_tool wrappers around queries.py,
then build customer_success_agent.py with the OpenAI Agents SDK Agent definition.

## Response snapshot

Created two production agent files:

**tools.py** (6 @function_tool functions):
- `create_ticket`: finds/creates customer + conversation + ticket; returns all 3 IDs
- `get_customer_history`: returns last N tickets + repeat_contact detection
- `analyze_sentiment`: OpenAI LLM scoring (0.0–1.0) + fast-path critical keyword override
- `search_knowledge_base`: embeds query via text-embedding-3-small, vector search with auto-retry at 0.60 threshold
- `escalate_to_human`: creates escalation record, updates ticket status, auto-upgrades urgency from keywords, returns channel-appropriate customer message
- `send_response`: enforces channel formatting (length limits, markdown stripping for WhatsApp), stores message, records metric

**customer_success_agent.py**:
- `SYSTEM_PROMPT`: full mandatory workflow, hard rules, escalation triggers, channel formatting guide
- `get_agent()`: singleton Agent with all 6 tools and gpt-4o model
- `run_agent()`: end-to-end async runner — builds context message, loads conversation history, runs Agent via Runner.run(), extracts tool outputs, records latency metric, returns structured result dict

## Outcome

- Impact: Full production agent layer complete. run_agent() is the single entry point for all channel workers.
- Tests: None yet — integration tests in production/tests/test_transition.py (Day 5)
- Files: 2 files — tools.py (~340 lines), customer_success_agent.py (~200 lines)
- Next prompts: Build production/workers/message_processor.py (Kafka consumer), then FastAPI channel handlers
- Reflection: Pydantic validators on all tool inputs catch bad data before DB calls. Auto-urgency upgrade in escalate_to_human means agent only needs to pass reason text — routing is deterministic.

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): none yet
- Prompt variant: none
- Next experiment: pytest production/tests/ with mocked DB pool after message_processor is built
