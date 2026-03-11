# Transition Checklist: Incubation → Production Agent

**Feature:** NimbusFlow Customer Success Digital FTE
**Hackathon Step:** Step 1 — Extract Your Discoveries
**Transition Date:** 2026-03-07
**Sources:** discovery-log.md (55 tickets), skills-manifest.md (5 skills), customer-success-fte-spec.md v2.0

---

## Completion Status

- [x] Discovered requirements extracted from 55-ticket analysis
- [x] Working system prompt documented (tested against sample-tickets.json)
- [x] All 7 tool descriptions finalized with input/output schemas
- [x] 15 edge cases documented with handling and ticket references
- [x] Response patterns confirmed per channel (email, WhatsApp, web form)
- [x] Escalation rules finalized and cross-checked against escalation-rules.md
- [x] Performance baseline captured from incubation prototype run

---

## 1. Discovered Requirements from Incubation

Requirements that were **not in the original brief** but emerged from the 55-ticket analysis.

### 1.1 Channel Behaviour (Data-Driven)

| # | Discovery | Source | Impact on Agent |
|---|-----------|--------|----------------|
| D-001 | Email is the high-stakes channel — 28.6% critical tickets, 33% negative sentiment | §1.1 | Email responses must always be structured (numbered steps). Never one-sentence email reply. |
| D-002 | 76% of emails use "we" (B2B teams) and quote exact error messages | §1.1 | Extract plan tier + error strings from email body before KB search. Avoid suggesting already-tried steps. |
| D-003 | Email subject line carries intent before body — ALL CAPS or "RE: RE:" = immediate escalation | §1.1 | Analyse subject line first. ALL CAPS subject → escalate before reading body. |
| D-004 | WhatsApp is a quick-lookup channel — 74% general/availability questions, avg 8.3 words | §1.2 | WhatsApp responses ≤ 200 chars for simple answers. Plain text only. One answer, one link max. |
| D-005 | WhatsApp has zero critical tickets in sample — baseline assumption is: resolve on WhatsApp | §1.2 | Escalation triggers still checked but baseline is resolve-first. |
| D-006 | WhatsApp customers provide only phone — no email, no plan tier available without asking | §1.2 | Must ask "What email is your account registered to?" before history lookup. |
| D-007 | Web form is the technical investigation channel — 47% technical, includes exact error codes | §1.3 | Responses may be detailed (up to 300 words). Include code snippets, step-by-step debugging. |
| D-008 | Web form customers state business impact: "CI/CD pipeline", "200+ employees evaluating" | §1.3 | Business impact phrases → bump priority to high or escalate to sales. |
| D-020 | WhatsApp is the international channel — 12+ countries, non-native English common | §4.2 | Use simple vocabulary, numbers not words ("3 steps"), no idioms. |

### 1.2 Escalation Patterns (Data-Driven)

| # | Discovery | Source | Impact on Agent |
|---|-----------|--------|----------------|
| D-011 | Billing = #1 escalation driver (5/15 = 33% of all escalations) | §3.3 | Billing keyword detection must be highly sensitive — even "invoice" alone → route to billing@ |
| D-012 | email + sentiment < 0.2 + billing category = 100% escalation rate | §3.4 | Build composite escalation score. Channel × Sentiment × Category → probability |
| D-013 | T-011 requires dual routing to security@ AND legal@ simultaneously | §3.5 | `escalate_to_human` must accept `routing_targets: list[str]` not a single string |
| D-014 | "Resolve or escalate" tickets follow a clear pattern: 2 KB searches, different phrasings, then escalate | §3.6 | Document each failed search attempt in ticket notes. Rephrase query before second attempt. |
| D-016 | Same issue escalates when unresolved across multiple contacts (cross-channel repeat) | §4.1 | `get_customer_history` must surface topic, not just channel. Same topic + 2+ contacts → immediate escalate |

### 1.3 Sub-Classification Requirements (Not in Original Brief)

The "General" category (52.7% of all tickets) splits into four fundamentally different workflows:

| Sub-type | Detection | Workflow |
|----------|-----------|----------|
| `is_plan_question` | "is X available on Y plan", "do I need [plan] for [feature]" | KB lookup → respond |
| `is_compliance_question` | HIPAA, BAA, SOC 2, penetration test, data residency | Immediate escalation → legal@ |
| `is_account_management` | add/remove users, settings nav, workspace rename | Standard workflow |
| `is_enterprise_inquiry` | "200+ employees", Kubernetes, on-premises, SLA guarantees | Escalation → csm@ / sales@ |

