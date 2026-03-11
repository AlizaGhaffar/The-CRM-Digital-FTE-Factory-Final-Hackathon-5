---
id: "025"
title: API Services and WebSocket Hook
stage: green
date: 2026-03-08
surface: agent
model: claude-sonnet-4-6
feature: none
branch: master
user: admin
command: none
labels: ["frontend","api","websocket","hooks","services","real-time"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - frontend/services/api.js
  - frontend/hooks/useWebSocket.js
tests:
  - none
---

## Prompt

Create API integration: frontend/services/api.js (16 functions), frontend/hooks/useWebSocket.js (real-time connection, auto-reconnect, event handlers for new tickets and escalations).

## Response snapshot

**api.js** — centralised fetch wrapper with: BASE_URL from env vars, Bearer token store (localStorage), AbortController timeout (15s), ApiError normalisation, `mockFallback()` HOF that catches network errors in dev and returns MOCKS[fn.name]. 16 public functions (submitTicket, getTicketStatus, getDashboardMetrics, getRecentTickets, getActivityFeed, getEscalations, getConversation, respondToTicket, escalateTicket, resolveTicket, getKnowledgeBase, createKbArticle, updateKbArticle, deleteKbArticle, getChannelMetrics, getAnalytics). Default export `api` object + named exports for tree-shaking.

**useWebSocket.js** — hook with: exponential back-off reconnect (1s→30s, max 10 attempts), heartbeat ping/pong (25s interval, 10s pong timeout), per-event-type subscriber registry (Set per type + wildcard '*'), auth token sent on open, channel subscription on connect. Status enum: connecting/connected/reconnecting/disconnected/failed. Returns: `on(type, fn)` → unsubscribe fn, `onAny(eventMap)` → unsubscribe all, `send(type, payload)`, `reconnect()`, `disconnect()`, convenience senders (claimEscalation, sendTyping, subscribeChannel). Two auxiliary hooks: `useTicketEvents(handlers)` pre-wires 9 event types; `useConnectionStatus()` lightweight status-only consumer.

## Outcome

- ✅ Impact: All frontend components now have a single typed API surface and real-time event bus
- 🧪 Tests: none added
- 📁 Files: frontend/services/api.js, frontend/hooks/useWebSocket.js (created)
- 🔁 Next prompts: Wire api.js into each admin component replacing inline fetch calls; add React Query / SWR layer over api.js for caching; write unit tests for request() and reconnect logic
- 🧠 Reflection: mockFallback HOF keeps mock logic co-located with real implementations without polluting call sites; subscriber Set pattern avoids memory leaks vs addEventListener approach

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): none
- Prompt variant (if applicable): none
- Next experiment (smallest change to try): Add request deduplication (inflight map) to prevent duplicate concurrent GET calls
