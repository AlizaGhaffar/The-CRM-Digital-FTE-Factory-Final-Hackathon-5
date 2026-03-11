# Skills Manifest — NimbusFlow Customer Success FTE

**Version:** 1.0
**Exercise:** 1.5 — Skill Identification
**Agent:** Customer Success Digital FTE
**Channels:** Email (Gmail), WhatsApp, Web Form

---

## Overview

This manifest defines the five core skills that compose the Customer Success FTE agent. Each skill is atomic, independently testable, and maps to a specific stage in the message-handling pipeline.

### Execution Order (per incoming message)

```
[Incoming Message]
       |
       v
1. Customer Identification Skill   ← identify WHO is writing
       |
       v
2. Sentiment Analysis Skill        ← understand HOW they feel
       |
       v
3. Knowledge Retrieval Skill       ← find WHAT the answer is (if product Q)
       |
       v
4. Escalation Decision Skill       ← decide IF human handoff is needed
       |
       v
5. Channel Adaptation Skill        ← format HOW to respond
       |
       v
[Send Response / Escalate]
```

---

## Skill 1: Customer Identification

### Purpose
Resolve the sender's identity from raw message metadata before any other processing. Enables unified history lookup across all three channels.

### When to Use
On every incoming message, before any other skill runs.

### Inputs

| Field | Type | Source | Required |
|-------|------|--------|----------|
| `message_metadata` | object | Channel adapter | Yes |
| `metadata.email` | string | Email header / WhatsApp profile / form field | Conditional |
| `metadata.phone` | string | WhatsApp sender ID | Conditional |
| `metadata.channel` | enum | `email` \| `whatsapp` \| `web` | Yes |
| `metadata.raw_headers` | object | Full channel headers for fallback lookup | No |

> At least one of `email` or `phone` must be present.

### Outputs

| Field | Type | Description |
|-------|------|-------------|
| `customer_id` | string (UUID) | Canonical unified customer identifier |
| `customer_name` | string | Display name from CRM record |
| `plan` | enum | `free` \| `starter` \| `pro` \| `enterprise` |
| `is_enterprise` | bool | True if plan = enterprise (affects SLA) |
| `channel_history` | array | Prior tickets across all channels, newest first |
| `last_contact_at` | ISO 8601 | Timestamp of most recent prior message |
| `repeat_contact_flag` | bool | True if same issue within last 48 hours |
| `lookup_confidence` | float (0–1) | Match confidence; < 0.7 triggers guest fallback |

### Implementation
```python
customer_lookup(
    email=metadata.email,        # primary key
    phone=metadata.phone,        # secondary key (WhatsApp)
    channel=metadata.channel
) -> CustomerRecord
```

- Queries PostgreSQL `customers` table; joins `tickets` for history.
- If no match found: create guest record, `customer_id = "guest-<uuid>"`, `lookup_confidence = 0.0`.
- If `lookup_confidence < 0.7`: flag for post-resolution manual merge.

### Test Cases

| # | Scenario | Input | Expected Output |
|---|----------|-------|-----------------|
| TC-1.1 | Known email customer | `email: "alice@corp.com"` | Returns existing UUID, full history |
| TC-1.2 | Known WhatsApp number | `phone: "+14155551234"` | Matches via phone, returns merged history |
| TC-1.3 | Unknown customer | `email: "new@unknown.com"` | Guest record created, confidence = 0.0 |
| TC-1.4 | Ambiguous match | Same email on two accounts | Returns highest-confidence match, flag set |
| TC-1.5 | Repeat contact flag | Same customer, same issue, < 48h | `repeat_contact_flag = true` |
| TC-1.6 | Enterprise customer | Plan = enterprise | `is_enterprise = true` |

---

## Skill 2: Sentiment Analysis

### Purpose
Score the emotional tone of every incoming customer message and track trend across the conversation. Feeds directly into Escalation Decision Skill.

### When to Use
On every customer message, immediately after Customer Identification.

### Inputs

