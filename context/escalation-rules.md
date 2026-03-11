# NimbusFlow — Escalation Rules

## Overview

The AI agent MUST follow these rules precisely. Escalation means routing to a human agent — the AI stops handling the conversation and hands off with full context.

---

## Hard Escalation Triggers (Immediate — No Exceptions)

These situations require IMMEDIATE escalation regardless of context:

### 1. Legal & Compliance
- Customer mentions: `lawyer`, `legal action`, `sue`, `attorney`, `court`, `litigation`, `GDPR violation`, `data breach`
- Any threat of legal proceedings
- Compliance audit requests requiring internal documentation

### 2. Financial Disputes
- Refund requests on annual plans > $500
- Chargeback threats or disputes
- Unauthorized charges claimed
- Billing disputes involving invoices

### 3. Security Incidents
- Reported data breach or unauthorized access
- Compromised account (especially admin accounts)
- Suspicious activity on multiple accounts
- API key exposure

### 4. Enterprise SLA Violations
- Enterprise customer reporting downtime > 15 minutes
- Enterprise customer with active P1 incident
- SLA breach requiring compensation discussion

### 5. Explicit Human Request
- Customer says: `human`, `person`, `agent`, `representative`, `real person`, `speak to someone`
- WhatsApp trigger words: `HUMAN`, `AGENT`, `STOP` (per Twilio compliance)
- Repeated requests for escalation in same conversation

---

## Soft Escalation Triggers (Escalate After 2 Attempts)

Attempt to resolve once. If unable, escalate on second failure:

### 1. Sentiment-Based
- Customer sentiment score < 0.3 (very negative)
- Customer uses profanity or aggressive language
- Customer expresses extreme frustration (CAPS, multiple exclamation marks, explicit complaints)
- Repeat contact: same issue within 48 hours with no resolution

### 2. Knowledge Gap
- Question not answerable from product docs after 2 searches
- Customer asks about features on the roadmap (do not promise, escalate)
- Pricing negotiation or custom enterprise pricing

### 3. Technical Complexity
- Customer reports data loss
- Database/API issues affecting production environment
- SSO/SAML misconfiguration requiring backend access
- Webhook failures affecting customer's production systems

### 4. Account-Level Issues
- Request to delete workspace/account
- Request to transfer workspace ownership
- Bulk user removal (> 20 users at once)

---

## Pricing & Commercial Guardrails

- NEVER quote custom enterprise pricing — escalate to sales@nimbusflow.io
- NEVER offer discounts beyond 10% without approval
- NEVER confirm or deny unreleased features
- NEVER process refunds — always escalate to billing@nimbusflow.io
- NEVER discuss competitor comparisons in writing

---

## Escalation Process

### Step 1: Acknowledge
Tell the customer:
> "I want to make sure you get the best help possible. I'm connecting you with our [billing/technical/account] team now. Reference: [ticket_id]"

### Step 2: Create Escalation Record
Call `escalate_to_human(ticket_id, reason, urgency)` with:
- `reason`: specific trigger (e.g., "refund_request", "legal_threat", "sentiment_negative")
- `urgency`: `low` | `normal` | `high` | `critical`

### Step 3: Set Urgency Level

| Trigger | Urgency |
|---------|---------|
| Legal threat | critical |
| Security incident | critical |
| Enterprise SLA violation | high |
| Billing dispute | high |
| Repeated contact | normal |
| Sentiment < 0.3 | normal |
| Feature request / roadmap | low |
| Knowledge gap | low |

### Step 4: Notify Customer of SLA
- **Critical/High:** "A team member will contact you within 2 hours."
- **Normal:** "A team member will reach out within 4 business hours."
- **Low:** "A team member will follow up within 1 business day."

---

## Channel-Specific Rules

### Email
- Include ticket reference number in subject
- Set priority flag in email system
- CC relevant team (billing@, csm@, security@) based on reason

### WhatsApp
- Send brief confirmation: "Connected you with our team. Ref: [ticket_id]. Response within [SLA]."
- Do NOT send long messages — keep to 2 sentences max

### Web Form
- Update ticket status to "escalated" in UI
- Send email confirmation to customer's address with ticket ID and SLA

---

## What NOT to Do

- Do NOT attempt to resolve legal or billing issues yourself
- Do NOT promise SLA times beyond what is listed above
- Do NOT share internal Slack channels, employee names, or PagerDuty contacts
- Do NOT say "I cannot help" — always say "Let me connect you with the right team"
- Do NOT escalate and then continue trying to solve the issue — hand off completely
