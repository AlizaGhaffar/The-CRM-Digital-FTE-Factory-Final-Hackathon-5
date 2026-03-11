# NimbusFlow Customer Success FTE — Incident Runbook

**System:** Customer Success FTE (AI Employee)
**Namespace:** `customer-success-fte`
**On-call escalation:** Check PagerDuty → `#fte-incidents` Slack channel
**Dashboard:** `kubectl port-forward svc/kube-prometheus-grafana -n monitoring 3000:80` → import `docs/grafana-dashboard.json`
**Alert source:** `production/k8s/monitoring.yaml` (PrometheusRule `fte-alerts`)

---

## Severity Levels

| Level | Definition | Response time | Examples |
|-------|------------|--------------|---------|
| P1 — Critical | System down or data loss | < 5 minutes | All API pods down, DB unreachable, message loss |
| P2 — High | Degraded service | < 15 minutes | Error rate > 5%, P95 > 3s, Kafka lag > 1000 |
| P3 — Medium | Partial impact | < 30 minutes | Single pod restarting, escalation rate warning |
| P4 — Low | Informational | Next business day | Config drift, DLQ messages, OOM warning |

---

## Incident Response Checklist (All Incidents)

```
1. □ Acknowledge alert in PagerDuty / Slack
2. □ Open Grafana dashboard (see URL above)
3. □ Run: kubectl get pods -n customer-success-fte
4. □ Identify the incident type (use sections below)
5. □ Follow the resolution steps for that type
6. □ Verify recovery: curl https://api.nimbusflow.io/health
7. □ Write incident summary in #fte-incidents (what happened, what was done, follow-up)
```

---

## Incident Type 1: Pod CrashLoopBackOff

**Triggered by:** Alerts `FTEPodRestartLoop`, `FTEPodDown`

### Symptoms

- `kubectl get pods -n customer-success-fte` shows `CrashLoopBackOff` or `Error` in STATUS column
- Pod RESTARTS counter is climbing (> 3)
- API requests may be returning 503 if enough pods are affected
- Worker Kafka lag may be growing while pods are unavailable

```
NAME                          READY   STATUS             RESTARTS   AGE
fte-api-7d4f9b8c-xkl9p        0/1     CrashLoopBackOff   5          8m
fte-worker-5c8b4f6d-rmn2k     0/1     Error              3          6m
```

### Investigation Steps

```bash
# Step 1: Which pods are crashing?
kubectl get pods -n customer-success-fte | grep -v Running

# Step 2: Read the crash logs (--previous shows the last crashed container):
kubectl logs <pod-name> -n customer-success-fte --previous

# Example for API pod:
kubectl logs -l app=fte-api -n customer-success-fte --previous --tail=100

# Step 3: Check pod events for the root cause:
kubectl describe pod <pod-name> -n customer-success-fte | tail -30
# Look at "Events:" section — errors like "Back-off restarting failed container"

# Step 4: Check the exit code:
kubectl get pod <pod-name> -n customer-success-fte \
  -o jsonpath='{.status.containerStatuses[0].lastState.terminated}' | jq .
# "exitCode": 1  → Python exception on startup
# "exitCode": 137 → OOMKilled (memory limit exceeded)
# "exitCode": 143 → SIGTERM (terminationGracePeriodSeconds too short)

# Step 5: Check whether initContainers are stuck (DB or Kafka not ready):
kubectl describe pod <pod-name> -n customer-success-fte | grep -A 10 "Init Containers"
kubectl logs <pod-name> -c wait-for-postgres -n customer-success-fte
kubectl logs <pod-name> -c wait-for-kafka -n customer-success-fte
```

### Common causes and resolution

#### Cause A: Missing or wrong environment variable (exitCode 1)

**Log signature:**
```
KeyError: 'GEMINI_API_KEY'
```
or
```
pydantic_core._pydantic_core.ValidationError: ...
```

