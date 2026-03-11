---
id: 010
title: System Prompt Step 4 Formal Transformation
stage: general
date: 2026-03-07
surface: agent
model: claude-sonnet-4-6
feature: customer-success-fte
branch: master
user: CDC
command: create formal system prompt in production/agent/prompts.py
labels: ["prompts","system-prompt","brand-voice","escalation","channel-awareness","step4"]
links:
  spec: specs/customer-success-fte-spec.md
  ticket: null
  adr: null
  pr: null
files:
  - production/agent/prompts.py
tests:
  - test_agent.py TestPrompts covers SYSTEM_PROMPT content assertions
---

## Prompt

Following "Step 4: Transform Your System Prompt":

Create /production/agent/prompts.py with formal system prompt including:
- Purpose
- Channel Awareness (Email, WhatsApp, Web differences)
- Required Workflow (ALWAYS create ticket first)
- Hard Constraints (NEVER discuss pricing)
- Escalation Triggers (from escalation-rules.md)
- Response Quality Standards
- Context Variables

Use brand-voice.md for tone guidance.

## Response snapshot

Rewrote production/agent/prompts.py with 7-section SYSTEM_PROMPT + 3 new routing maps.

SYSTEM_PROMPT sections:
1. PURPOSE — mission, success metrics (escalation rate, accuracy, latency, identification accuracy)
2. CHANNEL AWARENESS — per-channel: audience, tone, sentiment baseline, priority signals, format rules, identity handling. Includes data from discovery-log (D-001 to D-020): email avg 0.48 sentiment, WhatsApp avg 0.73, 76% B2B "we" emails, WhatsApp 8.3-word average.
3. REQUIRED WORKFLOW — 6-step numbered sequence (create_ticket → get_customer_history → analyze_sentiment → search_knowledge_base → escalate_to_human → send_response) with inline decision conditions
4. HARD CONSTRAINTS — NEVER/ALWAYS blocks with specific action language and tool call references
5. ESCALATION TRIGGERS — full hard/soft trigger table with keywords, urgency, routing address, SLA. Includes dual-routing for legal+security. No-touch topics section.
6. RESPONSE QUALITY STANDARDS — accuracy, empathy (with channel thresholds), tone (from brand-voice.md We ARE/NOT), escalation verbatim templates, actionable endings
7. CONTEXT VARIABLES — full typed variable listing available to agent at runtime

New constants added:
- ROUTING_EMAIL: reason → list[str] (supports dual-routing e.g. legal+security)
- URGENCY_BY_REASON: reason → default urgency string
- get_routing_emails(): helper returning routing addresses for a reason
- get_default_urgency(): helper returning correct starting urgency before keyword upgrade

## Outcome

- Impact: SYSTEM_PROMPT is now the authoritative behavioural specification for the production agent — all 7 required sections present, data-backed channel guidance, complete escalation routing table
- Tests: TestPrompts in test_agent.py validates key sections and keyword presence
- Files: production/agent/prompts.py (full rewrite)
- Next prompts: run pytest, integrate get_routing_emails into escalate_to_human tool
- Reflection: Channel Awareness section is the highest-value addition — agents often treat all channels the same; the per-channel behavioural profiles prevent systematic errors

## Evaluation notes (flywheel)

- Failure modes observed: original lacked channel-specific guidance, no context variables, no routing map
- Graders run and results (PASS/FAIL): static review PASS — all 7 sections present, verbatim brand-voice templates included
- Prompt variant (if applicable): none
- Next experiment: A/B test empathy threshold at 0.5 vs 0.4 on email to measure resolution rate impact
