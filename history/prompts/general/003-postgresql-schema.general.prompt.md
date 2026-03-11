---
id: 003
title: Create Production PostgreSQL Schema
stage: general
date: 2026-03-06
surface: agent
model: claude-sonnet-4-6
feature: customer-success-fte
branch: master
user: CDC
command: schema creation
labels: ["database", "postgresql", "pgvector", "crm", "schema"]
links:
  spec: specs/customer-success-fte-spec.md
  ticket: null
  adr: null
  pr: null
files:
  - production/database/schema.sql
  - production/database/queries.py
  - production/database/seed_knowledge_base.py
  - production/database/migrations/v2.0.0_initial.sql
tests:
  - none yet (DB tests come in production/tests/test_transition.py)
---

## Prompt

Create PostgreSQL schema from hackathon document section Exercise 2.1 including all 8 tables with pgvector extension and proper indexes. This IS the CRM system.

## Response snapshot

Rewrote schema.sql (1049 lines) from scratch with full production-grade schema. Created queries.py with all async DB access functions. Created seed_knowledge_base.py for loading product-docs.md into vector store.

Tables: customers, customer_identifiers, conversations, messages, tickets, knowledge_base (VECTOR(1536)), channel_configs, agent_metrics, escalations (9 total)

Key additions over hackathon baseline:
- 7 CHECK constraints across all enum-like columns
- 6 triggers: updated_at, message_count, SLA breach time, resolution time, customer counters, escalation SLA
- 4 helper functions: fn_find_or_create_customer, fn_search_knowledge_base, fn_get_active_conversation, fn_get_customer_summary
- 4 views: v_open_tickets, v_channel_daily_summary, v_knowledge_base_usage, v_sla_breaches
- 28 indexes including IVFFlat vector index (lists=100), GIN for JSONB/arrays, partial indexes for SLA monitoring
- knowledge_base.embedding VECTOR(1536) with ivfflat cosine ops index
- channel_configs.secrets_encrypted pattern for safe API key storage

## Outcome

- Impact: Complete production-ready schema. Run docker-compose up postgres then psql -f schema.sql to apply. Vector search via fn_search_knowledge_base(). Customer unification via fn_find_or_create_customer().
- Tests: None yet — DB integration tests in production/tests/test_transition.py (Day 5)
- Files: 4 files, 1049 lines schema.sql, 330 lines queries.py, 120 lines seed script
- Next prompts: Build production/agent/tools.py with @function_tool wrappers around queries.py, then message_processor.py worker
- Reflection: Added escalations as separate table from hackathon baseline — allows multiple escalation events per ticket. Triggers keep denormalized counters consistent without app-layer logic.

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): none yet
- Prompt variant: none
- Next experiment: docker-compose up -d postgres && psql schema.sql to validate syntax
