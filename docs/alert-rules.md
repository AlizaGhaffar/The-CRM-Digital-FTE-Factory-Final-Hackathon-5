# NimbusFlow Customer Success FTE — Alert Runbook

**Source:** `production/k8s/monitoring.yaml` — PrometheusRule `fte-alerts`
**Namespace:** `customer-success-fte`
**Dashboard:** Import `docs/grafana-dashboard.json` into Grafana

This document explains every alert: what it means, when it fires, and exactly
how to respond. Keep this open during the 24-hour Final Challenge test.

---

## How Alerts Are Routed

| Severity | Who Gets Paged | Response Time |
|----------|----------------|---------------|
| `critical` | On-call engineer (PagerDuty) | < 5 minutes |
| `warning`  | Slack `#fte-alerts` channel  | < 30 minutes |

Labels on each alert:
- `team: platform` → infrastructure issues (pods, Kafka, latency)
- `team: product` → agent quality issues (escalation rate, identification)
- `page: "true"` → wakes someone up immediately

---

## Group 1 — HTTP Error Rate (`fte.api.errors`)

### `FTEHighErrorRateWarning`

| Field | Value |
|-------|-------|
| **Condition** | HTTP 5xx error rate > **2 %** for 5 minutes |
| **Severity** | warning |
| **SLO impact** | Uptime SLO at risk (target > 99.9 %) |

**What it means:**
More than 2 in 100 API requests are returning server errors (500–599). This
is usually the first sign of a database connection pool exhaustion, a
dependency timeout, or a bad deployment.

**Investigation steps:**
```bash
# 1. Check which endpoint is throwing errors:
kubectl logs -l app=fte-api -n customer-success-fte --tail=200 | grep "ERROR\|500\|502\|503"

# 2. Check pod health:
kubectl get pods -n customer-success-fte
kubectl describe pod <pod-name> -n customer-success-fte

# 3. Check database connectivity:
kubectl exec -it deploy/fte-api -n customer-success-fte -- \
  python -c "import asyncio; from production.database import queries; asyncio.run(queries.get_pool())"

# 4. Check Kafka producer:
curl https://api.nimbusflow.io/ready
```

**Common causes and fixes:**

| Cause | Fix |
|-------|-----|
| DB connection pool exhausted | Check `max_size=10` in `queries.py`; restart API pods |
| Kafka producer not connected | `kubectl rollout restart deploy/fte-api -n customer-success-fte` |
| OOM on a pod | Check `kubectl top pods`; increase memory limits in `deployment-api.yaml` |
| Bad deployment | `kubectl rollout undo deploy/fte-api -n customer-success-fte` |

---

### `FTEHighErrorRateCritical`

| Field | Value |
|-------|-------|
| **Condition** | HTTP 5xx error rate > **5 %** for 5 minutes |
| **Severity** | critical — pages on-call |
| **Final Challenge** | FAIL if sustained during 24h test |

**What it means:**
1 in 20 requests is failing. At this rate, customers are seeing errors and
webhook deliveries may be timing out. Pub/Sub will retry Gmail webhooks for
up to 7 days, but Twilio only retries 3 times.

**Immediate response:**
```bash
# 1. Roll back last deployment if this started after a deploy:
kubectl rollout history deploy/fte-api -n customer-success-fte
kubectl rollout undo deploy/fte-api -n customer-success-fte

# 2. Scale up to dilute the bad pods:
kubectl scale deploy/fte-api --replicas=6 -n customer-success-fte

# 3. Identify crash-looping pods:
kubectl get pods -n customer-success-fte | grep -v Running

# 4. Tail all API logs simultaneously:
kubectl logs -l app=fte-api -n customer-success-fte -f --prefix=true
```

---

### `FTEWebhookErrors`

| Field | Value |
|-------|-------|
| **Condition** | 5xx rate > 0.1 req/s on any `/webhooks/*` endpoint for 5 minutes |
| **Severity** | warning |
| **Risk** | Message loss — Twilio stops retrying after 3 failures |

