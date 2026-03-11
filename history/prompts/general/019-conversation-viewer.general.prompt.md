---
id: 019
title: Conversation Viewer Admin Component
stage: general
date: 2026-03-07
surface: agent
model: claude-sonnet-4-6
feature: customer-success-fte
branch: master
user: CDC
command: create frontend/components/ConversationViewer.jsx with split view, ticket details panel, conversation thread, reply box, action buttons
labels: ["react","frontend","admin","conversation","split-view","tailwind","reply","escalate"]
links:
  spec: specs/customer-success-fte-spec.md
  ticket: null
  adr: null
  pr: null
files:
  - frontend/components/ConversationViewer.jsx
tests:
  - manual browser test
---

## Prompt

Create Conversation Viewer for admin at frontend/components/ConversationViewer.jsx with: split view (left ticket details / right conversation), customer info (name/email/phone/channels used), priority/status badges, escalation reason, conversation timeline (customer right / AI left / human left with different styling / internal notes full-width yellow), reply box with channel selector, action buttons (resolve/escalate/assign/internal note).

## Response snapshot

Created ConversationViewer.jsx — most complex component so far. 280+ lines with 8 sub-components.

**Layout:** `flex h-screen overflow-hidden` — left `aside` (w-72, fixed) + right `main` (flex-1). Both panels scroll independently.

**Left panel sub-components:**
- TicketDetails — full left panel with all details sections
- ActionBtn — polymorphic button with variant (green/red/indigo/amber/default) + loading spinner
- ChannelPill — icon + label badge

**TicketDetails sections:**
1. Ticket ID (copy button → clipboard API → "Copied!" feedback)
2. Status badge + Priority badge
3. Timeline (Created / Updated / Resolved if applicable)
4. Classification: category chip + source channel pill
5. Escalation reason: red warning box (conditional)
6. Customer card: avatar initials + name + company + contact details (email/phone/plan/tickets/since)
7. Channel history: array of ChannelPill from customer.channels_used
8. Action buttons: Resolve (green, hidden if resolved), Escalate (red, only open/in_progress), Assign (indigo)

**Right panel sections:**
1. Thread header: customer avatar + name + email + message count + status badge
2. Action toast: green success banner with 3s auto-dismiss
3. Conversation thread (overflow-y-auto, auto-scrolls to bottom on load/new message)
4. Reply box (hidden when resolved) OR resolved notice

**4 message types in MessageBubble:**
- customer: right-aligned, blue gradient bubble, rounded-tr-sm
- ai: left-aligned, white border bubble, rounded-tl-sm, shows latency_ms
- human: left-aligned, indigo gradient bubble + "Human Agent" badge
- internal_note: full-width amber banner with note icon (not a bubble)

**Reply box modes:**
- reply: gradient blue send button, "Type your reply…" placeholder, channel dropdown selector
- note: amber styling, "Add an internal note…" placeholder, "Add Note" button
- Ctrl+Enter keyboard shortcut for quick send
- All messages optimistically appended immediately after send

**Actions (handleAction):** POST to /api/tickets/{id}/{type} → optimistic state update → toast. Falls back to optimistic update in demo (no real API).

**Mock data:** Full MOCK_TICKET + MOCK_MESSAGES (7 messages covering all 4 types) used as fallback when API unavailable.

**Props:** ticketId (required), apiBase (default '').

## Outcome

- Impact: Admins can view full conversation context, understand channel-switching behavior, reply directly, add internal notes, and resolve/escalate without leaving the page
- Files: frontend/components/ConversationViewer.jsx (new)
- Next prompts: Exercise 2.7 Kubernetes manifests (k8s/), pytest production/tests/
- Reflection: Optimistic message append is essential for UX — waiting for API response to show sent message feels broken; the demo mode (API fallback to mock data) ensures component is always demonstrable

## Evaluation notes (flywheel)

- Failure modes observed: none new
- Graders run and results (PASS/FAIL): static review PASS — all 5 feature sections implemented, 4 message types differentiated, reply box has channel selector + mode toggle
- Prompt variant (if applicable): none
- Next experiment: test panel layout on 768px viewport to confirm left panel doesn't overflow
