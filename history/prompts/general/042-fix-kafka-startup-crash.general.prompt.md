---
name: Fix Kafka startup crash
description: Make Kafka connection optional so backend starts without a running broker
type: general
stage: general
date: 2026-03-15
surface: agent
model: claude-sonnet-4-6
feature: none
branch: master
labels: ["bugfix", "kafka", "backend", "startup"]
---

## Prompt

backend start karte hoa ye error aarah mujhe
KafkaConnectionError: Unable to bootstrap from [('localhost', 9092, ...)]

## Response

Made Kafka startup non-fatal in `production/api/main.py`:

1. Wrapped `_producer.start()` in try/except — sets `_producer = None` on failure with a warning log.
2. Added null check on shutdown so `_producer.stop()` is skipped if Kafka never connected.
3. Changed `get_producer()` to raise `HTTPException(503)` instead of `RuntimeError` so webhook endpoints return a proper HTTP error rather than crashing the app.

**Result:** App starts cleanly without Kafka. `/health`, `/api/metrics`, `/api/send-email`, `/api/send-whatsapp` work normally. `/webhooks/gmail` and `/webhooks/whatsapp` return 503 until a Kafka broker is reachable.

## Files Modified

- `production/api/main.py` — lifespan, get_producer, shutdown
