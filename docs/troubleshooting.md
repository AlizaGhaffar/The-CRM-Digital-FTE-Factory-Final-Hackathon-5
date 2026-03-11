# NimbusFlow Customer Success FTE — Troubleshooting Guide

**Scope:** Local development and common operator issues.
**For production incidents** (CrashLoopBackOff, Kafka lag, DB connection failures, high escalation rate) → see [`docs/runbook.md`](runbook.md).
**For first-time credential setup** → see [`docs/environment-setup.md`](environment-setup.md).

---

## Quick diagnostics

```bash
# Is the local stack healthy?
docker-compose ps

# Tail all service logs
docker-compose logs -f

# Tail a single service
docker-compose logs -f api
docker-compose logs -f worker
docker-compose logs -f postgres
docker-compose logs -f kafka
```

---

## 1. Docker Compose / Local Setup

### 1.1 `api` or `worker` container exits immediately

**Symptom:** `docker-compose up` shows container state `Exit 1` for `fte_api` or `fte_worker`.

**Cause:** Missing or malformed `.env` file, or secrets volume missing.

**Fix:**
```bash
# 1. Verify .env exists
ls -la .env

# 2. Copy example if missing
cp .env.example .env
# Then fill in real values (GEMINI_API_KEY, TWILIO_*, etc.)

# 3. Verify secrets directory exists with required files
ls -la secrets/
# Must contain: gmail-credentials.json, gmail-token.json

mkdir -p secrets
# Place your JSON files there

# 4. Rebuild and restart
docker-compose down && docker-compose up -d --build
```

---

### 1.2 `postgres` container never becomes healthy

**Symptom:** `api` and `worker` fail to start; `docker-compose ps` shows `postgres` as `starting`.

**Fix:**
```bash
# Check postgres logs
docker-compose logs postgres

# Force-recreate the volume if corrupted
docker-compose down -v
docker-compose up -d postgres

# Wait for healthy status (up to 30s)
docker-compose ps postgres
```

---

### 1.3 `kafka` container never becomes healthy

**Symptom:** `api` and `worker` fail because healthcheck waits on kafka.

**Common cause:** Zookeeper not ready when Kafka starts.

**Fix:**
```bash
# Bring up in dependency order
docker-compose up -d zookeeper
sleep 10
docker-compose up -d kafka
sleep 15
docker-compose up -d api worker
```

---

### 1.4 Port conflicts

**Symptom:** `Bind for 0.0.0.0:5432 failed: port is already allocated`.

**Fix:**
```bash
# Find the conflicting process
lsof -i :5432       # postgres
lsof -i :9092       # kafka
lsof -i :8000       # api
lsof -i :3000       # frontend

# Kill it or change the host port in docker-compose.yml:
# ports:
#   - "5433:5432"   # change the left (host) side only
```

---

### 1.5 `volume postgres_data` has stale schema

**Symptom:** `relation "conversations" does not exist` after schema changes.

**Fix:**
```bash
# Wipe the volume and re-init (destroys local data)
docker-compose down -v
docker-compose up -d
```

---

## 2. API Credential Issues

### 2.1 Gemini `401 UNAUTHENTICATED` or `API key not valid`

**Check:**
```bash
# Verify key is set in .env
grep GEMINI_API_KEY .env

# Test the key directly
curl -s "https://generativelanguage.googleapis.com/v1beta/models?key=$GEMINI_API_KEY" | python3 -m json.tool | head -20
```