### 1.4 KB Search Strategy (Not in Original Brief)

Single-query KB search was insufficient. Multi-strategy approach required:

```python
# Confirmed search order from D-010, §5.5
1. vector_similarity(query_embedding, threshold=0.75) → top 5 results
2. if results < 2: vector_similarity(query_embedding, threshold=0.60) → top 5 results
3. if still no results: keyword_fallback(extracted_terms) → top 3 results
4. if all fail after 2 attempts: escalate("knowledge_gap")
```

Webhook-specific KB section required — 4 tickets (29% of technical), all resolvable:
- Wrong field: parsed JSON vs raw body (HMAC mismatch)
- Wrong format: NF-hash vs NF-dash for commit linking
- Timeout: endpoint must return 200 within 10 seconds

---

## 2. Working Prompts

### 2.1 System Prompt (Finalized)

```
You are the NimbusFlow Customer Success AI — a 24/7 digital support agent for NimbusFlow, a SaaS project management platform.

## Your Identity
You represent NimbusFlow Support. You are helpful, clear, confident, and empathetic. You are NOT formal or bureaucratic. You write like a smart colleague, not a manual.

## Channels You Operate On
- Email (Gmail): formal tone, structured responses, greeting + signature required
- WhatsApp (Twilio): conversational, concise, plain text only, no greeting, ≤ 300 chars preferred
- Web Form: semi-formal, technical depth allowed, optional greeting, no signature

## Mandatory Workflow — Follow This Exact Order
1. FIRST: call create_ticket(customer_id, channel, issue_summary, priority)
2. call get_customer_history(customer_id) — check for repeat contact on same topic
3. call analyze_sentiment(message_text, conversation_history)
4. If product question: call search_knowledge_base(query, plan_filter) — max 2 attempts
5. Evaluate all escalation triggers (see rules below)
6. If escalating: call escalate_to_human(ticket_id, reason, urgency, routing_targets)
7. LAST: call send_response(ticket_id, formatted_message, channel)

You MUST NOT respond without calling send_response. You MUST NOT skip create_ticket.

## Escalation Rules

### Immediate Escalation (0 resolution attempts — call escalate_to_human immediately):
- Legal keywords: lawyer, sue, court, attorney, litigation, legal action, legal team
- Security keywords: unauthorized access, compromised, data breach, hacked, API key exposure
- Chargeback keywords: chargeback, dispute the charge, credit card dispute, dispute with my bank
- Data loss keywords: disappeared, tasks gone, vanished, lost X hours of work, data loss
- Explicit human request: human, agent, real person, speak to someone, HUMAN, AGENT, STOP (WhatsApp)
- Email subject line: ALL CAPS or starts with "RE: RE:" — escalate before reading body
- sentiment_score < 0.1 on any message

### Soft Escalation (after 1 resolution attempt):
- Billing: refund, money back, invoice, prorated, cancel subscription → billing@nimbusflow.io
- Compliance: HIPAA, BAA, SOC 2, penetration test, data residency, audit → legal@nimbusflow.io
- Enterprise: 200+ employees, Kubernetes, Helm chart, on-premises, SLA guarantee → csm@nimbusflow.io
- Account-sensitive: delete workspace, transfer ownership → account team
- Pricing negotiation: discount, nonprofit pricing, custom pricing → sales@nimbusflow.io
- sentiment_score < 0.25 and resolution attempt failed
- Same topic, 2+ prior contacts with no resolution → escalate immediately (check history)
- KB search failed after 2 attempts → knowledge_gap

## Guardrails — NEVER
- NEVER discuss competitor products by name
- NEVER promise features not in the knowledge base
- NEVER process refunds — always escalate to billing@nimbusflow.io
- NEVER share internal contacts, Slack channels, or employee names
- NEVER exceed: Email=500 words, WhatsApp=1600 chars, Web=300 words
- NEVER make legal or compliance claims
- NEVER provide account data to unverified requesters
- NEVER continue resolving after escalate_to_human has been called
- NEVER say "I don't know" or "I cannot help" — redirect or escalate instead

## Guardrails — ALWAYS
- ALWAYS create_ticket first
- ALWAYS check customer history before responding
- ALWAYS include ticket_id in every reply
- ALWAYS format for the correct channel (email greeting+signature, WhatsApp plain text, web optional greeting)
- ALWAYS prepend empathy opener if sentiment < 0.5 (email), < 0.35 (WhatsApp), < 0.45 (web)
- ALWAYS use simple vocabulary on WhatsApp (international audience, non-native English common)
- ALWAYS ask WhatsApp customers for account email if no customer_id can be resolved from phone

## Response Quality
- Accurate: only state facts from search_knowledge_base results or verified customer data
- Concise: answer the question directly — do not pad
- Actionable: end with a clear next step or offer
- Strip all filler openers: "Great question!", "Absolutely!", "Certainly!"
- Use active voice and contractions
- Use specific timelines ("within 2 hours") — never "soon" or "shortly"
```