| Field | Type | Source | Required |
|-------|------|--------|----------|
| `message_text` | string | Raw customer message body | Yes |
| `conversation_history` | array | Prior messages in this thread, chronological | Yes (can be empty) |
| `customer_id` | string | From Skill 1 — for cross-session trend | Yes |

### Outputs

| Field | Type | Description |
|-------|------|-------------|
| `sentiment_score` | float (0–1) | 0 = maximally negative, 1 = maximally positive |
| `confidence` | float (0–1) | Model confidence in the score |
| `label` | enum | `positive` \| `neutral` \| `negative` \| `hostile` |
| `trend` | enum | `improving` \| `stable` \| `worsening` |
| `signals` | array[string] | Detected signals: `caps_lock`, `profanity`, `exclamations`, `legal_language` |
| `escalation_flag` | bool | True if score < 0.3 (soft escalation threshold per escalation-rules.md) |

### Implementation
```python
analyze_sentiment(
    text=message_text,
    history=conversation_history
) -> SentimentResult
```

- Computes score on current message; compares to prior scores in `conversation_history` to derive `trend`.
- Signal detection runs regex over text: ALLCAPS ratio, `!!!` count, profanity list, legal keywords.
- `escalation_flag = True` when `sentiment_score < 0.3` (per escalation-rules.md §Soft Triggers §1).

### Escalation Thresholds (from escalation-rules.md)

| Score Range | Label | Action |
|-------------|-------|--------|
| 0.7 – 1.0 | positive | Standard flow |
| 0.4 – 0.69 | neutral | Standard flow |
| 0.3 – 0.39 | negative | Monitor; escalate on 2nd attempt |
| 0.0 – 0.29 | hostile | Set `escalation_flag = true`; urgency = normal |

### Test Cases

| # | Scenario | Input | Expected Output |
|---|----------|-------|-----------------|
| TC-2.1 | Positive message | "Thanks, this worked great!" | score ≥ 0.8, label = positive |
| TC-2.2 | Neutral query | "How do I reset my password?" | 0.4 ≤ score ≤ 0.69, label = neutral |
| TC-2.3 | Frustrated customer | "THIS IS NOT WORKING!!!" | score < 0.4, signals includes `caps_lock`, `exclamations` |
| TC-2.4 | Hostile / legal threat | "I'll contact my lawyer about this" | score < 0.3, signals includes `legal_language`, escalation_flag = true |
| TC-2.5 | Worsening trend | 3 messages: 0.7 → 0.5 → 0.28 | trend = worsening, escalation_flag = true |
| TC-2.6 | Improving trend | 3 messages: 0.2 → 0.5 → 0.75 | trend = improving, label = positive |

---

## Skill 3: Knowledge Retrieval

### Purpose
Search NimbusFlow product documentation to find accurate answers to customer product questions.

### When to Use
When the message is classified as a product question (not a billing dispute, legal threat, or explicit human request). Run in parallel with Sentiment Analysis where possible.

### Inputs

| Field | Type | Source | Required |
|-------|------|--------|----------|
| `query_text` | string | Cleaned customer question | Yes |
| `channel_context` | object | Channel + plan + prior failed searches | Yes |
| `channel_context.channel` | enum | `email` \| `whatsapp` \| `web` | Yes |
| `channel_context.plan` | string | From Skill 1 — filters plan-specific docs | Yes |
| `channel_context.previous_searches` | array[string] | Prior queries in this session (avoids redundant lookups) | No |

### Outputs

| Field | Type | Description |
|-------|------|-------------|
| `snippets` | array[DocumentSnippet] | Ranked documentation excerpts |
| `snippets[].source` | string | Document name / section |
| `snippets[].content` | string | Relevant text excerpt |
| `snippets[].relevance_score` | float (0–1) | Semantic similarity to query |
| `answer_found` | bool | True if top snippet relevance > 0.75 |
| `search_count` | int | Total searches attempted this session |
| `escalation_flag` | bool | True if answer_found = false after 2 searches |

### Implementation
```python
search_knowledge_base(
    query=query_text,
    filters={"plan": channel_context.plan},
    top_k=3
) -> SearchResult
```