**Fix:**
```bash
# Verify the secret exists and has the right keys:
kubectl get secret fte-secrets -n customer-success-fte \
  -o jsonpath='{.data}' | jq 'keys'
# Expected: ["GEMINI_API_KEY","OPENAI_API_KEY","POSTGRES_PASSWORD","TWILIO_ACCOUNT_SID","TWILIO_AUTH_TOKEN"]

# If a key is missing, recreate the secret:
kubectl create secret generic fte-secrets \
  --namespace customer-success-fte \
  --from-literal=POSTGRES_PASSWORD="..." \
  --from-literal=GEMINI_API_KEY="..." \
  --from-literal=OPENAI_API_KEY="..." \
  --from-literal=TWILIO_ACCOUNT_SID="..." \
  --from-literal=TWILIO_AUTH_TOKEN="..." \
  --dry-run=client -o yaml | kubectl apply -f -

# Restart pods to pick up the fixed secret:
kubectl rollout restart deployment/fte-api deployment/fte-worker \
  -n customer-success-fte
```

#### Cause B: Database connection refused (initContainer stuck)

**Log signature (wait-for-postgres container):**
```
Waiting for PostgreSQL...
Waiting for PostgreSQL...
```

**Fix:**
```bash
# Check PostgreSQL pod is running:
kubectl get pods -n customer-success-fte | grep postgres

# If PostgreSQL is down, check its logs:
kubectl logs -l app.kubernetes.io/name=postgresql -n customer-success-fte --tail=50

# Check the POSTGRES_HOST value in ConfigMap:
kubectl get configmap fte-config -n customer-success-fte -o yaml | grep POSTGRES_HOST
# Should be: postgres-postgresql.customer-success-fte.svc.cluster.local

# Test connectivity from a debug pod:
kubectl run debug --image=busybox --restart=Never -n customer-success-fte -- \
  nc -zv postgres-postgresql.customer-success-fte.svc.cluster.local 5432
kubectl logs debug -n customer-success-fte
kubectl delete pod debug -n customer-success-fte
```

#### Cause C: OOMKilled (exitCode 137)

**Fix:**
```bash
# Check current memory usage:
kubectl top pods -n customer-success-fte

# If workers are regularly using > 900Mi, increase memory limit:
kubectl patch deployment fte-worker -n customer-success-fte \
  --type='json' \
  -p='[{"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/memory","value":"2Gi"}]'

# If API pods are OOMKilling, increase API memory:
kubectl patch deployment fte-api -n customer-success-fte \
  --type='json' \
  -p='[{"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/memory","value":"1Gi"}]'
```

#### Cause D: Bad deployment (new image fails to start)

**Fix:**
```bash
# Immediate rollback to previous working version:
kubectl rollout undo deployment/fte-api -n customer-success-fte
kubectl rollout undo deployment/fte-worker -n customer-success-fte

# Watch rollback progress:
kubectl rollout status deployment/fte-api -n customer-success-fte

# Verify:
kubectl get pods -n customer-success-fte
curl https://api.nimbusflow.io/health
```

### Recovery verification

```bash
kubectl get pods -n customer-success-fte
# All pods Running, RESTARTS stable

curl https://api.nimbusflow.io/ready
# HTTP 200

kubectl get hpa -n customer-success-fte
# REPLICAS = 3 (or higher if under load)
```

---

## Incident Type 2: Kafka Consumer Lag

**Triggered by:** Alerts `FTEKafkaConsumerLagWarning` (> 500), `FTEKafkaConsumerLagCritical` (> 1000)

### Symptoms

- Customer messages are being received but agents are not responding within 3 seconds
- Grafana "Kafka Consumer Lag" stat panel shows orange/red
- Worker pods may show high CPU on `kubectl top pods`
- No DLQ growth (messages are being processed, just slowly)

### Investigation Steps

```bash
# Step 1: Check current lag across all consumer groups:
kubectl exec -it kafka-0 -n customer-success-fte -- \
  kafka-consumer-groups \
    --bootstrap-server localhost:9092 \
    --describe \
    --group fte-worker

# Expected output:
# GROUP       TOPIC                          PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG
# fte-worker  nimbusflow.messages.email      0          1250            1250            0
# fte-worker  nimbusflow.messages.whatsapp   0          890             890             0
# fte-worker  nimbusflow.messages.web_form   0          340             340             0
#
# If LAG column shows large numbers (> 500), proceed to resolution.

# Step 2: Check how many worker pods are running:
kubectl get pods -n customer-success-fte -l app=fte-worker

# Step 3: Check HPA — is it scaling?
kubectl get hpa fte-worker-hpa -n customer-success-fte -w
# If TARGETS is unknown or REPLICAS is stuck at 3, HPA may not be functioning

# Step 4: Check worker processing rate from logs:
kubectl logs -l app=fte-worker -n customer-success-fte --tail=50 | grep "Processed"
# Look for: "Processed email message in XXXms" — if latency is > 10s, LLM API may be slow

# Step 5: Check if a specific topic has all the lag:
kubectl exec -it kafka-0 -n customer-success-fte -- \
  kafka-consumer-groups \
    --bootstrap-server localhost:9092 \
    --describe \
    --all-groups | grep fte-
```

