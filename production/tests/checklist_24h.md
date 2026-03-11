# 24-Hour Multi-Channel Test — Validation Checklist

**Feature:** Customer Success FTE
**Namespace:** `customer-success-fte`
**Test window:** 24 continuous hours
**Reference:** Hackathon 5, Final Challenge

Fill in each metric after the run completes. All thresholds must pass before marking the FTE as production-ready.

---

## Pre-Test Setup

- [ ] `kubectl apply -f production/k8s/` — all 8 manifests applied
- [ ] `kubectl get pods -n customer-success-fte` — all pods Running (API ×3, Worker ×3)
- [ ] `kubectl get hpa -n customer-success-fte` — both HPAs healthy
- [ ] Secrets filled: `POSTGRES_PASSWORD`, `GEMINI_API_KEY`, `TWILIO_AUTH_TOKEN`, `TWILIO_ACCOUNT_SID`
- [ ] Gmail token mounted at `/app/secrets/gmail_credentials.json`
- [ ] cert-manager `ClusterIssuer letsencrypt-prod` exists and is Ready
- [ ] `GET /health` → `{"status":"ok"}` for all three channels (`email`, `whatsapp`, `web_form`)
- [ ] `GET /ready` → 200 (Postgres + Kafka reachable)
- [ ] Locust installed: `pip install locust`
- [ ] kubernetes Python package installed: `pip install kubernetes`

---

## Traffic Targets (Final Challenge)

| Channel | Target volume | Actual |
|---------|--------------|--------|
| Web Form submissions | 100+ over 24 h | _____ |
| Email (Gmail) messages | 50+ over 24 h | _____ |
| WhatsApp messages | 50+ over 24 h | _____ |
| Cross-channel customers (2+ channels) | 10+ | _____ |
| Chaos pod kills | 12 (every 2 h) | _____ |

---

## Threshold 1 — Uptime > 99.9 %

**Formula:** `(total_minutes - downtime_minutes) / total_minutes × 100`
**Allowed downtime over 24 h:** < 1.44 minutes

| Measurement | Value | Pass? |
|-------------|-------|-------|
| Total observation window (minutes) | 1440 | — |
| Downtime minutes (health returning non-200) | _____ | |
| Uptime % | _____ % | ☐ ≥ 99.9 % |

**How to measure:**
```bash
# Run alongside load test:
while true; do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://api.nimbusflow.io/health)
  echo "$(date -u +%H:%M:%S) $STATUS" >> uptime_log.txt
  sleep 10
done

# Calculate uptime:
TOTAL=$(wc -l < uptime_log.txt)
DOWN=$(grep -v "^.*200$" uptime_log.txt | wc -l)
echo "Uptime: $(echo "scale=3; ($TOTAL - $DOWN) / $TOTAL * 100" | bc)%"
```

---

## Threshold 2 — P95 Latency < 3 000 ms (All Channels)

**Source:** Locust HTML report or `load_results_stats.csv`

| Endpoint | P95 (ms) | Pass? |
|----------|----------|-------|
| POST /support/submit | _____ | ☐ < 3 000 ms |
| POST /webhooks/gmail | _____ | ☐ < 3 000 ms |
| POST /webhooks/whatsapp | _____ | ☐ < 3 000 ms |
| GET /conversations/{id} | _____ | ☐ < 3 000 ms |
| GET /customers/lookup | _____ | ☐ < 3 000 ms |
| GET /metrics/channels | _____ | ☐ < 3 000 ms |
| GET /health | _____ | ☐ < 500 ms |
| GET /ready | _____ | ☐ < 500 ms |

**How to measure:**
```bash
locust -f production/tests/load_test.py \
    --host http://api.nimbusflow.io \
    --users 20 --spawn-rate 2 --run-time 24h --headless \
    --html production/tests/load_report.html \
    --csv production/tests/load_results

# P95 is in load_results_stats.csv column "95%"
```

**Overall P95 Pass?** ☐ Yes  ☐ No

---

## Threshold 3 — Escalation Rate < 25 %

**Formula:** `escalated_conversations / total_conversations × 100`

| Measurement | Value | Pass? |
|-------------|-------|-------|
| Total conversations handled | _____ | — |
| Conversations escalated to human | _____ | |
| Escalation rate | _____ % | ☐ < 25 % |

**How to measure:**
```bash
curl https://api.nimbusflow.io/metrics/channels | jq '.channels[].escalation_rate'

# Or query DB directly:
psql $DATABASE_URL -c "
  SELECT
    COUNT(*)                                             AS total,
    COUNT(*) FILTER (WHERE status = 'escalated')        AS escalated,
    ROUND(
      COUNT(*) FILTER (WHERE status = 'escalated')::numeric
      / NULLIF(COUNT(*), 0) * 100, 2
    )                                                    AS pct
  FROM conversations
  WHERE created_at > NOW() - INTERVAL '24 hours';
"
```