**What it means:**
A specific webhook handler (`/webhooks/gmail`, `/webhooks/whatsapp`, or
`/webhooks/whatsapp/status`) is failing. Customer messages published to that
channel are not being queued to Kafka.

**Investigation steps:**
```bash
# Check which webhook is failing:
kubectl logs -l app=fte-api -n customer-success-fte --tail=100 | grep "webhooks"

# Test the webhook manually:
curl -X POST https://api.nimbusflow.io/webhooks/gmail \
  -H "Content-Type: application/json" \
  -d '{"message":{"data":"dGVzdA==","messageId":"test"},"subscription":"test"}'

# Check Twilio webhook errors in Twilio console:
# https://console.twilio.com/us1/monitor/logs/messaging
```

---

## Group 2 — Response Latency (`fte.api.latency`)

### `FTEHighLatencyWarning`

| Field | Value |
|-------|-------|
| **Condition** | P95 latency > **2 seconds** for 5 minutes |
| **Severity** | warning |
| **Final Challenge** | SLO threshold is 3 s — investigate immediately |

**What it means:**
95% of requests are completing within 2 seconds, but the slowest 5% are
taking longer. This is often a sign of LLM API latency spikes or database
query slowdown. The Final Challenge SLO is 3 s — you have 1 second of
headroom.

**Investigation steps:**
```bash
# Check which endpoint is slow (see Grafana "P95 Latency by Endpoint" panel):
# Look for /webhooks/gmail — Gmail API fetch adds latency

# Check LLM API latency:
kubectl logs -l app=fte-worker -n customer-success-fte --tail=100 | grep "latency_ms"

# Check DB slow queries:
psql $DATABASE_URL -c "
  SELECT query, mean_exec_time, calls
  FROM pg_stat_statements
  ORDER BY mean_exec_time DESC
  LIMIT 10;
"
```

---

### `FTEHighLatencyCritical`

| Field | Value |
|-------|-------|
| **Condition** | P95 latency > **3 seconds** for 5 minutes |
| **Severity** | critical — pages on-call |
| **Final Challenge** | FAIL — SLO breach |

**What it means:**
The 24-hour test requires P95 < 3 s across all channels. This alert means
you are actively failing that requirement.

**Immediate response:**
```bash
# 1. Check if Gemini API is slow (most common cause):
kubectl logs -l app=fte-worker -n customer-success-fte --tail=50 | grep "run_agent\|latency"

# 2. Scale worker pods to reduce queue wait time:
kubectl scale deploy/fte-worker --replicas=10 -n customer-success-fte

# 3. Check Kafka consumer lag — if lag is high, messages are waiting:
kubectl exec -it deploy/fte-api -n customer-success-fte -- \
  curl -s http://localhost:8000/metrics | grep kafka_consumer_lag

# 4. Check DB connection pool — if all 10 connections are busy, queries queue:
kubectl logs -l app=fte-api -n customer-success-fte --tail=50 | grep "asyncpg\|pool"
```

---

### `FTEWebhookLatencyHigh`

| Field | Value |
|-------|-------|
| **Condition** | Webhook handler P95 > **25 seconds** for 2 minutes |
| **Severity** | critical |
| **Risk** | Google Pub/Sub delivery timeout is 30 s — duplicate messages possible |

**What it means:**
A webhook handler is taking so long to respond that Pub/Sub or Twilio may
time out and re-deliver the same message. If `/webhooks/gmail` takes > 30 s,
Google will retry and you'll process the same email twice.

**Fix:** The API uses `background_tasks` for Gmail to return 200 immediately.
If this alert fires, check that `background_tasks.add_task()` is working
correctly and the background task itself is not blocking the response.

---

## Group 3 — Kafka Consumer Lag (`fte.kafka.lag`)

### `FTEKafkaConsumerLagWarning`

