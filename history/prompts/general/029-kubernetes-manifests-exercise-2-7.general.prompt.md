---
id: 029
title: Kubernetes Manifests Exercise 2.7
stage: green
date: 2026-03-10
surface: agent
model: claude-sonnet-4-6
feature: customer-success-fte
branch: master
user: CDC
command: manual
labels: ["kubernetes","k8s","deployment","hpa","ingress","tls","exercise-2-7","production"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - production/k8s/namespace.yaml
  - production/k8s/configmap.yaml
  - production/k8s/secrets.yaml
  - production/k8s/deployment-api.yaml
  - production/k8s/deployment-worker.yaml
  - production/k8s/service.yaml
  - production/k8s/ingress.yaml
  - production/k8s/hpa.yaml
tests:
  - none
---

## Prompt

Following Exercise 2.7, create all Kubernetes manifests:

/production/k8s/ with:
1. namespace.yaml
2. configmap.yaml
3. secrets.yaml (placeholders)
4. deployment-api.yaml (with health checks)
5. deployment-worker.yaml
6. service.yaml
7. ingress.yaml (with TLS)
8. hpa.yaml (auto-scaling)

Follow document examples exactly.

## Response snapshot

Created all 8 Kubernetes manifests in `production/k8s/` for the `customer-success-fte` namespace.

Key decisions:
- **namespace.yaml**: `customer-success-fte` namespace with standard labels
- **configmap.yaml**: All non-secret env vars (Postgres host/port/db/user, Kafka bootstrap, group IDs for API vs worker, Twilio number, Gmail/Pub/Sub config, CORS origins, model name). Secrets excluded.
- **secrets.yaml**: Two Secret objects — `fte-secrets` (Postgres pw, Gemini, OpenAI, Twilio credentials as base64 opaque) and `fte-gmail-secrets` (gmail_credentials.json + gmail_token.json mounted as files). All values are `REPLACE_ME` placeholders with encoding instructions.
- **deployment-api.yaml**: 3 replicas, `uvicorn production.api.main:app --workers 2`, initContainers wait for Postgres + Kafka via netcat, liveness on `/health`, readiness on `/ready`, startupProbe with 60s window, `maxSurge=1 maxUnavailable=0` (zero-downtime rolling), Gmail secret volume mounted at `/app/secrets`, resources request=100m/256Mi limit=500m/512Mi.
- **deployment-worker.yaml**: 3 replicas, `python -m production.workers.message_processor`, same initContainers, exec liveness probe (no HTTP port), `terminationGracePeriodSeconds=60` (in-flight agent runs), resources request=200m/512Mi limit=1000m/1Gi.
- **service.yaml**: ClusterIP on port 80→8000, selector `app: fte-api`.
- **ingress.yaml**: Nginx ingress, cert-manager TLS (`letsencrypt-prod` cluster issuer), path-based routing for /webhooks, /support, /conversations, /customers, /metrics, /health, /ready. Security headers snippet, rate limiting (50 rps), 8m body limit for webhook payloads.
- **hpa.yaml**: autoscaling/v2 with CPU+memory metrics. API: min=3 max=20 CPU=70%. Worker: min=3 max=30 CPU=70%. Both have scaleUp/scaleDown stabilization windows (30s/300s API, 15s/600s worker) and per-event pod limits to prevent flapping.

## Outcome

- ✅ Impact: All 8 Exercise 2.7 manifests created; deployment ready for `kubectl apply -f production/k8s/` after substituting secrets and domain names
- 🧪 Tests: None run; validate with `kubectl dry-run --client -f production/k8s/`
- 📁 Files: 8 new files in production/k8s/
- 🔁 Next prompts: Exercise 3.1 multi-channel E2E tests; fill secrets and apply to cluster; set up cert-manager ClusterIssuer
- 🧠 Reflection: Document gave only a list of what to create with no YAML examples; derived all specs from Dockerfile (image structure, port 8000, non-root user 1000), docker-compose.yml (env vars, command lines), and standard k8s production patterns (autoscaling/v2, initContainers, security contexts, rolling update strategy)

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): none
- Prompt variant (if applicable): none
- Next experiment (smallest change to try): kubectl apply --dry-run=client to validate all YAML syntax