---

## Threshold 4 — Cross-Channel Identification > 95 %

**Formula:** `customers_correctly_merged / customers_contacted_on_multiple_channels × 100`

| Measurement | Value | Pass? |
|-------------|-------|-------|
| Customers who contacted via ≥ 2 channels | _____ | — |
| Correctly merged into single customer record | _____ | |
| Cross-channel identification rate | _____ % | ☐ > 95 % |

**How to verify:**
```bash
# Check customers with multiple channels_used:
psql $DATABASE_URL -c "
  SELECT
    email,
    array_agg(DISTINCT channel) AS channels,
    COUNT(DISTINCT channel)     AS channel_count
  FROM conversations c
  JOIN customers cu ON c.customer_id = cu.id
  WHERE c.created_at > NOW() - INTERVAL '24 hours'
  GROUP BY email
  HAVING COUNT(DISTINCT channel) >= 2;
"

# Identification failure = same real customer appearing as two separate customer records.
# Spot-check via /customers/lookup?email=... for known test customers.
```

---

## Threshold 5 — No Message Loss

**Definition:** Every message published to Kafka must appear in the DB `messages` table.

| Measurement | Value | Pass? |
|-------------|-------|-------|
| Messages published to Kafka (all topics) | _____ | — |
| Messages stored in DB `messages` table | _____ | |
| Difference (must be 0) | _____ | ☐ = 0 |
| Message loss after chaos kills | 0 required | ☐ = 0 |

**How to measure:**
```bash
# Kafka message counts (requires kafka-topics.sh):
kafka-run-class.sh kafka.tools.GetOffsetShell \
    --bootstrap-server $KAFKA_BOOTSTRAP_SERVERS \
    --topic nimbusflow.messages.email,nimbusflow.messages.whatsapp,nimbusflow.messages.web_form \
    --time -1

# DB message count:
psql $DATABASE_URL -c "
  SELECT channel, COUNT(*) AS stored
  FROM messages
  WHERE created_at > NOW() - INTERVAL '24 hours'
  GROUP BY channel
  ORDER BY channel;
"

# Chaos test verifies zero loss per kill cycle:
pytest production/tests/chaos_test.py::test_24h_chaos_run -v -s
```

---

## Chaos Test Results

| Cycle | Time | Pod killed | Recovery (s) | Max consec fails | Msg loss | Pass? |
|-------|------|-----------|--------------|------------------|----------|-------|
| 1 | _____ | _____ | _____ | _____ | 0 | ☐ |
| 2 | _____ | _____ | _____ | _____ | 0 | ☐ |
| 3 | _____ | _____ | _____ | _____ | 0 | ☐ |
| 4 | _____ | _____ | _____ | _____ | 0 | ☐ |
| 5 | _____ | _____ | _____ | _____ | 0 | ☐ |
| 6 | _____ | _____ | _____ | _____ | 0 | ☐ |
| 7 | _____ | _____ | _____ | _____ | 0 | ☐ |
| 8 | _____ | _____ | _____ | _____ | 0 | ☐ |
| 9 | _____ | _____ | _____ | _____ | 0 | ☐ |
| 10 | _____ | _____ | _____ | _____ | 0 | ☐ |
| 11 | _____ | _____ | _____ | _____ | 0 | ☐ |
| 12 | _____ | _____ | _____ | _____ | 0 | ☐ |

**Recovery SLO:** < 60 s per cycle
**Max consecutive failures:** ≤ 10 health pings (50 s window)

---

## HPA Scaling Validation

- [ ] API pods scaled above 3 during peak load (`kubectl get hpa fte-api-hpa -n customer-success-fte`)
- [ ] Worker pods scaled above 3 during high message volume
- [ ] API pods scaled back down after load subsided (within 5 min)
- [ ] Worker pods scaled back down slowly (10-min stabilization window respected)
- [ ] No `OOMKilled` pod restarts during test (`kubectl describe pods -n customer-success-fte | grep OOM`)

---

## Post-Test Sign-Off

| Threshold | Target | Result | Pass? |
|-----------|--------|--------|-------|
| Uptime | > 99.9 % | _____ % | ☐ |
| P95 latency (worst endpoint) | < 3 000 ms | _____ ms | ☐ |
| Escalation rate | < 25 % | _____ % | ☐ |
| Cross-channel identification | > 95 % | _____ % | ☐ |
| Message loss | = 0 | _____ | ☐ |
| All chaos cycles passed | 12/12 | ___/12 | ☐ |

**Overall result:** ☐ **PASS — True Omnichannel Digital FTE**  ☐ **FAIL — remediation required**

**Tester:** _____________________
**Date completed:** _____________________
**Cluster / environment:** _____________________