| Field | Value |
|-------|-------|
| **Condition** | Consumer lag > **500 messages** for 5 minutes |
| **Severity** | warning |
| **Impact** | Customers waiting longer than usual for responses |

**What it means:**
Worker pods are consuming Kafka messages slower than they arrive. 500 messages
of lag at a typical processing rate of 5 msgs/s means ~100 seconds of delay
before new messages are processed.

**Investigation steps:**
```bash
# Check how many worker pods are running:
kubectl get pods -n customer-success-fte -l app=fte-worker

# Check HPA status:
kubectl get hpa fte-worker-hpa -n customer-success-fte

# Manually trigger HPA scale-up:
kubectl patch hpa fte-worker-hpa -n customer-success-fte \
  -p '{"spec":{"minReplicas":6}}'
```

---

### `FTEKafkaConsumerLagCritical`

| Field | Value |
|-------|-------|
| **Condition** | Consumer lag > **1000 messages** for 5 minutes |
| **Severity** | critical — pages on-call |
| **Final Challenge** | Message loss risk — HPA may not scale fast enough |

**What it means:**
1000+ customer messages are waiting to be processed. At peak load this happens
during a chaos pod kill. The worker HPA should auto-scale, but if it hasn't
triggered yet (15-second stabilization window), manual intervention is needed.

**Immediate response:**
```bash
# Emergency: manually scale workers:
kubectl scale deploy/fte-worker --replicas=15 -n customer-success-fte

# Watch the lag drain:
watch kubectl get hpa -n customer-success-fte

# Check if workers are crashing (restart loop):
kubectl get pods -n customer-success-fte -l app=fte-worker

# After recovery, allow HPA to scale back down:
kubectl patch hpa fte-worker-hpa -n customer-success-fte \
  -p '{"spec":{"minReplicas":3}}'
```

---

### `FTEDeadLetterQueueGrowing`

| Field | Value |
|-------|-------|
| **Condition** | DLQ lag increases by > 5 messages in 30 minutes |
| **Severity** | warning |
| **Impact** | Permanent message loss — these messages will not be retried |

**What it means:**
Messages that failed all 3 retry attempts (`WORKER_MAX_RETRIES=3`) are
published to the dead letter queue. They represent customer messages that
were never processed.

**Investigation steps:**
```bash
# Read DLQ messages to understand what's failing:
kafka-console-consumer.sh \
  --bootstrap-server $KAFKA_BOOTSTRAP_SERVERS \
  --topic nimbusflow.messages.dlq \
  --from-beginning \
  --max-messages 10

# Check worker error logs for the exception type:
kubectl logs -l app=fte-worker -n customer-success-fte --tail=200 | grep "handle_error\|DLQ"
```

---

## Group 4 — Pod Health (`fte.pods`)

### `FTEPodDown`

| Field | Value |
|-------|-------|
| **Condition** | Any pod in `Failed` or `Unknown` phase for 2 minutes |
| **Severity** | critical — pages on-call |
| **Final Challenge** | Counts against uptime SLO |

**What it means:**
A pod has crashed and is not recovering. Kubernetes should restart it
automatically, but `Failed` means it won't retry without intervention.

**Immediate response:**
```bash
# Check pod events:
kubectl describe pod <pod-name> -n customer-success-fte | tail -30

# Check exit code (0=success, 1=app error, 137=OOM, 143=SIGTERM):
kubectl get pod <pod-name> -n customer-success-fte -o jsonpath='{.status.containerStatuses[0].lastState.terminated}'

# Delete and let Kubernetes recreate:
kubectl delete pod <pod-name> -n customer-success-fte

# If all pods of a deployment are down:
kubectl rollout restart deploy/fte-api -n customer-success-fte
```

**Exit code reference:**