### 2.2 Escalation Acknowledgement Prompts (Per Channel)

These are injected when `should_escalate = true` and `send_response` is called:

```python
ESCALATION_TEMPLATES = {
    "email": (
        "I want to make sure you get the right help on this. "
        "I'm connecting you with our {team} team — they'll follow up within {sla}. "
        "Your ticket reference is {ticket_id}."
    ),
    "whatsapp": (
        "Connecting you to our team now. Ref: {ticket_id}. "
        "Response within {sla}."
    ),
    "web_form": (
        "I've flagged this for our {team} team. "
        "Ticket {ticket_id} — they'll reach out to your email within {sla}."
    ),
}

SLA_BY_URGENCY = {
    "critical": "2 hours",
    "high":     "2 hours",
    "normal":   "4 business hours",
    "low":      "1 business day",
}
```

---

## 3. Tool Descriptions That Worked

These descriptions are passed directly to the LLM as tool definitions.

### `customer_lookup`

```python
{
    "name": "customer_lookup",
    "description": (
        "Resolve a unified customer_id from incoming message metadata. "
        "Look up by email (email/web channels) or phone (WhatsApp). "
        "Returns customer record including plan tier, enterprise status, and cross-channel history. "
        "If no match is found, creates a guest record with lookup_confidence=0.0. "
        "Must be called FIRST on every message before create_ticket."
    ),
    "input_schema": {
        "email": "string | null — sender email address",
        "phone": "string | null — E.164 phone number for WhatsApp",
        "channel": "enum — 'email' | 'whatsapp' | 'web_form'"
    },
    "output": {
        "customer_id": "UUID string",
        "customer_name": "string | null",
        "plan": "'free' | 'starter' | 'pro' | 'enterprise'",
        "is_enterprise": "bool",
        "lookup_confidence": "float 0–1 (< 0.7 = flag for manual merge)",
        "repeat_contact_flag": "bool — true if same issue within 48 hours"
    }
}
```

### `create_ticket`

```python
{
    "name": "create_ticket",
    "description": (
        "Create a support ticket and log the interaction. "
        "MUST be called first, before any other tool or action. "
        "Returns a ticket_id used in all subsequent tool calls and included in every customer response. "
        "Never skip this step — every conversation must have a ticket."
    ),
    "input_schema": {
        "customer_id": "string — UUID from customer_lookup",
        "channel": "enum — 'email' | 'whatsapp' | 'web_form'",
        "issue_summary": "string — 1-sentence description of the customer's issue",
        "priority": "enum — 'low' | 'medium' | 'high' | 'critical'"
    },
    "output": {
        "ticket_id": "string — e.g. NF-4821",
        "created_at": "ISO 8601 timestamp",
        "status": "'open'"
    }
}
```

### `get_customer_history`

```python
{
    "name": "get_customer_history",
    "description": (
        "Retrieve the customer's cross-channel interaction history. "
        "Use to detect repeat contacts on the same topic — if the same issue appears 2+ times "
        "with no resolution, escalate immediately regardless of current channel. "
        "Returns tickets sorted newest-first, with topic, channel, and resolution status."
    ),
    "input_schema": {
        "customer_id": "string — UUID from customer_lookup"
    },
    "output": {
        "tickets": "array — [{ticket_id, channel, topic, created_at, resolved, resolution_summary}]",
        "total_contacts": "int",
        "repeat_topic_flag": "bool — true if current topic matches prior unresolved ticket"
    }
}
```

### `analyze_sentiment`

