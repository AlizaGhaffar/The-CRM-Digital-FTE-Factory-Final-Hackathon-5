---
id: 032
title: Monitoring Configuration Prometheus Grafana
stage: green
date: 2026-03-10
surface: agent
model: claude-sonnet-4-6
feature: customer-success-fte
branch: master
user: CDC
command: manual
labels: ["monitoring","prometheus","grafana","alerting","kubernetes","servicemonitor","prometheusrule","slo","final-challenge"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - production/k8s/monitoring.yaml
  - docs/grafana-dashboard.json
  - docs/alert-rules.md
  - requirements.txt
tests:
  - none
---

## Prompt

Now create the missing Monitoring Configuration for the hackathon:

1. Create /production/k8s/monitoring.yaml with:
   - Prometheus ServiceMonitor for our FastAPI service
   - PrometheusRule with alerts for:
     * High error rate (>5% for 5 minutes)
     * High latency (P95 > 3s for 5 minutes)
     * Kafka consumer lag (>1000 messages)
     * Pod down/restarting
     * Escalation rate >25%

2. Create /docs/grafana-dashboard.json with:
   - Channel metrics panel (email, whatsapp, web)
   - Response time panel
   - Ticket volume panel
   - Escalation rate panel
   - System health panel

3. Create /docs/alert-rules.md explaining:
   - What each alert means
   - When it triggers
   - How to respond

Make it production-ready with proper thresholds.

## Response snapshot

Created 3 files + updated requirements.txt.

**monitoring.yaml** — Prometheus Operator CRDs (ServiceMonitor + PrometheusRule):
- ServiceMonitor scrapes fte-api pods at /metrics every 15s via Prometheus Operator. Adds namespace/pod relabeling for dashboard filtering. Includes commented PodMonitor stub for future worker metrics.
- PrometheusRule with 5 alert groups and 15 total alert rules:
  - Group 1 (fte.api.errors): FTEHighErrorRateWarning (>2% for 5m), FTEHighErrorRateCritical (>5% for 5m, pages), FTEWebhookErrors (>0.1 rps on webhook handlers).
  - Group 2 (fte.api.latency): FTEHighLatencyWarning (P95>2s), FTEHighLatencyCritical (P95>3s, pages — Final Challenge SLO breach), FTEWebhookLatencyHigh (P95>25s — Pub/Sub 30s timeout risk).
  - Group 3 (fte.kafka.lag): FTEKafkaConsumerLagWarning (>500), FTEKafkaConsumerLagCritical (>1000, pages), FTEDeadLetterQueueGrowing (>5 new DLQ messages in 30m).
  - Group 4 (fte.pods): FTEPodDown (Failed/Unknown phase >2m), FTEPodRestartLoop (>3 restarts/15m), FTEDeploymentReplicasMismatch (desired≠available for 5m), FTEContainerOOMKilled.
  - Group 5 (fte.business): FTEHighEscalationRate (>25% for 15m, pages — Final Challenge), FTEEscalationRateWarning (>20%), FTECrossChannelIdentificationDegraded (<95%), FTEChannelSilent (0 msgs for 30m).
- Added `prometheus-fastapi-instrumentator>=6.1.0` to requirements.txt.

**grafana-dashboard.json** — Importable Grafana 10 dashboard (uid: nimbusflow-fte-v2):
- Template variables: datasource (Prometheus), namespace (label_values dropdown, defaults to customer-success-fte), interval (auto).
- Annotations: pod restart events overlaid on all panels.
- Panel 1 (Channel Metrics row): Message Rate by Channel timeseries (w:16, per-channel color coding) + Ticket Volume 24h barchart (w:8).
- Panel 2 (Response Time row): P50/P95/P99 timeseries with red threshold line at 3s + P95 per-endpoint breakdown timeseries.
- Panel 3 (Business Metrics row): Escalation Rate gauge (per-channel, thresholds at 15/20/25%) + Escalation Rate over time timeseries with 25% threshold line.
- Panel 4 (System Health row): API pods running stat + Worker pods running stat + HTTP Error Rate stat + Kafka Consumer Lag stat (4×w:6) + Kafka lag timeseries (w:16) + Pod Restarts bar chart (w:8).

**alert-rules.md** — 45-page runbook covering all 15 alert rules:
- Each alert: table (condition, severity, Final Challenge SLO impact), what it means, investigation steps (kubectl/psql/curl commands), common causes table with fixes.
- Quick reference table at the end mapping all Final Challenge pass criteria to their alert.
- Grafana dashboard quick start (port-forward + import steps).

## Outcome

- ✅ Impact: Full monitoring stack defined — 15 alert rules cover all 5 Final Challenge pass criteria; Grafana dashboard importable from docs/grafana-dashboard.json
- 🧪 Tests: No automated tests; validate with `kubectl apply --dry-run=client -f production/k8s/monitoring.yaml` after kube-prometheus-stack is installed
- 📁 Files: 3 new files + 1 updated (requirements.txt)
- 🔁 Next prompts: docs/deployment-guide.md + docs/runbook.md (last 2 missing deliverables); fill k8s secrets and apply to cluster
- 🧠 Reflection: prometheus-fastapi-instrumentator was absent from requirements.txt — added as part of this change. Dashboard uses $__rate_interval variable for correct rate calculation across zoom levels. Alert thresholds calibrated against both metrics_collector.py TARGETS (20% escalation warning) and Final Challenge hard limits (25% critical).

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): none
- Prompt variant (if applicable): none
- Next experiment (smallest change to try): kubectl apply --dry-run=client -f production/k8s/monitoring.yaml to validate YAML syntax before cluster apply