| Exit Code | Meaning | Fix |
|-----------|---------|-----|
| 0 | Clean exit | Check if `main()` is returning prematurely |
| 1 | App exception | Check logs for Python traceback |
| 137 | OOMKilled (128+9) | Increase memory limits in deployment YAML |
| 143 | SIGTERM (128+15) | `terminationGracePeriodSeconds` too short |

---

### `FTEPodRestartLoop`

| Field | Value |
|-------|-------|
| **Condition** | Container restarts > **3 times** in 15 minutes |
| **Severity** | critical — pages on-call |
| **Pattern** | CrashLoopBackOff |

**What it means:**
A container is crashing and Kubernetes is restarting it with exponential
back-off (10s, 20s, 40s, 80s, 160s...). During chaos kills this is expected
for a brief window. If it continues > 15 minutes, it's a real failure.

**Immediate response:**
```bash
# Check crash reason:
kubectl logs <pod-name> -c <container> -n customer-success-fte --previous

# Most common causes for fte-api:
#   - KAFKA_BOOTSTRAP_SERVERS unreachable (producer fails to start)
#   - Missing environment variable (KeyError on startup)
#   - PostgreSQL connection refused

# Check if this is a startup failure (initContainer issue):
kubectl describe pod <pod-name> -n customer-success-fte | grep -A 5 "Init Containers"
```

---

### `FTEDeploymentReplicasMismatch`

| Field | Value |
|-------|-------|
| **Condition** | Available replicas < desired replicas for 5 minutes |
| **Severity** | warning |
| **Impact** | Reduced capacity; remaining pods carry higher load |

**What it means:**
The deployment wants N pods but fewer are available. This often happens
during a rolling update or after a chaos kill while Kubernetes is scheduling
replacement pods.

```bash
# Check rollout status:
kubectl rollout status deploy/fte-api -n customer-success-fte
kubectl rollout status deploy/fte-worker -n customer-success-fte

# Check node capacity (pods may be Pending due to resource limits):
kubectl describe nodes | grep -A 5 "Allocated resources"
kubectl get events -n customer-success-fte --sort-by='.lastTimestamp' | tail -20
```

---

### `FTEContainerOOMKilled`

| Field | Value |
|-------|-------|
| **Condition** | Container last terminated with reason `OOMKilled` |
| **Severity** | warning |
| **Root cause** | Memory limits set too low for actual workload |

**What it means:**
A container was killed by the Linux OOM killer because it exceeded its memory
limit (`api: 512Mi`, `worker: 1Gi`). During the 24-hour test with large LLM
context windows, workers can exceed 1 Gi.

**Fix:**
```bash
# Check current memory usage:
kubectl top pods -n customer-success-fte

# If workers routinely use > 900 Mi, increase in deployment-worker.yaml:
#   limits.memory: 2Gi
# Then apply:
kubectl apply -f production/k8s/deployment-worker.yaml
kubectl rollout status deploy/fte-worker -n customer-success-fte
```

---

## Group 5 — Business Metrics (`fte.business`)

### `FTEHighEscalationRate` / `FTEEscalationRateWarning`

| Field | Value |
|-------|-------|
| **Warning condition** | Escalation rate > **20 %** for 15 minutes |
| **Critical condition** | Escalation rate > **25 %** for 15 minutes |
| **Critical severity** | pages on-call |
| **Final Challenge** | FAIL at > 25 % |