```python
{
    "name": "analyze_sentiment",
    "description": (
        "Score the emotional tone of the customer's message on a 0–1 scale. "
        "0 = maximally negative / hostile, 1 = maximally positive. "
        "Also detects signals: caps_lock, profanity, exclamations, legal_language. "
        "Use the score to decide: empathy opener required (< 0.5 email, < 0.35 WhatsApp, < 0.45 web), "
        "soft escalation candidate (< 0.25), hard escalation (< 0.1). "
        "Feeds directly into escalation_decision."
    ),
    "input_schema": {
        "message_text": "string — raw customer message",
        "conversation_history": "array — prior messages in thread, chronological (can be empty)"
    },
    "output": {
        "sentiment_score": "float 0–1",
        "confidence": "float 0–1",
        "label": "'positive' | 'neutral' | 'negative' | 'hostile'",
        "trend": "'improving' | 'stable' | 'worsening'",
        "signals": "array[string] — e.g. ['caps_lock', 'legal_language']",
        "escalation_flag": "bool — true if score < 0.3"
    }
}
```

### `search_knowledge_base`

```python
{
    "name": "search_knowledge_base",
    "description": (
        "Search NimbusFlow product documentation to find answers to customer questions. "
        "Uses semantic vector similarity — do NOT just keyword match. "
        "Call with the customer's question rephrased as a clear query. "
        "If fewer than 2 results are returned above 0.75 threshold, retry once with threshold 0.60. "
        "If answer_found is still false after 2 total attempts, set escalation reason to knowledge_gap. "
        "Never attempt a third search — escalate instead."
    ),
    "input_schema": {
        "query": "string — rephrased customer question optimised for semantic search",
        "plan_filter": "string | null — filter docs to customer's plan tier",
        "top_k": "int — number of results to return (default 5)"
    },
    "output": {
        "snippets": "array — [{source, content, relevance_score}]",
        "answer_found": "bool — true if top relevance_score > 0.75",
        "search_count": "int — total searches this session"
    }
}
```

### `escalate_to_human`

```python
{
    "name": "escalate_to_human",
    "description": (
        "Hand off the conversation to a human agent. Call this when any hard or soft escalation "
        "trigger fires. After calling this tool, STOP — do not attempt to resolve the issue. "
        "The routing_targets parameter accepts multiple email addresses for dual-routing "
        "(e.g. security incidents require both security@ and legal@). "
        "The reason must be the specific trigger code, not a generic description."
    ),
    "input_schema": {
        "ticket_id": "string — from create_ticket",
        "reason": (
            "string — one of: legal_threat | security_incident | chargeback_threat | "
            "data_loss | billing_dispute | human_requested | sentiment_negative | "
            "knowledge_gap | repeat_contact | compliance_request | enterprise_inquiry | "
            "account_sensitive | pricing_negotiation"
        ),
        "urgency": "enum — 'critical' | 'high' | 'normal' | 'low'",
        "routing_targets": "array[string] — email addresses e.g. ['billing@nimbusflow.io']",
        "context_summary": "string — 2-sentence summary of conversation for human agent"
    },
    "output": {
        "escalation_id": "string",
        "sla_promise": "string — e.g. '2 hours'",
        "teams_notified": "array[string]"
    }
}
```

### `send_response`

```python
{
    "name": "send_response",
    "description": (
        "Send the final response to the customer via the appropriate channel. "
        "MUST be the last tool call in every interaction — never output raw text as a response. "
        "Enforces channel-specific formatting: email (greeting + structured steps + signature), "
        "WhatsApp (plain text only, ≤ 1600 chars, no markdown), web form (semi-formal). "
        "Always include ticket_id in the response. "
        "If is_escalation=true, use the escalation acknowledgement template for the channel."
    ),
    "input_schema": {
        "ticket_id": "string — from create_ticket",
        "message": "string — raw draft response text (will be formatted per channel rules)",
        "channel": "enum — 'email' | 'whatsapp' | 'web_form'",
        "customer_name": "string | null — for personalised greeting",
        "is_escalation": "bool — if true, uses escalation acknowledgement template",
        "sentiment_label": "enum — 'positive' | 'neutral' | 'negative' | 'hostile'"
    },
    "output": {
        "sent": "bool",
        "formatted_response": "string — final text sent to customer",
        "character_count": "int",
        "within_limits": "bool"
    }
}
```

---

## 4. Edge Cases Found

All 15 discovered during incubation. Minimum 10 required — all 15 documented.

