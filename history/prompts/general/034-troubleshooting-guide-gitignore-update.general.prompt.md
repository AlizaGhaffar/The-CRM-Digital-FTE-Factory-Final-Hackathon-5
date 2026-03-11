---
id: 034
title: Troubleshooting Guide and Gitignore Update
stage: green
date: 2026-03-11
surface: agent
model: claude-sonnet-4-6
feature: none
branch: master
user: CDC
command: manual
labels: ["documentation","troubleshooting","gitignore","local-dev","credentials","kafka","postgres","docker-compose"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - docs/troubleshooting.md
  - .gitignore
tests:
  - none
---

## Prompt

Continue from where we left off — create docs/troubleshooting.md, update .gitignore, and create PHR 034.

## Response snapshot

Created `docs/troubleshooting.md` (7 sections, ~200 lines):
- §1 Docker Compose / Local Setup — 5 issues: container exits immediately (missing .env/secrets), postgres never healthy, kafka never healthy, port conflicts, stale schema volume
- §2 API Credential Issues — 5 issues: Gemini 401/429, Gmail not receiving (OAuth/Pub/Sub/watch), Twilio sandbox join requirement, missing gmail-credentials.json
- §3 Database Issues — 4 issues: InvalidPasswordError, missing relations, pgvector missing, direct psql access
- §4 Kafka Issues — 3 issues: NoBrokersAvailable (inside vs outside Docker), missing topics, DLQ accumulating
- §5 Frontend Issues — 3 issues: CORS error, WebSocket disconnected, node_modules not found
- §6 Common Error Messages — quick-reference table mapping 11 error strings to causes and fixes
- §7 Getting Help — escalation path

Updated `.gitignore`:
- Added `secrets-real.yaml` — prevents the real secrets YAML from being committed (`.example` variant is safe to track)
- Added `*.real.yaml` — catch-all for any other `*.real.yaml` files
- Added `*.real.env` — catch-all for any real env variants

## Outcome

- ✅ Impact: Developer onboarding gap closed — troubleshooting.md complements runbook.md (production incidents) and environment-setup.md (credential acquisition) with local dev fixes; gitignore updated to prevent accidental secrets commit
- 🧪 Tests: None automated; all commands validated against docker-compose.yml service names (fte_api, fte_worker, fte_postgres, fte_kafka), .env.example keys, and known secrets paths
- 📁 Files: docs/troubleshooting.md (new), .gitignore (updated), history/prompts/general/034-troubleshooting-guide-gitignore-update.general.prompt.md (new)
- 🔁 Next prompts: Documentation suite is complete (deployment-guide, runbook, environment-setup, troubleshooting); next step is running the 24h Final Challenge or committing and opening a PR
- 🧠 Reflection: Troubleshooting content derived entirely from actual docker-compose.yml service names, .env.example variable names, and known error patterns — no generic placeholders

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): none
- Prompt variant (if applicable): none
- Next experiment (smallest change to try): Run `docker-compose up -d` on a clean checkout and verify the §1 fixes resolve the actual errors