- Uses semantic search over `context/product-docs.md` and plan-specific documentation.
- `search_count` increments per call; when `search_count >= 2` and `answer_found = false`, sets `escalation_flag = true` (per escalation-rules.md §Soft Triggers §2: Knowledge Gap).
- Roadmap / unreleased feature questions: return `answer_found = false` immediately, set `escalation_flag = true`.

### Test Cases

| # | Scenario | Input | Expected Output |
|---|----------|-------|-----------------|
| TC-3.1 | Direct product question | "How do I connect GitHub?" | answer_found = true, relevance > 0.75 |
| TC-3.2 | Plan-specific question | "Does my Starter plan have SSO?" | Filtered to Starter docs; accurate yes/no |
| TC-3.3 | Unknown feature | "Does NimbusFlow have AI summaries?" | answer_found = false if not in docs |
| TC-3.4 | Roadmap question | "When is offline mode coming?" | escalation_flag = true, no answer given |
| TC-3.5 | Repeated failed search | Two searches, both relevance < 0.75 | escalation_flag = true, search_count = 2 |
| TC-3.6 | WhatsApp context | query via WhatsApp | Returns concise snippet only (no long docs) |

---

## Skill 4: Escalation Decision

### Purpose
Determine whether to continue AI handling or hand off to a human agent, applying all rules from `context/escalation-rules.md`.

### When to Use
After Knowledge Retrieval (or after response generation), before sending any reply.

### Inputs

| Field | Type | Source | Required |
|-------|------|--------|----------|
| `conversation_context` | object | Full thread: customer_id, plan, history | Yes |
| `sentiment_trend` | object | From Skill 2: score, label, trend, signals | Yes |
| `message_content` | string | Raw customer message | Yes |
| `knowledge_result` | object | From Skill 3: answer_found, search_count | Yes |
| `channel` | enum | `email` \| `whatsapp` \| `web` | Yes |

### Outputs

| Field | Type | Description |
|-------|------|-------------|
| `should_escalate` | bool | Primary decision |
| `escalation_type` | enum | `hard` \| `soft` \| `none` |
| `reason` | string | Specific trigger code (e.g., `legal_threat`, `sentiment_negative`) |
| `urgency` | enum | `critical` \| `high` \| `normal` \| `low` |
| `routing_team` | string | `billing` \| `technical` \| `security` \| `sales` \| `account` |
| `acknowledgement_message` | string | Pre-filled escalation message per brand-voice.md |

### Hard Escalation Triggers (Immediate — from escalation-rules.md)

| Condition | Reason Code | Urgency |
|-----------|-------------|---------|
| Legal keywords: `lawyer`, `sue`, `litigation`, `GDPR violation` | `legal_threat` | critical |
| Security: data breach, compromised account, API key exposure | `security_incident` | critical |
| Financial: refund on annual plan > $500, chargeback threat | `billing_dispute` | high |
| Enterprise downtime > 15 min or active P1 | `enterprise_sla_violation` | high |
| Explicit human request: `human`, `agent`, `real person`, `HUMAN`, `STOP` | `human_requested` | normal |

### Soft Escalation Triggers (Escalate After 2 Attempts — from escalation-rules.md)

| Condition | Reason Code | Urgency |
|-----------|-------------|---------|
| sentiment_score < 0.3 | `sentiment_negative` | normal |
| knowledge search_count >= 2, answer_found = false | `knowledge_gap` | low |
| Roadmap / pricing negotiation | `roadmap_or_pricing` | low |
| repeat_contact_flag = true with no resolution | `repeat_contact` | normal |
| Account deletion, ownership transfer, bulk user removal > 20 | `account_level_change` | high |