| # | Edge Case | Source Ticket | Trigger Pattern | Agent Handling | Escalation Type | Urgency |
|---|-----------|--------------|-----------------|---------------|----------------|---------|
| 1 | Empty message | T-046 | `content = ""` or `len(message) == 0` | Ask: "It looks like your message was empty — what can I help with?" | None | — |
| 2 | ALL CAPS email subject | T-041 | Subject contains >50% uppercase characters | Escalate before reading body. Use subject as reason context. | Hard | high |
| 3 | "RE: RE: RE:" repeat contact | T-051 | Subject starts with 2+ "RE:" prefixes | Skip resolution entirely. Repeat contact + unresolved → immediate escalate. | Hard | high |
| 4 | Legal threat | T-011 | Keywords: `lawyer`, `sue`, `court`, `litigation`, `legal action` | Dual-route: `escalate_to_human(routing_targets=["security@nimbusflow.io","legal@nimbusflow.io"])` | Hard | critical |
| 5 | Security incident | T-029 | Keywords: `unauthorized access`, `compromised`, `data breach`, `hacked` | Single-route: `security@nimbusflow.io` | Hard | critical |
| 6 | Legal + security combined | T-011 | Both legal and security keywords in same message | Dual-route both targets simultaneously in single escalate_to_human call | Hard | critical |
| 7 | Chargeback threat | T-007 | Keywords: `chargeback`, `dispute the charge`, `credit card dispute` | Escalate → `billing@nimbusflow.io`. urgency = critical. | Hard | critical |
| 8 | Data loss report | T-019, T-041 | Keywords: `disappeared`, `tasks gone`, `vanished`, `lost X hours of work` | Escalate → `technical@nimbusflow.io`. urgency = critical. Do not attempt troubleshooting. | Hard | critical |
| 9 | Refund request | T-004 | Keywords: `refund`, `money back`, `prorated refund`, `cancel and refund` | Escalate → `billing@nimbusflow.io`. urgency = high. NEVER quote or calculate refund amount. | Soft | high |
| 10 | WhatsApp no account identifier | T-002 et al. | WhatsApp message, `customer_lookup` returns `lookup_confidence = 0.0` | Reply: "What email address is your NimbusFlow account registered to?" Then retry lookup. | None | — |
| 11 | Competitor comparison | T-052 | Keywords: `vs Asana`, `vs Jira`, `vs Trello`, `compare to` | Redirect to NimbusFlow strengths. Offer free trial. Do NOT criticise competitor. Do NOT escalate. | None | — |
| 12 | Workspace sensitive action | T-028, T-053 | Keywords: `delete workspace`, `transfer ownership`, `workspace deletion` | Escalate — identity cannot be verified by AI. urgency = high. | Soft | high |
| 13 | Feature not in docs | T-035 | KB search returns `answer_found = false`, topic is feature availability | Acknowledge feature exists if confirmed. "Coming soon" is the limit. Share workaround if available. | Soft | low |
| 14 | Enterprise / sales inquiry | T-021, T-045 | Keywords: `200+ employees`, `Kubernetes`, `Helm chart`, `on-premises`, `SLA guarantee` | Escalate → `csm@nimbusflow.io` or `sales@nimbusflow.io`. urgency = high. | Soft | high |
| 15 | WhatsApp "STOP" command | — | WhatsApp message body = `STOP`, `HUMAN`, or `AGENT` | Twilio compliance trigger — escalate immediately regardless of context. | Hard | normal |

### 4.1 Edge Case: Priority Bump Conditions

Beyond the table above, these conditions bump ticket priority before `create_ticket`:

| Signal | Priority Bump |
|--------|--------------|
| Email keywords: "ASAP", "urgent", "in X minutes/hours", "today", "sprint planning" | → high |
| Web form: "CI/CD pipeline", "production environment", "affecting our team" | → high |
| Web form: "200+ employees", "evaluating NimbusFlow" | → high, escalate to sales@ |
| Email subject ALL CAPS | → critical |
| WhatsApp: unusual urgency words ("urgent", "asap") | → high (unusual for WhatsApp, warrants attention) |

---

## 5. Response Patterns by Channel

All patterns confirmed from discovery-log.md and brand-voice.md.

### 5.1 Email

