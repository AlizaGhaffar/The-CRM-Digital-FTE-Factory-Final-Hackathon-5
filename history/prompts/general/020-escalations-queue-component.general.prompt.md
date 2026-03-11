---
id: "020"
title: Escalations Queue Admin Component
stage: green
date: 2026-03-08
surface: agent
model: claude-sonnet-4-6
feature: none
branch: master
user: admin
command: none
labels: ["frontend","react","admin","escalations","tailwind"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - frontend/components/EscalationsQueue.jsx
tests:
  - none
---

## Prompt

Create Escalations Queue for admin:

File: frontend/components/EscalationsQueue.jsx

Features:
1. Header with count: "8 Tickets Awaiting Human Review"

2. Filter bar:
   - By channel
   - By priority
   - By escalation reason
   - By wait time

3. Escalated tickets list:
   - Ticket ID
   - Customer
   - Channel
   - Escalation reason
   - Wait time (highlight if >30min)
   - Priority (High/Medium/Low with colors)
   - Action button (Take Over)

4. For each ticket, show:
   - Last customer message preview
   - AI's attempted response
   - Why AI escalated

5. Quick actions:
   - Assign to me
   - Respond as human
   - Send back to AI

## Response snapshot

Created `frontend/components/EscalationsQueue.jsx` (React 18 + Tailwind CSS) following the same patterns as `AdminDashboard.jsx`. Component includes:

- **Header** showing live ticket count with alert icon and subtitle
- **Filter bar** with selects for channel, priority, escalation reason, and wait time; Clear all button appears when filters are active
- **Responsive ticket table** with columns: Ticket ID (expandable), Customer (name + email), Channel (badge with icon), Escalation Reason (colour-coded), Wait Time (red badge + pulsing clock if >30 min), Priority badge, and Take Over button
- **Expandable detail panel** per row showing three cards: Last Customer Message, AI's Attempted Response, and Why AI Escalated (amber highlighted)
- **Quick action buttons** in detail panel: Assign to Me, Respond as Human, Send Back to AI — each calls the appropriate API endpoint and removes the ticket on success
- **Toast notifications** for action feedback
- **Dark/light mode toggle** consistent with AdminDashboard
- Mock data with 8 realistic escalated tickets covering billing dispute, technical complexity, policy exception, legal compliance, negative sentiment, repeated contact, account security, and SSO issues
- Auto-refresh every 30s via `GET /api/escalations`

## Outcome

- ✅ Impact: Admin now has a dedicated escalations queue view with filtering, ticket detail inspection, and quick-action resolution
- 🧪 Tests: none added
- 📁 Files: frontend/components/EscalationsQueue.jsx (created)
- 🔁 Next prompts: Wire into admin routing; add keyboard shortcuts; hook up real API; write unit tests
- 🧠 Reflection: Followed AdminDashboard.jsx conventions exactly — same icon components, dark/light mode pattern, Tailwind class structure, and mock-data fallback approach

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): none
- Prompt variant (if applicable): none
- Next experiment (smallest change to try): Add sortable columns by wait time / priority