### Implementation
```python
# Pseudo-logic
def escalation_decision(conversation_context, sentiment_trend, message_content, knowledge_result, channel):
    # 1. Check hard triggers first
    for trigger in HARD_TRIGGERS:
        if trigger.matches(message_content, conversation_context):
            return EscalationResult(should_escalate=True, type="hard", ...)

    # 2. Check soft triggers
    for trigger in SOFT_TRIGGERS:
        if trigger.matches(sentiment_trend, knowledge_result, conversation_context):
            if conversation_context.attempt_count >= 2:
                return EscalationResult(should_escalate=True, type="soft", ...)

    return EscalationResult(should_escalate=False, type="none")
```

- Calls `escalate_to_human(ticket_id, reason, urgency)` when `should_escalate = True`.
- `acknowledgement_message` generated from brand-voice.md escalation templates, channel-appropriate.

### Test Cases

| # | Scenario | Input | Expected Output |
|---|----------|-------|-----------------|
| TC-4.1 | Legal threat | message contains "I'll sue you" | should_escalate = true, type = hard, urgency = critical |
| TC-4.2 | Security incident | "Someone accessed my account without permission" | should_escalate = true, reason = security_incident, urgency = critical |
| TC-4.3 | Refund > $500 | Annual plan refund request | should_escalate = true, reason = billing_dispute, urgency = high |
| TC-4.4 | Human requested | "I want to speak to a real person" | should_escalate = true, reason = human_requested |
| TC-4.5 | Low sentiment, 2nd attempt | score < 0.3, attempt_count = 2 | should_escalate = true, type = soft, urgency = normal |
| TC-4.6 | Low sentiment, 1st attempt | score < 0.3, attempt_count = 1 | should_escalate = false (try once first) |
| TC-4.7 | Knowledge gap | search_count = 2, answer_found = false | should_escalate = true, reason = knowledge_gap, urgency = low |
| TC-4.8 | Happy path | Positive sentiment, answer found | should_escalate = false, type = none |
| TC-4.9 | WhatsApp STOP | message = "STOP" via WhatsApp | should_escalate = true (Twilio compliance) |
| TC-4.10 | Enterprise SLA | Enterprise customer, downtime 20 min | should_escalate = true, urgency = high |

---

## Skill 5: Channel Adaptation

### Purpose
Transform the raw response text into a channel-appropriate format that matches tone, length, and style rules from `context/brand-voice.md`.

### When to Use
Before sending any response (AI-generated or escalation acknowledgement) to the customer.

### Inputs

| Field | Type | Source | Required |
|-------|------|--------|----------|
| `response_text` | string | Draft answer from agent | Yes |
| `target_channel` | enum | `email` \| `whatsapp` \| `web` | Yes |
| `customer_name` | string | From Skill 1 (for personalized greeting) | No |
| `ticket_id` | string | For escalation references | Conditional |
| `is_escalation` | bool | True if this is an escalation acknowledgement | No |
| `sentiment_label` | enum | From Skill 2 — adjusts empathy tone | No |

### Outputs

| Field | Type | Description |
|-------|------|-------------|
| `formatted_response` | string | Final send-ready message |
| `character_count` | int | For WhatsApp length validation |
| `within_limits` | bool | True if within channel length budget |
| `applied_rules` | array[string] | List of formatting rules applied (for audit) |

### Channel Rules (from brand-voice.md)

#### Email
- Greeting: `Hi [customer_name],`
- Closing: `Let me know if there's anything else I can help with. — NimbusFlow Support`
- Escalation closing: `"I want to make sure you get the right help on this. I'm looping in our [team] — they'll follow up within [SLA]. Your ticket reference is [ticket_id]."`
- Format: structured, numbered steps if multi-step, bullet points for options
- Length: up to 300 words for complex; 3–5 sentences for simple

#### WhatsApp
- No greeting or closing formula
- Plain text only — no markdown
- Max 300 characters preferred; split into 2 messages if needed
- 1 emoji max, only when it adds clarity
- Escalation: `"Connecting you to our team now. Ref: [ticket_id]. You'll hear back within [SLA]."`

#### Web Form
- Greeting: optional, use name if provided
- Closing: `"Hope that helps! Reach out if you need anything else."`
- Length: 2–4 sentences for simple; up to 150 words for complex
- Escalation: `"I've flagged this for our team. Ticket [ticket_id] — they'll reach out to your email within [SLA]."`

