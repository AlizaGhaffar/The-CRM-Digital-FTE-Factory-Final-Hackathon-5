---
id: "026"
title: Kafka Client Exercise 2.5
stage: green
date: 2026-03-08
surface: agent
model: claude-sonnet-4-6
feature: none
branch: master
user: admin
command: none
labels: ["backend","kafka","aiokafka","producer","consumer","topics","exercise-2.5"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - production/kafka_client.py
tests:
  - none
---

## Prompt

Following Exercise 2.5, create /production/kafka_client.py:
Topics from document: fte.tickets.incoming, fte.channels.email.inbound, fte.channels.whatsapp.inbound, fte.channels.webform.inbound, fte.channels.email.outbound, fte.channels.whatsapp.outbound, fte.escalations, fte.metrics, fte.dlq.
Create FTEKafkaProducer and FTEKafkaConsumer classes.

## Response snapshot

**kafka_client.py** — centralised Kafka wrapper with:

- **`TOPICS` class** — all 9 `fte.*` topic names as class attributes + `ALL` list
- **`KafkaMessage` dataclass** — standard envelope (message_id UUID, type, source, ts ISO, payload); `to_bytes()` / `from_bytes()` JSON serialisation
- **`FTEKafkaProducer`** — async context manager; `AIOKafkaProducer` with gzip compression, `acks="all"`, `enable_idempotence=True`; `send(topic, payload, event_type, key)` with automatic DLQ routing on `KafkaError`; convenience helpers: `send_ticket`, `send_escalation`, `send_metrics`, `send_outbound_email`, `send_outbound_whatsapp`
- **`FTEKafkaConsumer`** — async context manager; `AIOKafkaConsumer` with `enable_auto_commit=False`; `consume(handler)` poll loop with manual commit after each successful handler call; DLQ routing for handler exceptions (via injected `dlq_producer`)
- **`FTEKafkaMultiConsumer`** — subscribes to N topics in one consumer instance; per-topic handler dispatch map + `default_handler` fallback; same manual-commit pattern

## Outcome

- ✅ Impact: Single Kafka abstraction for all FTE workers — message_processor.py and web_form_handler.py can adopt these classes to replace direct aiokafka usage
- 🧪 Tests: none added
- 📁 Files: production/kafka_client.py (created)
- 🔁 Next prompts: Write Kubernetes manifests in production/k8s/ (7 YAML files); add Locust load tests in tests/load_test.py; write deployment runbook
- 🧠 Reflection: KafkaMessage envelope ensures every message has a UUID and ISO timestamp for tracing; injecting dlq_producer into consumer keeps DLQ routing optional and testable

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): none
- Prompt variant (if applicable): none
- Next experiment (smallest change to try): Add request deduplication via inflight message_id set to prevent duplicate processing on consumer restart