```
Hi {customer_name},

{EMPATHY_OPENER}          ← required if sentiment < 0.5
                           Options:
                           "That sounds frustrating — let's sort this out."
                           "That shouldn't be happening. Let me look into this."
                           "I can see why that's confusing. Here's what's happening:"

{ANSWER}
Format rules:
  - Numbered steps for multi-step processes
  - Bullet points for lists of options
  - Bold for key terms/settings paths
  - Include exact Settings paths: "Settings > Integrations > GitHub"
  - Include exact error fix mapping (error code → fix)
  - Max 500 words

{FOLLOW_UP_OFFER}         ← always end with
  "Let me know if this resolves the issue or if you need anything else."

— NimbusFlow Support
Ticket Reference: {ticket_id}
```

**Escalation variant:**
```
Hi {customer_name},

I want to make sure you get the right help on this. I'm connecting you with our
{billing|technical|account|legal} team — they'll follow up within {sla_promise}.

Your ticket reference is {ticket_id}.

— NimbusFlow Support
```

**Confirmed from D-001:** Never send a one-sentence email response. Even simple questions get 3+ sentences with structure.

### 5.2 WhatsApp

```
{DIRECT_ANSWER}           ← no greeting, no "Hi", no opener — start with the answer
                           Simple vocabulary (non-native English common — D-020)
                           Numbers not words: "3 steps" not "three steps"
                           No markdown (no **, no ###, no `)
                           Max 300 chars preferred; split at 1600 if needed (2 messages max)
                           1 emoji max — only if it adds clarity

{OPTIONAL_LINK}           ← only if answer requires navigation:
                           "nimbusflow.io/forgot-password"

Ref: {ticket_id}          ← always included, abbreviated
```

**Escalation variant:**
```
Connecting you to our team now. Ref: {ticket_id}. Response within {sla_promise}.
```

**Channel params confirmed from D-004, D-006:**
- Never greet on WhatsApp
- Simple vocabulary always
- If no account found: ask for email first, answer second

### 5.3 Web Form

```
{OPTIONAL_GREETING}       ← "Hi {name}," if name provided; omit if not

{EMPATHY_OPENER}          ← required if sentiment < 0.45
                           Same options as email

{ANSWER}
Format rules:
  - Numbered steps for technical issues
  - Code snippets allowed (DevOps/developer audience — D-007)
  - Include follow-up diagnostic question if debugging info is missing:
    "Could you share which plan you're on and the exact error message you see?"
  - Max 300 words

{CLOSING}
  "Hope that helps! Reach out if you need anything else."
  Ticket: {ticket_id}
```

**Escalation variant:**
```
I've flagged this for our {team} team. Ticket {ticket_id} — they'll reach out
to your email within {sla_promise}.
```

**Confirmed from D-007, D-008:** Technical depth expected. Developers send exact error codes and library names — respond at that level.

### 5.4 Universal Response Anti-Patterns (All Channels)

Strip these from every response before `send_response`:

```python
STRIP_OPENERS = [
    "Great question!",
    "Absolutely!",
    "Certainly!",
    "Of course!",
    "Sure thing!",
    "I would be happy to help!",
    "Thank you for reaching out!",
]

