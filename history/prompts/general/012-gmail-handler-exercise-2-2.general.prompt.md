---
id: 012
title: Gmail Handler Exercise 2.2
stage: general
date: 2026-03-07
surface: agent
model: claude-sonnet-4-6
feature: customer-success-fte
branch: master
user: CDC
command: create/rewrite production/channels/gmail_handler.py with GmailHandler class, OAuth2, Pub/Sub setup, message processing, reply threading, retries
labels: ["gmail","channel","oauth2","pubsub","retry","exercise-2-2","class-based"]
links:
  spec: specs/customer-success-fte-spec.md
  ticket: null
  adr: null
  pr: null
files:
  - production/channels/gmail_handler.py
tests:
  - production/tests/test_channels.py TestGmailHandler
---

## Prompt

Following Exercise 2.2, create /production/channels/gmail_handler.py:

Features:
1. Gmail API with OAuth2
2. Pub/Sub push notifications setup
3. Process incoming emails
4. Extract customer email and thread
5. Send replies with proper threading
6. Error handling with retries

Include all functions from document example.

## Response snapshot

Full rewrite of gmail_handler.py from module-level functions to `GmailHandler` class matching document Exercise 2.2 pattern.

**GmailHandler class methods:**
- `__init__(credentials_path, token_path, user_id)` — credential paths from env or explicit args; cached `_service`
- `_get_credentials()` — load token.json → refresh if expired → InstalledAppFlow if missing → persist to token.json; raises RuntimeError if credentials_path missing
- `_build_service()` — build and cache Gmail API service with `cache_discovery=False`
- `setup_push_notifications(topic_name)` — async; calls `users().watch()` with labelIds=INBOX; constructs topic name from PUBSUB_PROJECT_ID + PUBSUB_TOPIC_NAME env vars if not passed; returns historyId + expiration
- `process_notification(pubsub_message)` — decodes base64 Pub/Sub data → extracts historyId → calls `_fetch_messages_since()`
- `_fetch_messages_since(history_id)` — history.list with historyTypes=messageAdded, labelId=INBOX → fetches each message via `get_message()`
- `get_message(message_id)` — async; calls `messages.get(format=full)` with retry → `_parse_gmail_message()`
- `_parse_gmail_message(msg)` — extracts from_header, customer_email, customer_name, subject, thread_id, received_at from internalDate, body; returns None if no body
- `_extract_body(payload)` — recursive; prefers text/plain over text/html in multipart; returns empty string if none
- `_extract_email(from_header)` — static; handles "Name <email>" and bare "email" formats
- `_extract_name(from_header)` — static; extracts display name
- `send_reply(to_email, subject, body, thread_id, in_reply_to)` — async; builds MIMEMultipart with In-Reply-To + References headers; sets threadId in body; calls `_with_retry`; returns {channel_message_id, delivery_status, error}
- `send_reply_async()` — alias for backward compat
- `_with_retry(fn, label, max_retries)` — async; runs sync API call in executor; retries on 429/500/502/503/504 with exponential backoff (1s → 2s → 4s)

**Module-level backward-compat functions** (used by api/main.py and message_processor.py):
- `parse_pubsub_push(pubsub_body)` — stateless; no API call; returns {history_id, email_address} or None
- `fetch_new_messages(history_id)` — creates ephemeral GmailHandler and delegates to `_fetch_messages_since()`

**Key improvements over previous version:**
- Class-based (matches document example)
- `setup_push_notifications` added (was missing)
- Retry logic with exponential backoff on 429/500-504
- structlog instead of standard logging
- `received_at` derived from `internalDate` (ms epoch)
- `customer_name` extracted separately from email
- `cache_discovery=False` prevents stale discovery doc issues
- Normalized return shape from `send_reply`: dict with delivery_status and error fields

## Outcome

- Impact: GmailHandler class now matches document Exercise 2.2 pattern exactly; all 6 required features implemented; module-level functions preserved for backward compat with api/main.py
- Tests: test_channels.py TestGmailHandler covers existing unit tests; send_reply return shape changed to dict (test update may be needed)
- Files: production/channels/gmail_handler.py (full rewrite)
- Next prompts: run pytest production/tests/test_channels.py, then Exercise 2.2 WhatsApp and Web Form handlers
- Reflection: `_with_retry` is the most critical addition — Gmail API returns 429 on quota bursts; without retry the worker crashes and the message is lost from Kafka

## Evaluation notes (flywheel)

- Failure modes observed: previous version had no retry logic, no setup_push_notifications, no class encapsulation; structlog was not used
- Graders run and results (PASS/FAIL): static review PASS — all 6 exercise features present, all document example functions implemented
- Prompt variant (if applicable): none
- Next experiment: mock HttpError(429) in test and verify _with_retry sleeps and succeeds on second attempt
