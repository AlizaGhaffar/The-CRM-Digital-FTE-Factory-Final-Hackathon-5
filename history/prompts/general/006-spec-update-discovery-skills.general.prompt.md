---
id: 006
title: Spec Update from Discovery and Skills
stage: general
date: 2026-03-07
surface: agent
model: claude-sonnet-4-6
feature: customer-success-fte
branch: master
user: CDC
command: create/update /specs/customer-success-fte-spec.md
labels: ["spec","customer-success","discovery","skills-manifest","guardrails","channels","escalation"]
links:
  spec: specs/customer-success-fte-spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/customer-success-fte-spec.md
tests:
  - 15 edge cases from discovery-log.md §6 (all referenced)
  - 38 test cases cross-referenced from skills-manifest.md
---

## Prompt

Following the hackathon document, create:

/specs/customer-success-fte-spec.md with:

1. Purpose
2. Supported Channels table (Channel, Identifier, Response Style, Max Length)
3. Scope (In Scope vs Out of Scope - escalate)
4. Tools table (Tool, Purpose, Constraints)
5. Performance Requirements
6. Guardrails (NEVER discuss pricing, ALWAYS create ticket first, etc.)

Base this on our discovery-log.md and skills-manifest.md.

## Response snapshot

Rewrote `specs/customer-success-fte-spec.md` from v1.0 to v2.0 with 9 sections:
1. Purpose — includes success metrics and discovery sources
2. Supported Channels — enriched with avg sentiment, critical ticket rate, and D-00x behaviour insights
3. Scope — In/Out table with route-to column; sub-classification guide for "General" tickets (D-009)
4. Agent Tools — maps each tool to the Skill that calls it; enforces mandatory execution order
5. Performance Requirements — baseline vs target gap table from discovery-log.md §8
6. Guardrails — ALWAYS/NEVER blocks; hard escalation triggers with route; soft triggers; response quality rules
7. Skills Reference — cross-links to skills-manifest.md execution order
8. Context Variables — full typed context object available to agent
9. Edge Cases — all 15 from discovery-log.md §6 with handling

## Outcome

- Impact: Spec is now the authoritative v2.0 design document for the Customer Success FTE agent, grounded in 55-ticket empirical analysis and 5-skill decomposition
- Tests: 15 edge cases + 38 skill test cases cross-referenced; no placeholders
- Files: specs/customer-success-fte-spec.md (updated v1.0 → v2.0)
- Next prompts: /sp.plan for architecture plan; /sp.tasks to generate implementation tasks
- Reflection: Key value added: data-backed channel behaviour notes (D-001 to D-021), dual-routing for security+legal incidents, sub-categorisation of "General" tickets, gap-closure strategy for escalation rate

## Evaluation notes (flywheel)

- Failure modes observed: v1.0 lacked empirical grounding — all targets were aspirational, not compared to baseline
- Graders run and results (PASS/FAIL): manual review — PASS
- Prompt variant (if applicable): none
- Next experiment: validate guardrails against full sample-tickets.json run