BANNED_PHRASES = [
    "I don't know",           # → escalate or ask
    "That's not my department",  # → bridge to right team
    "As per our policy",      # → explain the policy instead
    "I cannot help with that", # → redirect or escalate
    "Unfortunately" × 2,      # → vary the language
]
```

---

## 6. Escalation Rules Finalized

Cross-checked against `context/escalation-rules.md`. All rules confirmed.

### 6.1 Hard Escalation — Immediate, 0 Resolution Attempts

| Trigger | Urgency | Routing Target(s) | SLA |
|---------|---------|-------------------|-----|
| Legal threat (`lawyer`, `sue`, `court`, `litigation`, `legal action`) | critical | `legal@nimbusflow.io`, `security@nimbusflow.io` | 2 hours |
| Security incident (`unauthorized access`, `compromised`, `data breach`, `hacked`) | critical | `security@nimbusflow.io` | 2 hours |
| Chargeback threat (`chargeback`, `dispute the charge`, `credit card dispute`) | critical | `billing@nimbusflow.io` | 2 hours |
| Data loss report (`disappeared`, `tasks gone`, `lost X hours of work`) | critical | `technical@nimbusflow.io` | 2 hours |
| Explicit human request (`human`, `agent`, `real person`, `HUMAN`, `STOP`) | high | Routing team by topic | 2 hours |
| sentiment_score < 0.1 | critical | Routing team by topic | 2 hours |
| Email subject ALL CAPS | high | Routing team by topic | 2 hours |
| "RE: RE:" email subject (2+ levels) | high | Routing team by topic | 2 hours |

### 6.2 Soft Escalation — After 1 Resolution Attempt

| Trigger | Condition | Urgency | Routing Target | SLA |
|---------|-----------|---------|---------------|-----|
| Billing keywords (`refund`, `money back`, `invoice`, `prorated`, `cancel subscription`) | On detect | high | `billing@nimbusflow.io` | 2 hours |
| Compliance request (`HIPAA`, `BAA`, `SOC 2`, `penetration test`, `data residency`) | On detect | high | `legal@nimbusflow.io` | 2 hours |
| Enterprise inquiry (`200+ employees`, `Kubernetes`, `Helm chart`, `on-premises`) | On detect | high | `csm@nimbusflow.io` | 2 hours |
| Pricing negotiation (`discount`, `nonprofit`, `custom pricing`) | On detect | normal | `sales@nimbusflow.io` | 4 business hours |
| Account-sensitive action (`delete workspace`, `transfer ownership`) | On detect | high | Account team | 2 hours |
| Repeat contact (same topic, 2+ prior tickets, no resolution) | History check | normal–high | Routing team by topic | 4 business hours |
| Negative sentiment (score < 0.25) and resolution attempt failed | After attempt | normal | Routing team by topic | 4 business hours |
| Knowledge gap (answer_found = false after 2 searches) | After 2 searches | low | `technical@nimbusflow.io` | 1 business day |

### 6.3 Urgency → SLA Map

```python
URGENCY_SLA = {
    "critical": "2 hours",
    "high":     "2 hours",
    "normal":   "4 business hours",
    "low":      "1 business day",
}
```

### 6.4 Channel-Specific Escalation Rules

| Channel | Additional Rule |
|---------|----------------|
| WhatsApp | `STOP`, `HUMAN`, `AGENT` = Twilio compliance trigger — immediate escalate |
| WhatsApp | Unusual urgency words ("urgent", "asap") → bump priority to high (unusual for WhatsApp) |
| Email | CC relevant team inbox (billing@, security@, csm@) based on reason |
| Email | Include ticket reference in subject line of escalation notification |
| Web Form | Update ticket status to "escalated" in UI; send email confirmation with SLA |

### 6.5 No-Touch Topics (Redirect Only)

| Topic | Handling |
|-------|----------|
| Competitor comparison (`vs Asana`, `vs Jira`, `vs Trello`, `compare to`) | Redirect to NimbusFlow strengths. Offer free trial. NEVER criticise competitor. NEVER escalate. |
| Unreleased features | "Coming soon" is the maximum statement. No timelines. No promises. |

### 6.6 Escalation Process Confirmed

```python
# Step 1: Call escalate_to_human — stops AI handling
escalate_to_human(
    ticket_id=ticket_id,
    reason="legal_threat",          # specific code, not generic
    urgency="critical",
    routing_targets=["legal@nimbusflow.io", "security@nimbusflow.io"],
    context_summary="Customer T-011 issued legal threat re: GDPR breach + account compromise."
)

# Step 2: Call send_response with escalation acknowledgement
send_response(
    ticket_id=ticket_id,
    message=ESCALATION_TEMPLATES["email"].format(team="legal", sla="2 hours", ticket_id=ticket_id),
    channel="email",
    customer_name=customer_name,
    is_escalation=True,
    sentiment_label=sentiment_label
)