**What it means:**
The AI agent is escalating too many conversations to human agents. The most
common causes are knowledge base gaps (agent can't find answers) or
sentiment-triggered escalations from a batch of frustrated customers.

**Investigation steps:**
```bash
# Check most common escalation reasons:
psql $DATABASE_URL -c "
  SELECT
    resolution_notes AS reason,
    COUNT(*) AS count
  FROM conversations
  WHERE status = 'escalated'
    AND ended_at > NOW() - INTERVAL '1 hour'
  GROUP BY resolution_notes
  ORDER BY count DESC
  LIMIT 10;
"

# Check if knowledge base is answering queries:
curl https://api.nimbusflow.io/conversations/<recent-escalated-id>
```

**Fixes by root cause:**

| Root cause | Fix |
|------------|-----|
| Knowledge base missing articles | Add content via `production/database/seed_knowledge_base.py` |
| System prompt too aggressive | Loosen escalation triggers in `production/agent/customer_success_agent.py` |
| Spike of angry customers | Check `/metrics/channels` sentiment scores |
| Keyword false positives | Review `ESCALATION_TRIGGERS` constant in agent |

---

### `FTECrossChannelIdentificationDegraded`

| Field | Value |
|-------|-------|
| **Condition** | Cross-channel identification rate < **95 %** for 15 minutes |
| **Severity** | warning |
| **Final Challenge** | Requires > 95 % for pass |

**What it means:**
The system is failing to link customer identities across channels. A customer
who emails first and then sends a WhatsApp message should be recognised as
the same person — if `customer_identifiers` merging is broken, they get
separate records and lose conversation history.

**Investigation steps:**
```bash
# Find customers with multiple unmerged records:
psql $DATABASE_URL -c "
  SELECT email, phone, COUNT(*) AS records
  FROM customers
  GROUP BY email, phone
  HAVING COUNT(*) > 1;
"

# Check customer_identifiers table for recent entries:
psql $DATABASE_URL -c "
  SELECT identifier_type, identifier_value, created_at
  FROM customer_identifiers
  ORDER BY created_at DESC
  LIMIT 20;
"
```

---

### `FTEChannelSilent`

| Field | Value |
|-------|-------|
| **Condition** | Zero messages on any channel for **30 minutes** |
| **Severity** | warning |
| **Risk** | Channel integration broken — silent failure |

**What it means:**
A normally-active channel has gone completely quiet. During the 24-hour test,
any 30-minute silence on a tested channel is suspicious.

**Diagnosis by channel:**

```bash
# Email (Gmail) silent:
# Check Pub/Sub subscription is active:
gcloud pubsub subscriptions describe nimbusflow-gmail-sub
# Re-register Gmail push:
curl -X POST https://api.nimbusflow.io/webhooks/gmail/register

# WhatsApp silent:
# Check Twilio webhook URL in console:
# https://console.twilio.com/us1/develop/phone-numbers/manage/active
# Verify TWILIO_VALIDATE_SIGNATURE=true and secret is correct

# Web form silent:
# Verify form is pointing to correct API URL:
curl https://api.nimbusflow.io/health | jq '.channels.web_form'
```

---

## Quick Reference: Final Challenge Alert Summary

| Alert | Threshold | SLO | Action if fires |
|-------|-----------|-----|-----------------|
| `FTEHighErrorRateCritical` | > 5% for 5m | Uptime > 99.9% | Rollback deployment |
| `FTEHighLatencyCritical` | P95 > 3s for 5m | P95 < 3s | Scale workers, check LLM API |
| `FTEKafkaConsumerLagCritical` | > 1000 msgs for 5m | No message loss | Emergency scale workers |
| `FTEPodDown` | Pod Failed > 2m | Uptime > 99.9% | Delete pod, check logs |
| `FTEPodRestartLoop` | > 3 restarts / 15m | Uptime > 99.9% | Check previous logs |
| `FTEHighEscalationRate` | > 25% for 15m | Escalation < 25% | Expand knowledge base |
| `FTECrossChannelIdentificationDegraded` | < 95% for 15m | Cross-channel > 95% | Check customer_identifiers |

---

## Grafana Dashboard Quick Start

```bash
# 1. Port-forward Grafana:
kubectl port-forward svc/kube-prometheus-grafana -n monitoring 3000:80

# 2. Login (default admin/prom-operator):
open http://localhost:3000

# 3. Import dashboard:
#    Dashboards → Import → Upload JSON file → docs/grafana-dashboard.json

# 4. Select Prometheus datasource and your namespace

# 5. Set time range to "Last 24 hours" for the Final Challenge review
```