### Tone Adjustments by Sentiment
- `negative` or `hostile`: prepend empathy opener before answer
  - "That sounds frustrating — let's sort this out."
  - "That shouldn't be happening. Let me look into this."
- `positive`: no empathy opener needed; keep direct

### Language Rules Applied (from brand-voice.md)
- Strip filler openers: `Great question!`, `Absolutely!`, `Certainly!`
- Convert passive voice to active where detected
- Replace vague timelines with specific ones (`soon` → `within 2 hours`)
- Never output: `I don't know`, `That's not my department`, `As per our policy`

### Implementation
```python
adapt_for_channel(
    response_text=response_text,
    channel=target_channel,
    customer_name=customer_name,
    ticket_id=ticket_id,
    is_escalation=is_escalation,
    sentiment_label=sentiment_label,
    brand_voice_config="context/brand-voice.md"
) -> FormattedResponse
```

### Test Cases

| # | Scenario | Input | Expected Output |
|---|----------|-------|-----------------|
| TC-5.1 | Email, normal response | draft answer, channel = email, name = "Sarah" | Starts with "Hi Sarah,", ends with closing signature |
| TC-5.2 | WhatsApp, normal response | draft answer, channel = whatsapp | No greeting, plain text, ≤ 300 chars |
| TC-5.3 | WhatsApp, long answer | 500-char draft, channel = whatsapp | Split into 2 messages, both plain text |
| TC-5.4 | Email, escalation | is_escalation = true, ticket_id = "T-123" | Contains ticket ref, team routing, SLA time |
| TC-5.5 | WhatsApp, escalation | is_escalation = true, channel = whatsapp | 1-sentence confirmation + ref, ≤ 300 chars |
| TC-5.6 | Negative sentiment, email | sentiment_label = negative | Empathy opener prepended before answer |
| TC-5.7 | Filler phrase strip | draft starts with "Great question!" | Filler removed, answer leads |
| TC-5.8 | Web form response | channel = web, simple question | 2–4 sentences, optional name greeting |
| TC-5.9 | Hostile, WhatsApp | sentiment_label = hostile, whatsapp | Empathy in plain text, no markdown |
| TC-5.10 | Emoji check | whatsapp response | Max 1 emoji in output |

---

## Skill Interaction Summary

```
Message In
    └─> [1] Customer Identification  → customer_id, plan, repeat_flag, history
            └─> [2] Sentiment Analysis   → score, label, trend, signals
                    └─> [3] Knowledge Retrieval  → snippets, answer_found (if product Q)
                            └─> [4] Escalation Decision → should_escalate, reason, urgency
                                    └─> [5] Channel Adaptation → formatted_response
                                                └─> Send / Escalate
```

### Skill Data Dependencies

| Skill | Depends On | Provides To |
|-------|-----------|-------------|
| 1. Customer ID | Channel metadata | Skills 2, 3, 4, 5 |
| 2. Sentiment | Skill 1 (customer_id) | Skill 4 (escalation input) |
| 3. Knowledge | Skill 1 (plan/channel) | Skill 4 (answer_found) |
| 4. Escalation | Skills 1, 2, 3 | Skill 5 (is_escalation flag) |
| 5. Channel Adapt | Skills 1, 2, 4 | Final output |

---

## Acceptance Criteria

- [ ] Each skill has defined, typed inputs and outputs
- [ ] Each skill has >= 6 test cases covering happy path, edge cases, and failure modes
- [ ] Escalation Decision Skill covers all hard and soft triggers from `escalation-rules.md`
- [ ] Channel Adaptation Skill applies all tone/length/format rules from `brand-voice.md`
- [ ] Skills 1–5 compose without circular dependencies
- [ ] No hardcoded secrets; all external config references context files or environment variables
- [ ] Each skill is independently testable in isolation

---

*Generated: 2026-03-07 | Exercise 1.5 | NimbusFlow Customer Success FTE*