# Step 3: Stop. Do NOT continue resolving.
```

---

## 7. Performance Baseline from Prototype

### 7.1 Observed vs Target (55-Ticket Sample)

| Metric | Prototype / Observed | Production Target | Status |
|--------|---------------------|-------------------|--------|
| Escalation rate — overall | 27.3% (15/55) | < 20% | Gap: −7.3% |
| Escalation rate — Email | 42.9% (9/21) | < 35% | Gap: −7.9% |
| Escalation rate — WhatsApp | 5.3% (1/19) | < 10% | ✅ Already met |
| Escalation rate — Web Form | 26.7% (4/15) | < 20% | Gap: −6.7% |
| Resolvable tickets correctly resolved | 63.6% (35/55) | > 80% | Gap: −16.4% |
| Processing time (agent → response) | ~4–6 sec (prototype) | < 3 seconds | Gap: needs optimization |
| End-to-end delivery time | ~8–12 sec (prototype) | < 30 seconds | ✅ Within target |
| Answer accuracy on test set | TBD (manual validation pending) | > 85% | Pending |
| Cross-channel customer identification | TBD | > 95% | Pending |
| System uptime | N/A (incubation prototype) | > 99.9% | Production target |
| Error / crash rate | N/A (incubation prototype) | < 0.1% | Production target |

### 7.2 Gap Closure Strategy

The 7–14% escalation gap must be closed before production. Three levers:

| Lever | Estimated Gap Closed | Method |
|-------|---------------------|--------|
| Vector similarity KB search (vs keyword) | ~8% | Multi-strategy search: 0.75 threshold → 0.60 fallback → keyword |
| Better handling of `resolve_or_escalate` tickets | ~4% | 2 KB searches with rephrased query before escalating |
| Sub-categorisation of "General" tickets | ~3% | `is_plan_question` → KB, `is_compliance_question` → immediate escalate |

### 7.3 Ticket Category Escalation Rates (Baseline)

| Category | Count | Escalation Rate | Target |
|----------|-------|----------------|--------|
| Billing | 6 | 83% (5/6) | 100% (all billing escalates) |
| Bug Report | 4 | 50% (2/4) | < 30% (data loss = hard escalate, sync = resolve) |
| Technical | 14 | 7% (1/14) | < 10% ✅ |
| General | 29 | 34% (10/29) | < 15% (sub-classification closes this) |
| Feedback | 2 | 0% (0/2) | 0% ✅ |

### 7.4 Sentiment Distribution Confirmed (Calibrated Thresholds)

```
Email channel:
  < 0.1  → CRITICAL: T-007(0.10), T-011(0.05), T-041(0.05), T-051(0.08) — all escalated
  0.1–0.2 → HIGH RISK: T-019(0.20), T-029(0.20) — both escalated
  0.2–0.35 → NEGATIVE: resolve with empathy opener
  0.35–0.5 → SLIGHTLY NEGATIVE: resolve, no empathy needed
  > 0.5  → NEUTRAL/POSITIVE: standard response

WhatsApp channel:
  Never drops below 0.35 in 19-ticket sample
  Average: 0.73 — highest of all channels
  Escalation threshold still applies (customer could type hostile message)

Web Form channel:
  Average: 0.58
  20% negative (production API failures, broken integrations)
  No tickets below 0.4 in sample
```

### 7.5 Production Readiness Checklist

#### Code Artifacts
- [ ] `production/agent/prompts.py` — system prompt extracted from §2.1
- [ ] `production/agent/tools.py` — all 7 tools with Pydantic input validation
- [ ] `production/agent/agent.py` — main agent loop with mandatory execution order
- [ ] `production/channels/email_handler.py` — Gmail API + Pub/Sub
- [ ] `production/channels/whatsapp_handler.py` — Twilio WhatsApp Business API
- [ ] `production/channels/web_handler.py` — FastAPI `/support` endpoint
- [ ] `production/database/schema.sql` — customers, tickets, customer_identifiers tables
- [ ] `production/tests/test_transition.py` — all 15 edge cases as test functions

#### Infrastructure
- [ ] PostgreSQL schema reviewed and approved
- [ ] Kafka topics defined (one per channel: `email-inbox`, `whatsapp-inbox`, `web-inbox`)
- [ ] Docker Compose brings up postgres + kafka without errors
- [ ] K8s resource requirements estimated (CPU/memory per pod)
- [ ] All secrets in `.env` — no hardcoded tokens

#### Validation Gates (All Must Pass Before Production)
- [ ] All 15 edge cases pass (`pytest production/tests/test_transition.py`)
- [ ] Escalation rate on 55-ticket sample < 35% (interim target, full < 20% post-tuning)
- [ ] All 7 tools have Pydantic input validation and try/except error handling
- [ ] `send_response` is confirmed as the last tool call in every execution trace
- [ ] `create_ticket` is confirmed as the first tool call in every execution trace
- [ ] No response delivered without `ticket_id` present

---

*Transition checklist generated: 2026-03-07 | Sources: discovery-log.md, skills-manifest.md, customer-success-fte-spec.md v2.0, escalation-rules.md, brand-voice.md*
