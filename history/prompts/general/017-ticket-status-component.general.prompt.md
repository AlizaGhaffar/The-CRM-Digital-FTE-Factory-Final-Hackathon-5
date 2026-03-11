---
id: 017
title: Ticket Status Checker Component
stage: general
date: 2026-03-07
surface: agent
model: claude-sonnet-4-6
feature: customer-success-fte
branch: master
user: CDC
command: create frontend/components/TicketStatus.jsx with search, status badge, metadata, timeline, reply, escalate, print/download
labels: ["react","frontend","ticket-status","timeline","tailwind","animations"]
links:
  spec: specs/customer-success-fte-spec.md
  ticket: null
  adr: null
  pr: null
files:
  - frontend/components/TicketStatus.jsx
tests:
  - manual browser test
---

## Prompt

Create Ticket Status Checker for customers at frontend/components/TicketStatus.jsx with: input + check button, status badge (Open/In Progress/Resolved/Escalated), created/updated dates, priority, assigned to (AI or Human), timeline conversation (customer right / agent left, channel icons, timestamps), add reply, escalate if open, print/download conversation.

## Response snapshot

Created TicketStatus.jsx as a multi-panel component with 4 internal sub-components.

**Sub-components:**
- StatusBadge — colored ring badge with animated dot (pulse on in_progress/escalated)
- PriorityBadge — colored ring badge (green/amber/red)
- ChannelBadge — icon + label for email/whatsapp/web_form
- MetaItem — label+value metadata cell
- MessageBubble — blue gradient right (customer) / white left (agent) with channel badge + time
- TimelineDivider — date label with flanking hr lines
- ReplyForm — textarea + send button → POST /ticket/{id}/reply
- EscalateConfirm — warning box + optional reason + POST /ticket/{id}/escalate

**States:**
- idle: search card only
- loading: spinner on Check Status button
- loaded: search card + ticket detail card
- error: red error banner below search input

**Ticket detail card sections:**
1. Header: StatusBadge + PriorityBadge + ticket ID monospace
2. Action buttons (no-print): Download (.txt) + Print (window.print())
3. Metadata grid 4-col: Created / Last Updated / Category / Assigned To
4. Resolution notes (conditional green box)
5. Conversation timeline: grouped by day with TimelineDivider
6. Action panels: Reply form / Escalate confirm / success notices / buttons row

**Timeline logic:**
- messages grouped by date using reduce() into {day: messages[]}
- Customer messages: flex-row-reverse, blue gradient bubble, rounded-tr-sm
- Agent messages: flex-row, white bubble + border, rounded-tl-sm
- Each bubble: avatar circle (U / AI) + content + channel badge + time
- Empty state: placeholder icon + "No messages yet" text

**Channel icons:** SVG components EmailIcon / WhatsAppIcon / WebIcon

**Print/Download:**
- handlePrint: window.print() with @media print CSS hiding no-print elements
- handleDownload: builds plain text string → Blob → URL.createObjectURL → <a> click → revoke

**Reply flow:** textarea (min 5 chars) → POST reply → onSent → replySuccess banner → "Refresh to see in timeline"
**Escalate flow:** optional reason textarea → POST escalate → onDone → escalSuccess banner with SLA note

**API endpoints used:**
- GET /support/ticket/{id} — ticket metadata
- GET /support/ticket/{id}/messages — conversation (degrades gracefully on 404)
- POST /support/ticket/{id}/reply
- POST /support/ticket/{id}/escalate

## Outcome

- Impact: Customers can self-serve ticket status, view full conversation timeline, add replies, and escalate without contacting support again — reduces repeat contacts
- Files: frontend/components/TicketStatus.jsx (new)
- Next prompts: Exercise 2.7 Kubernetes manifests, then pytest
- Reflection: Graceful degradation on messages endpoint is key — if the endpoint isn't ready yet, the component still works for status checking without crashing

## Evaluation notes (flywheel)

- Failure modes observed: none new — builds on SupportForm patterns
- Graders run and results (PASS/FAIL): static review PASS — all 7 user requirements implemented
- Prompt variant (if applicable): none
- Next experiment: test with 0 messages, 1 message, and 20+ messages to verify timeline grouping