### Resolution Steps

#### Resolution A: Auto-scaling not responding fast enough — manual scale

```bash
# Emergency scale-up (bypasses HPA stabilization window):
kubectl scale deployment fte-worker \
  --replicas=10 \
  -n customer-success-fte

# Watch lag drain (run in separate terminal):
watch -n 5 "kubectl exec -it kafka-0 -n customer-success-fte -- \
  kafka-consumer-groups --bootstrap-server localhost:9092 \
  --describe --group fte-worker 2>/dev/null | grep -v TOPIC"

# Once lag drops to < 100, allow HPA to take over again:
kubectl scale deployment fte-worker \
  --replicas=3 \
  -n customer-success-fte
# HPA will scale up if needed based on CPU metrics
```

#### Resolution B: Worker pods are crashing (lag + restarts)

Workers may be consuming messages, failing, and not committing offsets.

```bash
# Check worker logs for processing errors:
kubectl logs -l app=fte-worker -n customer-success-fte --tail=200 | \
  grep -E "ERROR|handle_error|DLQ"

# If workers are stuck in retry loops, restart them:
kubectl rollout restart deployment/fte-worker -n customer-success-fte

# Monitor restart recovery:
kubectl rollout status deployment/fte-worker -n customer-success-fte
```

#### Resolution C: Kafka consumer needs to be reset (rarely needed)

Only do this if you want to skip unprocessable messages. **Data will not be processed.**

```bash
# ⚠ DESTRUCTIVE — only if messages are unprocessable (e.g., schema change)
# Reset consumer group offset to latest (skips unprocessed messages):
kubectl exec -it kafka-0 -n customer-success-fte -- \
  kafka-consumer-groups \
    --bootstrap-server localhost:9092 \
    --group fte-worker \
    --topic nimbusflow.messages.email \
    --reset-offsets \
    --to-latest \
    --execute

# Restart workers to resume consuming from latest:
kubectl rollout restart deployment/fte-worker -n customer-success-fte
```

#### Resolution D: Lag during chaos kill (expected, monitor recovery)

During the 24-hour chaos test, pod kills will cause temporary lag.

```bash
# Check when the pod was killed:
kubectl get events -n customer-success-fte \
  --sort-by='.lastTimestamp' | grep -E "Killing|Killed" | tail -5

# Verify new pod is up and consuming:
kubectl get pods -n customer-success-fte -l app=fte-worker

# The lag should drain within RECOVERY_TIMEOUT_S (60s by default).
# If it doesn't drain after 5 minutes, escalate to Resolution A above.
```

### Recovery verification

```bash
kubectl exec -it kafka-0 -n customer-success-fte -- \
  kafka-consumer-groups \
    --bootstrap-server localhost:9092 \
    --describe \
    --group fte-worker

# All LAG values should be < 50 (near-zero)
```

---

## Incident Type 3: Database Connection Issues

**Triggered by:** Alert `FTEDeploymentReplicasMismatch`, pods failing readiness probe (`GET /ready` returns 503), or application errors containing `asyncpg`.

### Symptoms

