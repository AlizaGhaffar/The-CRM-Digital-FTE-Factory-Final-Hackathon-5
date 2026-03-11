---
id: 005
title: Skills Manifest Exercise 1.5
stage: general
date: 2026-03-07
surface: agent
model: claude-sonnet-4-6
feature: customer-success-fte
branch: master
user: CDC
command: create /specs/skills-manifest.md
labels: ["skills","manifest","exercise-1.5","customer-success","sentiment","escalation","channel-adaptation","knowledge-retrieval"]
links:
  spec: specs/customer-success-fte-spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/skills-manifest.md
tests:
  - TC-1.1 through TC-1.6 (Customer Identification)
  - TC-2.1 through TC-2.6 (Sentiment Analysis)
  - TC-3.1 through TC-3.6 (Knowledge Retrieval)
  - TC-4.1 through TC-4.10 (Escalation Decision)
  - TC-5.1 through TC-5.10 (Channel Adaptation)
---

## Prompt

Following Exercise 1.5 EXACTLY from hackathon document:

Create /specs/skills-manifest.md defining 5 skills:

1. Knowledge Retrieval Skill
   - When to use: Customer asks product questions
   - Inputs: query text, channel context
   - Outputs: relevant documentation snippets
   - Implementation: search_knowledge_base tool

2. Sentiment Analysis Skill
   - When to use: Every customer message
   - Inputs: message text, conversation history
   - Outputs: sentiment score (0-1), confidence, trend
   - Implementation: analyze_sentiment function

3. Escalation Decision Skill
   - When to use: After generating response
   - Inputs: conversation context, sentiment trend, message content
   - Outputs: should_escalate (bool), reason, urgency
   - Use escalation-rules.md from context

4. Channel Adaptation Skill
   - When to use: Before sending any response
   - Inputs: response text, target channel, brand-voice.md
   - Outputs: formatted response appropriate for channel
   - Email: formal with greeting/signature
   - WhatsApp: concise, conversational, emojis allowed
   - Web: semi-formal, balanced

5. Customer Identification Skill
   - When to use: On every incoming message
   - Inputs: message metadata (email, phone, headers)
   - Outputs: unified customer_id, merged history across channels
   - Implementation: customer lookup in database

Each skill must have clear inputs, outputs, and test cases.

## Response snapshot

Created `specs/skills-manifest.md` with all 5 skills fully defined:
- Skill 1: Customer Identification — resolves identity from metadata, PostgreSQL lookup, guest fallback
- Skill 2: Sentiment Analysis — scores 0–1, detects signals (caps, profanity, legal language), trend tracking
- Skill 3: Knowledge Retrieval — semantic search over product-docs.md, plan-filtered, escalates after 2 failed searches
- Skill 4: Escalation Decision — applies all hard/soft triggers from escalation-rules.md, routes to correct team
- Skill 5: Channel Adaptation — formats per brand-voice.md rules for email/WhatsApp/web, strips fillers, applies empathy

Each skill includes typed input/output tables, implementation pseudocode, and 6–10 test cases. Execution order and data dependency table included.

## Outcome

- Impact: Complete skill inventory for the NimbusFlow Customer Success FTE agent, ready for Stage 2 implementation
- Tests: 38 test cases across 5 skills covering happy path, edge cases, and failure modes
- Files: specs/skills-manifest.md (created)
- Next prompts: /sp.plan to generate architecture plan; /sp.tasks to generate implementation tasks; /sp.adr for key decisions
- Reflection: Cross-referenced escalation-rules.md and brand-voice.md to ensure skill outputs match real trigger thresholds and channel formatting rules

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): manual review — PASS (all 5 skills defined, 38 test cases, no unresolved placeholders)
- Prompt variant (if applicable): none
- Next experiment: validate test cases against actual tool implementations in Stage 2