**Fix:** Regenerate key at [Google AI Studio](https://aistudio.google.com/app/apikey) and update `.env`.

---

### 2.2 Gemini `429 RESOURCE_EXHAUSTED` (rate limit)

**Cause:** Free tier is 15 RPM / 1 million TPM.

**Fix:**
```bash
# Reduce concurrency in .env
MAX_KB_RESULTS=3
RESPONSE_TIMEOUT_SECONDS=60

# Or upgrade to a paid key.
```

---

### 2.3 Gmail handler not receiving emails

**Step 1 — Check token validity:**
```bash
python3 -c "
import json, datetime
t = json.load(open('secrets/gmail-token.json'))
print('Expiry:', t.get('expiry', 'unknown'))
print('Has refresh_token:', bool(t.get('refresh_token')))
"
```

**Step 2 — Re-run OAuth flow if token is missing refresh_token:**
```bash
python3 production/channels/gmail_handler.py --setup
```

**Step 3 — Verify Pub/Sub push subscription is active:**
```bash
gcloud pubsub subscriptions describe gmail-push-sub --project=$GOOGLE_CLOUD_PROJECT
# Look for: pushConfig.pushEndpoint = https://api.nimbusflow.io/channels/gmail/webhook
```

**Step 4 — Re-register the watch:**
```bash
curl -X POST http://localhost:8000/channels/gmail/setup \
  -H "Content-Type: application/json"
```

---

### 2.4 Twilio WhatsApp messages not arriving

**Check sandbox join:**
The Twilio sandbox requires users to send `join <sandbox-word>` first.

```bash
# Verify webhook URL is set in Twilio console:
# Messaging → Try it out → WhatsApp
# Webhook URL: https://api.nimbusflow.io/channels/whatsapp/webhook (POST)

# Test locally with ngrok
ngrok http 8000
# Then set ngrok URL as Twilio webhook
```

**Check credentials:**
```bash
grep TWILIO .env
# TWILIO_ACCOUNT_SID must start with AC
# TWILIO_AUTH_TOKEN is 32 characters
```

---

### 2.5 `secrets/gmail-credentials.json: No such file or directory`

**Fix:**
```bash
mkdir -p secrets
# Download from Google Cloud Console:
# APIs & Services → Credentials → OAuth 2.0 Client IDs → Download JSON
# Save as secrets/gmail-credentials.json
```

---

## 3. Database Issues (local)

### 3.1 `asyncpg.exceptions.InvalidPasswordError`

**Fix:**
```bash
# Check .env password matches docker-compose.yml
grep POSTGRES_PASSWORD .env
grep POSTGRES_PASSWORD docker-compose.yml
# Both must be "changeme" (or your custom value)
```

---

### 3.2 `relation "knowledge_base" does not exist`

**Cause:** Schema not applied (fresh DB volume).

**Fix:**
```bash
# Apply schema manually
docker-compose exec postgres psql -U fte_user -d fte_db \
  -f /docker-entrypoint-initdb.d/01-schema.sql

# Or use the seed script if available
python3 scripts/seed_knowledge_base.py
```

---

### 3.3 pgvector extension missing

**Symptom:** `ERROR: type "vector" does not exist`

**Cause:** Wrong Postgres image (not pgvector).

**Fix:** Ensure `docker-compose.yml` uses `pgvector/pgvector:pg16`, not `postgres:16`.

---

### 3.4 Connect to local Postgres directly

```bash
docker-compose exec postgres psql -U fte_user -d fte_db

# Useful queries
\dt                                        -- list tables
SELECT COUNT(*) FROM conversations;
SELECT COUNT(*) FROM knowledge_base;
SELECT * FROM escalations ORDER BY created_at DESC LIMIT 5;
```

---

## 4. Kafka Issues (local)

### 4.1 `NoBrokersAvailable` in worker logs

**Cause:** `KAFKA_BOOTSTRAP_SERVERS` is set to `localhost:9092` but worker runs inside Docker where Kafka is at `kafka:29092`.

**Fix:** The `docker-compose.yml` overrides this automatically via the `environment` block. If running the worker outside Docker:
```bash
export KAFKA_BOOTSTRAP_SERVERS=localhost:9092
python3 production/workers/message_processor.py
```

---

### 4.2 Topic not found / messages not processing

```bash
# Open Kafka UI
open http://localhost:8080

# Or list topics via CLI
docker-compose exec kafka kafka-topics \
  --bootstrap-server kafka:29092 \
  --list

# Create missing topic manually
docker-compose exec kafka kafka-topics \
  --bootstrap-server kafka:29092 \
  --create --topic messages.gmail \
  --partitions 3 --replication-factor 1
```

---

### 4.3 Dead letter queue (DLQ) messages accumulating

```bash
# Inspect DLQ
docker-compose exec kafka kafka-console-consumer \
  --bootstrap-server kafka:29092 \
  --topic messages.dlq \
  --from-beginning \
  --max-messages 10

# The message payload contains the original message + error reason
# Fix the root cause, then clear the DLQ by resetting the offset:
docker-compose exec kafka kafka-consumer-groups \
  --bootstrap-server kafka:29092 \
  --group fte-message-processor \
  --topic messages.dlq \
  --reset-offsets --to-latest --execute
```

---

## 5. Frontend Issues

### 5.1 CORS error in browser console

**Symptom:** `Access to fetch at 'http://localhost:8000' from origin 'http://localhost:3000' has been blocked by CORS policy`

**Fix:**
```bash
# In .env, ensure localhost:3000 is listed
CORS_ORIGINS=http://localhost:3000,https://yourdomain.com

# Restart the api container
docker-compose restart api
```

---

### 5.2 WebSocket connection refused

**Symptom:** Admin dashboard shows "Disconnected" or real-time updates stop.

**Fix:**
```bash
# Check the api is running and WebSocket endpoint is live
curl -i http://localhost:8000/health

# If using nginx or a reverse proxy locally, ensure it proxies WebSocket:
# proxy_http_version 1.1;
# proxy_set_header Upgrade $http_upgrade;
# proxy_set_header Connection "upgrade";
```

---

### 5.3 Frontend build fails (`node_modules` not found)

```bash
cd frontend
npm install
npm run dev
```

---

## 6. Common Error Messages

| Error message | Likely cause | Fix |
|--------------|-------------|-----|
| `GEMINI_API_KEY not set` | Missing env var | Add to `.env` |
| `Connection refused 5432` | Postgres not running | `docker-compose up -d postgres` |
| `Connection refused 9092` | Kafka not running | `docker-compose up -d kafka` |
| `gmail-credentials.json not found` | Missing secrets file | See §2.5 |
| `Token has been expired or revoked` | Gmail OAuth token expired | Re-run OAuth flow |
| `Invalid Account SID` | Wrong Twilio creds | Check `TWILIO_ACCOUNT_SID` in `.env` |
| `Table "conversations" doesn't exist` | Schema not applied | See §3.2 |
| `type "vector" does not exist` | Wrong Postgres image | See §3.3 |
| `NoBrokersAvailable` | Wrong Kafka address | See §4.1 |
| `UnicodeDecodeError` in email handler | Non-UTF-8 email body | Expected — handler strips non-UTF-8 chars |

---

## 7. Getting Help

1. Check `docker-compose logs -f <service>` for the exact error.
2. Run the 5-minute system check from [`docs/runbook.md`](runbook.md#5-minute-system-check-script).
3. Open an issue referencing the error message and the service name.