- `GET /ready` returns 503
- API logs contain: `asyncpg.exceptions.TooManyConnectionsError` or `asyncpg.exceptions.CannotConnectNowError`
- All API/worker pods show READY `0/1`
- `GET /health` still returns 200 (it doesn't test DB), but `/ready` is 503

### Investigation Steps

```bash
# Step 1: Check readiness probe:
kubectl port-forward svc/fte-api -n customer-success-fte 8000:80
curl -v http://localhost:8000/ready

# Step 2: Check PostgreSQL pod status:
kubectl get pods -n customer-success-fte | grep postgres

# Step 3: Check PostgreSQL logs:
kubectl logs -l app.kubernetes.io/name=postgresql -n customer-success-fte --tail=100

# Step 4: Test direct DB connection from inside the cluster:
kubectl run psql-debug \
  --image=postgres:16 \
  --restart=Never \
  --namespace=customer-success-fte \
  --env="PGPASSWORD=$(kubectl get secret fte-secrets -n customer-success-fte \
    -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 -d)" \
  -- psql \
    -h postgres-postgresql.customer-success-fte.svc.cluster.local \
    -U fte_user \
    -d fte_db \
    -c "SELECT COUNT(*) FROM messages;"

kubectl logs psql-debug -n customer-success-fte
kubectl delete pod psql-debug -n customer-success-fte

# Step 5: Check active DB connections (run from psql-debug or locally):
psql $DATABASE_URL -c "
  SELECT state, count(*) AS count
  FROM pg_stat_activity
  WHERE datname = 'fte_db'
  GROUP BY state;
"
# If count WHERE state='idle' is near max_connections, the pool is exhausted.

# Step 6: Check max_connections setting:
psql $DATABASE_URL -c "SHOW max_connections;"

# Step 7: Check connection pool settings in the application:
# production/database/queries.py — max_size=10
# With 3 API pods + 3 worker pods = 6 pods × 10 connections = 60 total.
# PostgreSQL default max_connections=100, so this should be fine.
```

### Resolution Steps

#### Resolution A: PostgreSQL pod is down — restart it

```bash
kubectl delete pod -l app.kubernetes.io/name=postgresql -n customer-success-fte
# Kubernetes will recreate it immediately

# Wait for it to be ready:
kubectl wait --namespace customer-success-fte \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/name=postgresql \
  --timeout=120s

# Restart API and worker to re-establish connection pool:
kubectl rollout restart deployment/fte-api deployment/fte-worker \
  -n customer-success-fte
```

#### Resolution B: Connection pool exhausted

**Symptom:** `asyncpg.exceptions.TooManyConnectionsError` in logs.

```bash
# Terminate idle connections that are hogging slots:
psql $DATABASE_URL -c "
  SELECT pg_terminate_backend(pid)
  FROM pg_stat_activity
  WHERE datname = 'fte_db'
    AND state = 'idle'
    AND query_start < NOW() - INTERVAL '5 minutes';
"

# If pool is consistently exhausted, reduce max_size per pod
# (edit production/database/queries.py, rebuild, redeploy):
# max_size=5 reduces total from 60 to 30 connections

# Alternatively, increase PostgreSQL max_connections:
kubectl exec -it postgres-postgresql-0 -n customer-success-fte -- \
  psql -U fte_user -d fte_db -c "ALTER SYSTEM SET max_connections = 200;"

kubectl delete pod postgres-postgresql-0 -n customer-success-fte
# PostgreSQL will restart with new setting
```

#### Resolution C: Wrong password / secret rotation

**Symptom:** `asyncpg.exceptions.InvalidPasswordError` in logs.

```bash
# Verify the secret value matches the PostgreSQL password:
kubectl get secret fte-secrets -n customer-success-fte \
  -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 -d
# Compare with what PostgreSQL was initialized with

# If they don't match, update the secret:
kubectl patch secret fte-secrets -n customer-success-fte \
  -p "{\"data\":{\"POSTGRES_PASSWORD\":\"$(echo -n 'correct-password' | base64)\"}}"

# Restart pods to use new secret:
kubectl rollout restart deployment/fte-api deployment/fte-worker \
  -n customer-success-fte
```

#### Resolution D: Schema migration needed

**Symptom:** `asyncpg.exceptions.UndefinedTableError: relation "..." does not exist`

```bash
# Apply the schema manually:
kubectl run migrate \
  --image=nimbusflow/customer-success-fte:latest \
  --restart=Never \
  --namespace=customer-success-fte \
  -- psql \
    -h postgres-postgresql.customer-success-fte.svc.cluster.local \
    -U fte_user \
    -d fte_db \
    -f production/database/schema.sql

kubectl logs migrate -n customer-success-fte
kubectl delete pod migrate -n customer-success-fte
```

### Recovery verification

```bash
curl https://api.nimbusflow.io/ready
# HTTP 200

kubectl get pods -n customer-success-fte
# All 1/1 Running

psql $DATABASE_URL -c "SELECT COUNT(*) FROM messages;"
# Returns a number (not an error)
```

---

## Incident Type 4: High Escalation Rate

**Triggered by:** Alert `FTEEscalationRateWarning` (> 20%) or `FTEHighEscalationRate` (> 25%)

### Symptoms

- `GET /metrics/channels` shows `escalation_rate` > 0.20 on one or more channels
- Support team is receiving more human escalation requests than usual
- Grafana "Escalation Rate by Channel" gauge is yellow/orange/red
- Customer satisfaction may be declining

### Investigation Steps

```bash
# Step 1: Get current escalation rate by channel:
curl -s https://api.nimbusflow.io/metrics/channels | jq '.channels[] | {channel, escalation_rate}'

# Step 2: Find the most common escalation reasons in the last hour:
psql $DATABASE_URL -c "
  SELECT
    resolution_notes AS reason,
    initial_channel  AS channel,
    COUNT(*)         AS count
  FROM conversations
  WHERE status = 'escalated'
    AND ended_at > NOW() - INTERVAL '1 hour'
  GROUP BY resolution_notes, initial_channel
  ORDER BY count DESC
  LIMIT 15;
"

# Step 3: Check if a specific keyword is triggering false escalations:
psql $DATABASE_URL -c "
  SELECT m.content, c.status, c.initial_channel
  FROM messages m
  JOIN conversations c ON m.conversation_id = c.id
  WHERE c.status = 'escalated'
    AND m.role = 'customer'
    AND m.created_at > NOW() - INTERVAL '1 hour'
  ORDER BY m.created_at DESC
  LIMIT 10;
"

# Step 4: Check knowledge base coverage for the topics that are escalating:
psql $DATABASE_URL -c "
  SELECT category, COUNT(*) AS articles
  FROM knowledge_base
  GROUP BY category
  ORDER BY articles;
"
# If a category has very few articles, the agent can't find answers → escalates

# Step 5: Check if sentiment is driving escalations (angry customers):
psql $DATABASE_URL -c "
  SELECT
    AVG(sentiment_score) AS avg_sentiment,
    COUNT(*) FILTER (WHERE sentiment_score < 0.3) AS very_negative,
    COUNT(*) AS total
  FROM conversations
  WHERE created_at > NOW() - INTERVAL '1 hour';
"
```

### Resolution Steps

#### Resolution A: Knowledge base gap — agent can't find answers

**Identified by:** reason = `cannot_find_information` or `knowledge_base_empty_result` in DB

```bash
# Find what topics customers are asking about in escalated conversations:
psql $DATABASE_URL -c "
  SELECT m.content
  FROM messages m
  JOIN conversations c ON m.conversation_id = c.id
  WHERE c.status = 'escalated'
    AND m.role = 'customer'
    AND m.created_at > NOW() - INTERVAL '24 hours'
  ORDER BY m.created_at DESC
  LIMIT 20;
"

# Add missing articles to knowledge base:
psql $DATABASE_URL -c "
  INSERT INTO knowledge_base (title, content, category)
  VALUES (
    'How to reset your password',
    'To reset your password: 1. Go to login page. 2. Click Forgot Password...',
    'account'
  );
"

# Or use the seed script to bulk-add articles:
kubectl exec -it deploy/fte-api -n customer-success-fte -- \
  python production/database/seed_knowledge_base.py
```

#### Resolution B: Escalation trigger too sensitive — false positives

**Identified by:** reason = `keyword_match` with benign keywords like "legal pad" or "agent fee"

```bash
# Review the current escalation triggers in the agent:
grep -n "ESCALATION_TRIGGERS\|escalate_to_human\|legal\|sue\|lawyer" \
  production/agent/customer_success_agent.py

# If keywords are too broad, tighten them in the system prompt.
# Then rebuild and redeploy:
docker build --target production -t $REGISTRY/customer-success-fte:latest .
docker push $REGISTRY/customer-success-fte:latest
kubectl rollout restart deployment/fte-api deployment/fte-worker \
  -n customer-success-fte
```

#### Resolution C: Wave of frustrated customers (sentiment < 0.3)

**Identified by:** many escalations with reason = `low_sentiment`

This is a product/customer-success problem, not an infrastructure issue.

```bash
# Get the failing conversations:
psql $DATABASE_URL -c "
  SELECT customer_id, initial_channel, sentiment_score, started_at
  FROM conversations
  WHERE sentiment_score < 0.3
    AND created_at > NOW() - INTERVAL '2 hours'
  ORDER BY sentiment_score ASC
  LIMIT 10;
"

# Notify human support team to prioritise these escalated tickets.
# Check if there was a product incident causing frustration:
# - Recent deployment? kubectl rollout history deploy/fte-api -n customer-success-fte
# - Check status page / known issues

# Temporary: lower sentiment escalation threshold to buy time for human agents:
# Edit production/agent/tools.py → ESCALATION_SENTIMENT_THRESHOLD
# Lower from 0.3 → 0.2 (fewer auto-escalations, agent tries harder first)
kubectl rollout restart deployment/fte-api deployment/fte-worker \
  -n customer-success-fte
```

#### Resolution D: Escalation rate spike after deployment (prompt regression)

**Identified by:** rate jumped exactly when a new image was deployed.

```bash
# Check rollout time vs escalation spike:
kubectl rollout history deployment/fte-api -n customer-success-fte

# Immediate rollback:
kubectl rollout undo deployment/fte-api -n customer-success-fte
kubectl rollout undo deployment/fte-worker -n customer-success-fte

# Verify rate recovers:
watch -n 30 "curl -s https://api.nimbusflow.io/metrics/channels | \
  jq '.channels[] | {channel, escalation_rate}'"
```

### Recovery verification

```bash
# Escalation rate should be back below 0.20 within 15–30 minutes
curl -s https://api.nimbusflow.io/metrics/channels | \
  jq '.channels[] | select(.escalation_rate > 0.20) | {channel, escalation_rate}'
# Should return empty (no channels above threshold)

# Final Challenge pass threshold check:
psql $DATABASE_URL -c "
  SELECT
    ROUND(
      COUNT(*) FILTER (WHERE status = 'escalated')::numeric
      / NULLIF(COUNT(*), 0) * 100, 2
    ) AS escalation_pct_24h
  FROM conversations
  WHERE created_at > NOW() - INTERVAL '24 hours';
"
# Must be < 25.0 to pass the Final Challenge
```

---

## Quick Diagnostic: 5-Minute System Check

Run this whenever you want a rapid health snapshot:

```bash
echo "=== Pod Status ==="
kubectl get pods -n customer-success-fte

echo ""
echo "=== HPA Status ==="
kubectl get hpa -n customer-success-fte

echo ""
echo "=== API Health ==="
curl -s https://api.nimbusflow.io/health | jq '{status,channels}'

echo ""
echo "=== Kafka Lag ==="
kubectl exec -it kafka-0 -n customer-success-fte 2>/dev/null -- \
  kafka-consumer-groups \
    --bootstrap-server localhost:9092 \
    --describe --group fte-worker 2>/dev/null | \
    awk 'NR>1 {print $1,$2,$6}' || echo "(kafka-0 not available)"

echo ""
echo "=== Escalation Rate (last 1h) ==="
curl -s https://api.nimbusflow.io/metrics/channels | \
  jq '.channels[] | {channel: .channel, esc_rate: .escalation_rate}'

echo ""
echo "=== Recent Errors ==="
kubectl logs -l app=fte-api -n customer-success-fte --tail=20 --prefix=true 2>/dev/null | \
  grep -i "error\|critical\|exception" | tail -10 || echo "No recent errors"
```

---

## Incident Post-Mortem Template

After resolving any P1 or P2 incident, fill this in `#fte-incidents`:

```
**Incident Summary**
Date/Time:
Duration:
Severity:
Alert that fired:

**Impact**
- Customers affected:
- Messages delayed/lost:
- Final Challenge metrics impact (uptime%, P95 ms, escalation%):

**Timeline**
- HH:MM  Alert fired
- HH:MM  Investigation started
- HH:MM  Root cause identified: [description]
- HH:MM  Fix applied: [command or change]
- HH:MM  Recovery confirmed

**Root Cause**
[One paragraph]

**Resolution**
[What was done]

**Prevention**
- [ ] Action item 1 (owner, due date)
- [ ] Action item 2 (owner, due date)
```
