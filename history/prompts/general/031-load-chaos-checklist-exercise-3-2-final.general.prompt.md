---
id: 031
title: Load Chaos Checklist Exercise 3.2 Final
stage: green
date: 2026-03-10
surface: agent
model: claude-sonnet-4-6
feature: customer-success-fte
branch: master
user: CDC
command: manual
labels: ["locust","load-testing","chaos-engineering","kubernetes","24h-test","exercise-3-2","final-challenge","uptime","p95","message-loss"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - production/tests/load_test.py
  - production/tests/chaos_test.py
  - production/tests/checklist_24h.md
tests:
  - production/tests/load_test.py
  - production/tests/chaos_test.py
---

## Prompt

Following Exercise 3.2 and Final Challenge:

1. Create /production/tests/load_test.py with Locust:
   - WebFormUser (simulate form submissions)
   - HealthCheckUser (monitor during load)

2. Create /production/tests/chaos_test.py:
   - Random pod kill every 2 hours
   - Verify system recovers
   - Check no message loss

3. Create 24-hour test validation checklist:
   - Uptime > 99.9%
   - P95 latency < 3 seconds (all channels)
   - Escalation rate < 25%
   - Cross-channel identification > 95%
   - No message loss

## Response snapshot

Created all 3 files for Exercise 3.2 and the Final Challenge.

**load_test.py** — Two Locust user classes expanded from document stubs:
- `WebFormUser` (weight=3, wait=2-10s): 4 tasks — `submit_support_form` (weight 6), `submit_high_priority_form` (weight 1, keyword-triggered triage), `check_ticket_status` (weight 2, polls submitted ticket IDs), `lookup_own_customer` (weight 1). Shared `_submitted_ticket_ids` list populated at runtime so ticket-status task has real IDs to poll. Module-level test data pools for names/emails/domains/subjects/messages ensure varied payloads.
- `HealthCheckUser` (weight=1, wait=5-15s): 3 tasks — `check_health`, `check_metrics` (validates `channels` key in response), `check_readiness` (accepts 503 during chaos kills). Locust `@events.test_stop` hook prints pass/fail against P95 < 3000ms and failure rate < 0.1%.

**chaos_test.py** — `ChaosEngine` class + 5 pytest tests:
- `_k8s_client()`: auto-detects in-cluster vs kubeconfig; `pytest.skip()` when no cluster available.
- `kill_random_pod()`: lists Running+Ready pods matching `app=fte-api` or `app=fte-worker`, deletes with `grace_period_seconds=0`.
- `wait_for_recovery()`: polls GET /health every 5s, tracks consecutive failures, returns `RecoveryResult` with elapsed time.
- `get_message_counts()`: prefers direct asyncpg DB query (when `CHAOS_DB_DSN` set), falls back to `/metrics/channels` API.
- `ChaosEngine.run()`: orchestrates KILL_CYCLES (default 12) × KILL_INTERVAL_S (default 7200s) cycles with message count snapshots before/after each kill.
- Tests: `test_single_kill_and_recovery` (smoke), `test_api_pod_kill_and_recovery`, `test_worker_pod_kill_does_not_affect_api`, `test_no_message_loss_after_single_kill`, `test_24h_chaos_run` (full 24h, marked `@pytest.mark.slow`).

**checklist_24h.md** — Fillable validation checklist with:
- Pre-test setup steps (kubectl, secrets, cert-manager, health/ready probes)
- Traffic targets table (web form 100+, email 50+, WhatsApp 50+, cross-channel 10+, chaos kills 12)
- Per-threshold sections with formula, measurement commands (bash/psql/kafka-tools), and fillable result fields
- 12-row chaos kill results table
- HPA scaling validation checkboxes
- Final sign-off table with overall PASS/FAIL declaration

## Outcome

- ✅ Impact: Exercise 3.2 + Final Challenge fully implemented — load test, chaos engine, and 24h validation checklist ready for deployment run
- 🧪 Tests: locust -f production/tests/load_test.py --headless --users 20 --run-time 24h | pytest production/tests/chaos_test.py -v -s
- 📁 Files: 3 new files — production/tests/load_test.py, production/tests/chaos_test.py, production/tests/checklist_24h.md
- 🔁 Next prompts: Fill secrets in k8s/secrets.yaml; apply manifests to cluster; run load + chaos tests; complete checklist_24h.md; submit Stage 3 deliverables
- 🧠 Reflection: Document stub for Exercise 3.2 gave only 8 lines of skeleton code; expanded WebFormUser with 4 weighted tasks (including high-priority triage path), HealthCheckUser with readiness probe check, and full Locust event hooks. Chaos test required inference of k8s client patterns, DB count verification, and recovery polling strategy — none present in the document.

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): none
- Prompt variant (if applicable): none
- Next experiment (smallest change to try): locust -f production/tests/load_test.py --host http://localhost:8000 --users 5 --spawn-rate 1 --run-time 60s --headless to verify load_test.py runs without import errors
