# Discovery Log — NimbusFlow Customer Success FTE

**Project:** NimbusFlow Customer Success Digital FTE
**Data Source:** `context/sample-tickets.json` (55 tickets)
**Analysis Date:** 2026-03-06
**Status:** Complete — ready to guide Agent Skills design

---

## Dataset Summary

| Channel | Count | % of Total | Avg Sentiment | Avg Words | Critical Tickets |
|---------|-------|------------|---------------|-----------|-----------------|
| Email | 21 | 38.2% | **0.48** | **44** | 6 (28.6%) |
| WhatsApp | 19 | 34.5% | **0.73** | **8.3** | 0 (0%) |
| Web Form | 15 | 27.3% | **0.58** | **39** | 0 (0%) |
| **Total** | **55** | 100% | 0.59 | — | 6 (10.9%) |

**Expected actions across all tickets:**
- Resolve: 35 (63.6%)
- Escalate: 15 (27.3%)
- Resolve or Escalate: 4 (7.3%)
- Resolve Limited: 1 (1.8%)

---

## Section 1: Channel-Specific Patterns

---

### 1.1 Email Channel — Deep Analysis

**Tickets analysed:** T-001, T-004, T-007, T-009, T-011, T-014, T-016, T-019, T-021, T-024, T-026, T-029, T-032, T-035, T-038, T-041, T-043, T-046, T-049, T-051, T-054

#### Message Length
- **Average:** 44 words (range: 0 to 56 words)
- **Shortest:** T-046 — empty message (0 words) — edge case
- **Longest:** T-041 — Richard Blake's angry data-loss complaint (56 words)
- **Typical:** 35–50 words per message

#### Formality Level: **HIGH**
Every email (except T-041 ALL CAPS rant) uses:
- Proper salutation: "Hi,", "Hello,", "I am writing to inform you that..."
- Complete sentences with correct capitalisation
- Professional sign-off implied
- "We" pronoun dominant (16/21 = 76%) → B2B team context, not individual users
- Error messages and technical details quoted verbatim (T-006: `InResponseTo attribute mismatch`, T-010: `401 Unauthorized`, T-018: `HMAC-SHA256`)

#### Sentence Structure
| Pattern | Example Tickets | Count |
|---------|----------------|-------|
| Context → Problem → Request | T-001, T-003, T-014 | 8 |
| Multi-item numbered list | T-021 (5 items), T-043 (3 asks) | 3 |
| Emotional → Complaint → Ultimatum | T-007, T-041, T-051 | 3 |
| Formal/Legal opening | T-011, T-024, T-049 | 3 |

#### Sentiment Distribution (Email)
```
Sentiment 0.0–0.2 (Very Negative): T-007(0.10), T-011(0.05), T-041(0.05), T-051(0.08) → 4 tickets = 19%
Sentiment 0.2–0.4 (Negative):      T-001(0.25), T-019(0.20), T-029(0.20)              → 3 tickets = 14%
Sentiment 0.4–0.6 (Neutral):       T-004(0.50), T-009(0.60), T-046(0.50) etc.         → 7 tickets = 33%
Sentiment 0.6–0.8 (Positive):      T-014(0.60), T-021(0.70), T-038(0.65) etc.         → 5 tickets = 24%
Sentiment 0.8–1.0 (Very Positive): T-035(0.90), T-054(0.80)                            → 2 tickets = 10%
```
**Key insight:** 33% of email tickets have negative sentiment (< 0.4). Email is the channel where customers go when they're already frustrated or have a serious issue.

#### Priority Distribution (Email)
- Critical: 6/21 = **28.6%** ← disproportionately high
- High: 4/21 = 19%
- Medium: 7/21 = 33%
- Low: 4/21 = 19%

#### Category Mix (Email)
- General: 9/21 = 43% (GDPR, enterprise inquiry, compliance, partnerships)
- Technical: 5/21 = 24% (GitHub, Slack, subtasks, API, repeat webhook)
- Billing: 4/21 = 19% (refund, chargeback, discount, invoice)
- Bug Report: 2/21 = 10% (data loss × 2)
- Feedback: 1/21 = 5%

#### D-001: Email = High-Stakes Channel
- **Finding:** Email carries 28.6% critical tickets and 33% negative sentiment. Customers use email when the issue is serious, has escalated from self-service, or involves money/legal risk.
- **Impact on Agent:** Email responses must be thorough (numbered steps), acknowledge prior effort when history shows repeat contact, and always include ticket reference. Never give a one-sentence email response.
- **Status:** [x] Incorporated into agent design

#### D-002: Email Customers Provide Structured Context
- **Finding:** 76% of emails use "we" (B2B teams). They describe what they tried, quote error messages, and state their plan tier. This context is usable.
- **Impact on Agent:** Extract plan tier, error messages, and steps-already-tried from email body before searching KB. Avoids suggesting things they've already tried.
- **Status:** [x] Incorporated

#### D-003: Email Subject Lines Are Signal-Rich
- **Finding:** Subject lines reveal intent before reading body — "LEGAL NOTICE" (T-011), "RE: RE: RE:" (T-051), "YOUR SERVICE IS ABSOLUTELY TERRIBLE" (T-041).
- **Impact on Agent:** Analyse subject line first. ALL CAPS subject = escalate before reading body. "RE: RE:" prefix = repeat contact, escalate directly.
- **Status:** [x] Incorporated

---

### 1.2 WhatsApp Channel — Deep Analysis

**Tickets analysed:** T-002, T-005, T-008, T-012, T-015, T-017, T-020, T-022, T-025, T-027, T-030, T-033, T-036, T-039, T-042, T-044, T-047, T-050, T-053

#### Message Length
- **Average:** 8.3 words (range: 4 to 14 words)
- **Shortest:** T-022 — "how to enable 2fa?" (4 words)
- **Longest:** T-005 — "getting 429 errors on the api. what are the limits for growth plan" (14 words)
- **Pattern:** All WhatsApp messages fit in a single line — not a single one exceeds 80 characters

#### Formality Level: **VERY LOW (Conversational)**
Every WhatsApp message uses:
- **All lowercase** (18/19 = 95%)
- **No greeting** (0/19 = 0%) — no "Hi" or "Hello"
- **No punctuation or minimal** (most have no period at end)
- **Abbreviations:** "hrs" (T-012), "2fa" (T-022), "im" (T-033), "ios" (T-020)
- **Question format:** "how do i", "is there", "where can i", "can i" — functional, not emotional

#### Sentiment Distribution (WhatsApp)
```
Sentiment 0.0–0.4 (Negative):      T-012(0.35), T-030(0.45), T-044(0.40) → 3 tickets = 16%
Sentiment 0.4–0.6 (Neutral):       T-005(0.55), T-042(0.70)              → 3 tickets = 16%
Sentiment 0.6–0.8 (Positive):      T-002(0.70), T-015(0.75) etc.         → 7 tickets = 37%
Sentiment 0.8–1.0 (Very Positive): T-008(0.80), T-020(0.85) etc.         → 6 tickets = 32%
```
**Key insight:** 69% of WhatsApp tickets have positive/neutral sentiment. WhatsApp is for quick, low-friction lookups — not complaints.

#### Priority Distribution (WhatsApp)
- Critical: 0/19 = **0%** ← zero critical tickets
- High: 1/19 = 5% (T-042 — trial expiring = urgency but not crisis)
- Medium: 5/19 = 26%
- Low: 12/19 = **63%** ← majority low priority

#### Category Mix (WhatsApp)
- General: 14/19 = **74%** (plan questions, feature availability, settings navigation)
- Bug Report: 2/19 = 11% (app sync, push notifications)
- Technical: 2/19 = 11% (API rate limits, slow app)
- Billing: 1/19 = 5% (upgrade from trial)

#### D-004: WhatsApp = Quick-Lookup Channel
- **Finding:** 74% of WhatsApp tickets are "general" category — availability questions, settings navigation, feature clarifications. Customers are not reporting incidents via WhatsApp. The longest message is 14 words.
- **Impact on Agent:** WhatsApp responses must be ≤ 200 characters for simple answers. Use plain text only. No lists, no markdown. One answer, one sentence, optionally one link.
- **Status:** [x] Incorporated

#### D-005: WhatsApp Has Zero Escalation-Worthy Tickets (except T-053)
- **Finding:** Only T-053 (workspace ownership transfer) required escalation. No legal threats, no billing disputes, no security incidents came via WhatsApp in this dataset.
- **Impact on Agent:** WhatsApp escalation triggers should still be checked (customer could type "sue" on WhatsApp), but the baseline assumption is: resolve on WhatsApp.
- **Status:** [x] Incorporated

#### D-006: WhatsApp Messages Have No Identifiers
- **Finding:** WhatsApp customers give only their question — no email, no plan tier, no account context. Cannot look up their account without asking.
- **Impact on Agent:** Must ask "What email is your account registered to?" before checking customer history on WhatsApp. Then store phone→email mapping in `customer_identifiers`.
- **Status:** [x] Incorporated

---

### 1.3 Web Form Channel — Deep Analysis

**Tickets analysed:** T-003, T-006, T-010, T-013, T-018, T-023, T-028, T-031, T-034, T-037, T-040, T-045, T-048, T-052, T-055

#### Message Length
- **Average:** 39 words (range: 30 to 50 words)
- **Tightest range:** 30–50 words — most consistent channel for length

#### Formality Level: **MEDIUM (Semi-Professional)**
Web form messages:
- Complete sentences with proper capitalisation (100%)
- No greeting (form replaces it)
- Professional but not as formal as email
- Technical precision: include exact error messages, API endpoints, plan tiers
- Often state what they've already tried: "We haven't changed anything on our end" (T-003), "When I test it from Settings it works fine" (T-034)

#### Sentiment Distribution (Web Form)
```
Sentiment 0.0–0.4 (Negative):      T-010(0.40), T-018(0.45), T-034(0.40) → 3 tickets = 20%
Sentiment 0.4–0.6 (Neutral):       T-003(0.45), T-006(0.60) etc.         → 5 tickets = 33%
Sentiment 0.6–0.8 (Positive):      T-013(0.55), T-031(0.70) etc.         → 7 tickets = 47%
```
**Key insight:** Web form sentiment is more neutral — customers are solving problems, not venting. But 20% still negative (API failures, broken integrations affecting production).

#### Priority Distribution (Web Form)
- Critical: 0/15 = 0%
- High: 6/15 = **40%** (production-affecting technical issues)
- Medium: 7/15 = 47%
- Low: 2/15 = 13%

#### Category Mix (Web Form)
- Technical: 7/15 = **47%** ← dominant category
- General: 6/15 = 40% (migration, seat management, deletion, competitor comparison)
- Billing: 1/15 = 7%
- Feedback: 1/15 = 7%

#### D-007: Web Form = Technical Investigation Channel
- **Finding:** 47% of web form tickets are technical, and they include the most detail — error messages, code context, API endpoints, libraries used. These are developers and DevOps engineers.
- **Impact on Agent:** Web form responses can be detailed (up to 300 words). Should include step-by-step instructions, code snippets where relevant, and follow-up question if debugging info is missing.
- **Status:** [x] Incorporated

#### D-008: Web Form Tickets Mention Business Impact
- **Finding:** Web form customers state business context — "CI/CD pipeline" (T-034), "15-person team from Jira" (T-031), "200+ employees evaluating NimbusFlow" (T-045). This signals urgency.
- **Impact on Agent:** Use business impact statements to set ticket priority. "CI/CD pipeline" → high priority. "Evaluating NimbusFlow" → escalate to sales.
- **Status:** [x] Incorporated

---

## Section 2: Question Categories Discovered

### 2.1 Full Category Breakdown (All 55 Tickets)

| Category | Count | % | Top Channel | Escalation Rate |
|----------|-------|---|-------------|----------------|
| General | 29 | 52.7% | WhatsApp (14) | 10/29 = 34% |
| Technical | 14 | 25.5% | Web Form (7) | 1/14 = 7% |
| Billing | 6 | 10.9% | Email (4) | 5/6 = 83% |
| Bug Report | 4 | 7.3% | Email (2) | 2/4 = 50% |
| Feedback | 2 | 3.6% | Email + Web | 0/2 = 0% |

### 2.2 Sub-Categories Within "General" (Most Common)

General tickets span very different needs. Breaking down by topic:

| Sub-Topic | Tickets | Channel Pattern |
|-----------|---------|----------------|
| Plan/feature availability | T-015, T-017, T-025, T-033, T-036, T-039, T-027 | WhatsApp only |
| Account management (add/remove users) | T-008, T-037, T-047, T-053 | All channels |
| Enterprise/compliance inquiry | T-021, T-024, T-045, T-049 | Email + Web |
| Data export / GDPR | T-009 | Email |
| Migration from competitors | T-031, T-052 | Web form |
| Authentication / login | T-022 | WhatsApp |
| Workspace management | T-028, T-047 | Web + WhatsApp |

**D-009: "General" Needs Sub-Categorisation**
- **Finding:** "General" is too broad. Plan-availability questions (74% of WhatsApp) need a quick KB lookup. Enterprise/compliance questions (T-021, T-024, T-045, T-049) need immediate escalation. They require completely different handling.
- **Impact on Agent:** Classify further after receiving message: `is_plan_question`, `is_compliance_question`, `is_account_management`. Different sub-type → different workflow.
- **Status:** [x] Incorporated

### 2.3 Technical Sub-Categories

| Sub-Topic | Tickets | Resolvable by AI |
|-----------|---------|-----------------|
| Integrations (GitHub, Slack, Figma) | T-003, T-014, T-023 | Yes (re-auth steps) |
| API / webhooks | T-005, T-010, T-018, T-034, T-038 | Yes (docs) |
| Authentication / login / SSO | T-001, T-006 | Partially |
| Mobile app | T-012, T-020, T-030, T-044 | Yes (standard fixes) |
| Sprint / task behaviour | T-032 | Yes (expected behaviour) |

**D-010: Webhooks Are the #1 Technical Pain Point**
- **Finding:** 4 webhook-related tickets (T-003, T-018, T-034, T-051) — that's 29% of all technical tickets. T-051 is a repeat contact escalation on the same issue.
- **Resolution pattern:** Common causes are: (a) wrong content field (parsed JSON vs raw body), (b) NF-dash not NF-hash format, (c) endpoint not returning 200 in 10s. All resolvable from KB.
- **Impact on Agent:** Create specific KB section for webhooks. High-confidence resolution available. But if same webhook issue appears 2+ times for same customer → escalate.
- **Status:** [x] Incorporated

---

## Section 3: Escalation Patterns

### 3.1 Escalation Statistics

```
Total tickets: 55
Pure escalate:          15 (27.3%)
Resolve-or-escalate:    4  (7.3%)  — conditional on KB result
Resolve:                35 (63.6%)
Resolve limited:        1  (1.8%)  — competitor comparison (don't answer, don't escalate)
```

**Theoretical escalation rate if all conditional tickets escalate: 34.5%**
**Target from spec: < 20%** — gap of ~14.5% that agent quality must close via good KB search.

### 3.2 Escalation Reasons Breakdown

| Reason | Count | Urgency | Tickets |
|--------|-------|---------|---------|
| Refund / billing financial | 3 | high | T-004, T-026, T-028 |
| Chargeback / billing dispute | 1 | critical | T-007 |
| Pricing negotiation / discount | 1 | normal | T-016 |
| Legal threat | 1 | critical | T-011 |
| Security incident | 2 | critical | T-011, T-029 |
| Compliance / legal request | 2 | high | T-024, T-049 |
| Data loss | 2 | critical | T-019, T-041 |
| Enterprise / sales inquiry | 2 | high | T-021, T-045 |
| Explicit human request | 1 | high | T-007 |
| Extreme negative sentiment | 2 | high | T-041, T-051 |
| Repeat contact + cancellation threat | 1 | critical | T-051 |
| Workspace ownership transfer | 1 | normal | T-053 |

### 3.3 D-011: Billing Is the #1 Escalation Driver

- **Finding:** Billing-related escalations = 5/15 = 33% of all escalations. Refunds, chargebacks, discounts, invoices — none can be handled by AI.
- **Breakdown:**
  - Refund request: T-004 ($8,700 annual)
  - Chargeback threat: T-007 (combined with explicit human request)
  - Pricing negotiation: T-016 (nonprofit discount)
  - Invoice not received: T-026 (routing to billing system)
  - Workspace deletion + refund: T-028
- **Impact on Agent:** Billing keyword detection must be highly sensitive. Even "invoice" alone → route to billing@. Never attempt to answer billing questions.
- **Status:** [x] Incorporated

### 3.4 D-012: Sentiment + Channel Predict Escalation Need

| Condition | Escalation Rate |
|-----------|----------------|
| Email + sentiment < 0.2 | 100% (4/4) |
| Email + sentiment 0.2–0.4 | 67% (2/3) |
| Email + billing category | 100% (4/4) |
| WhatsApp + any sentiment | 5% (1/19) |
| Web form + technical category | 14% (1/7) |
| Any channel + legal keywords | 100% |

**Finding:** The combination of `email + low sentiment + billing category` is the highest-risk escalation pattern. WhatsApp almost never escalates.
**Impact on Agent:** Build a composite escalation score. Channel × Sentiment × Category → probability. Not just keyword matching.

### 3.5 D-013: Dual-Routing Required for Security Incidents

- **Finding:** T-011 requires routing to BOTH `security@nimbusflow.io` AND `legal@nimbusflow.io`. T-029 routes to `security@` only. These are different codepaths.
- **Impact on Agent:** `escalate_to_human` tool must accept a `routing_targets: list[str]` parameter, not just a single target. For security + legal incidents: route to both simultaneously.
- **Status:** [x] Incorporated

### 3.6 D-014: "Resolve or Escalate" Tickets Follow a Clear Pattern

4 tickets are conditional (T-006, T-018, T-031, T-034):
- All are technical
- All require a KB search attempt first
- All have a specific fallback: "if 2 steps fail, escalate to technical team"

**Finding:** These are the tickets where agent quality makes the biggest difference. A good KB hit → resolved. A bad hit → escalation that costs the business.
**Impact on Agent:** For `resolve_or_escalate` category tickets, make 2 KB searches with different query phrasings before escalating. Document each search attempt in ticket notes.

### 3.7 D-015: Escalation Urgency Map (Confirmed)

```python
ESCALATION_URGENCY = {
    # Critical (2-hour SLA)
    "legal_threat":                       "critical",
    "security_incident":                  "critical",
    "chargeback_threat":                  "critical",
    "data_loss_reported":                 "critical",
    "repeat_contact_cancellation_threat": "critical",

    # High (2-hour SLA, different queue)
    "explicit_human_request":             "high",
    "extreme_negative_sentiment":         "high",
    "enterprise_sla_violation":           "high",
    "refund_request":                     "high",
    "compliance_legal_request":           "high",
    "enterprise_sales_inquiry":           "high",

    # Normal (4-hour SLA)
    "billing_invoice_request":            "normal",
    "pricing_negotiation":                "normal",
    "workspace_ownership_transfer":       "normal",
    "security_audit_request":             "normal",
    "knowledge_gap":                      "normal",

    # Low (24-hour SLA)
    "workspace_deletion_request":         "low",
    "enterprise_on_premises_inquiry":     "low",
    "feature_request":                    "low",
}
```

---

## Section 4: Cross-Channel Patterns

### 4.1 Same Topic, Different Channel, Different Depth

The most revealing pattern: identical topics appear across all 3 channels with dramatically different depth and intent.

#### Pattern A: Webhooks/Integrations
| Channel | Ticket | Message Style | Resolution |
|---------|--------|--------------|-----------|
| Web form | T-003 | "Since yesterday, commits with NF-[id] are no longer auto-closing tasks. We haven't changed anything on our end." | Resolve — re-auth steps |
| Web form | T-018 | "computing HMAC-SHA256 with our webhook secret but signatures don't match. Using Python requests library." | Resolve — raw body vs parsed |
| Web form | T-034 | "firing sometimes, not consistently. Test from Settings works fine. CI/CD pipeline." | Resolve/escalate |
| Email | T-051 | "4th email about the same GitHub webhook issue. Been 5 days." | Escalate — repeat contact |

**D-016: Same Issue Escalates When Unresolved Across Multiple Contacts**
- Pattern: Web form → no resolution → email → no resolution → escalate
- When T-051 arrives (email), the customer has already been through the web form / async channels.
- **Impact on Agent:** `get_customer_history()` must surface not just the channel but the topic. If topic matches current query + 2+ prior contacts → immediate escalation regardless of current channel.

#### Pattern B: Plan/Feature Availability (WhatsApp → Email)
| Channel | Ticket | Query |
|---------|--------|-------|
| WhatsApp | T-017 | "is velocity chart available on growth plan?" |
| WhatsApp | T-036 | "do we need business plan for okta sso" |
| WhatsApp | T-033 | "im on free plan how many projects can i make" |
| Email | T-021 | Enterprise plan pricing with 5 detailed questions |

**D-017: WhatsApp Serves Individual Users, Email Serves Decision-Makers**
- WhatsApp plan questions: individual contributors checking feature availability (8 words, single question)
- Email plan questions: decision-makers evaluating or negotiating (47 words, 5 questions, enterprise scale)
- **Impact on Agent:** Same topic (plan features) needs different treatment by channel. WhatsApp → quick answer. Email with enterprise inquiry → escalate to sales.

#### Pattern C: Account Access (Same Topic, Different Urgency)
| Channel | Ticket | Sentiment | Action |
|---------|--------|-----------|--------|
| WhatsApp | T-002 | 0.70 | "hi how do i reset password" → resolve |
| Email | T-001 | 0.25 | "account locked, sprint planning in 1 hour" → resolve (urgency) |

**D-018: Channel Indicates Urgency Within Same Topic**
- WhatsApp password reset = low urgency (quick lookup)
- Email password reset + ASAP + sprint in 1 hour = high urgency
- **Impact on Agent:** Context words like "ASAP", "urgent", "in X minutes/hours", "today" in email → bump priority to high. Same words on WhatsApp → normal priority (unusual for WhatsApp to have urgency).

#### Pattern D: Bug Reports Across Channels
| Channel | Ticket | Description | Priority |
|---------|--------|-------------|---------|
| WhatsApp | T-012 | "app not syncing tasks. been 2 hrs" | medium |
| WhatsApp | T-044 | "push notifications stopped working on android" | medium |
| Email | T-019 | "Tasks are randomly disappearing... 3 times in the past week" | critical |
| Email | T-041 | "tasks DISAPPEARED... lost 3 hours of work" | critical |

**D-019: Bug Severity Signals Are Channel-Specific**
- WhatsApp bug reports = personal inconvenience, single-user, usually fixable with app steps
- Email bug reports = team-wide impact, data loss, multi-occurrence, production-affecting
- **Impact on Agent:** Email bug reports get higher priority by default. WhatsApp bug reports → try standard fixes. If WhatsApp customer says "my whole team" or data is gone → escalate even on WhatsApp.

### 4.2 Geographic Diversity in WhatsApp

WhatsApp customers came from 12+ countries (based on phone prefixes):
+1 (US/Canada), +44 (UK), +91 (India), +61 (Australia), +49 (Germany), +33 (France), +20 (Turkey), +34 (Spain), +353 (Ireland), +971 (UAE), +55 (Brazil)

**D-020: WhatsApp Is the International Channel**
- **Finding:** WhatsApp is used globally. Email and web form skew to English-speaking markets.
- **Impact on Agent:** WhatsApp responses should be simpler vocabulary (non-native English common). Avoid idioms. Keep sentences short. Numbers over words ("3 steps" not "three steps").

### 4.3 Competitor Comparison: Web Form Only

Only T-052 mentions a competitor ("NimbusFlow vs Asana"). It came via web form, not WhatsApp or email.

**D-021: Competitor Comparisons Come Via Web Form (Evaluation Phase)**
- **Finding:** Customers in evaluation mode use the web form (structured, deliberate). They haven't committed yet.
- **Impact on Agent:** Web form with competitor mention → high-value prospect. Respond positively (NimbusFlow strengths), never criticise competitor, offer free trial, optionally loop in sales@.

---

## Section 5: Agent Skills Design Implications

### 5.1 Skill 1: Customer Identification — Updated Requirements

From analysis:
- WhatsApp customers (19 tickets) provide only phone — must ask for email to look up account
- Web form always provides email (structured form)
- Email always has sender address
- No ticket has both email AND phone from same customer → cross-channel merge never happens automatically in sample

```python
# Identification priority order:
1. Email from email channel header       → direct lookup
2. Email from web form submission field  → direct lookup
3. Phone from WhatsApp metadata          → lookup via customer_identifiers.identifier_type='whatsapp'
4. No identifier found (T-046 edge case) → ask: "What email is registered to your account?"
```

### 5.2 Skill 2: Sentiment Analysis — Calibrated Thresholds

From actual data distribution:
```
< 0.1  → CRITICAL: T-007(0.10), T-011(0.05), T-041(0.05), T-051(0.08) — all escalated
0.1–0.2 → HIGH RISK: T-019(0.20), T-029(0.20) — both escalated
0.2–0.35 → NEGATIVE: T-001(0.25), T-012(0.35) — resolve with empathy opener
0.35–0.5 → SLIGHTLY NEGATIVE: T-010(0.40), T-030(0.45) — resolve, no empathy needed
> 0.5  → NEUTRAL/POSITIVE: standard response
```

WhatsApp never drops below 0.35 in this dataset. Email hits as low as 0.05.

### 5.3 Skill 3: Escalation Decision — Keyword Triggers Confirmed

From all 15 escalated tickets, these keywords were present:

```python
HARD_ESCALATION_KEYWORDS = {
    # Legal (T-011)
    "lawyer", "legal", "sue", "attorneys", "court", "litigation",
    "legal team", "legal action",

    # Security (T-011, T-029)
    "unauthorized access", "compromised", "data breach", "security incident",
    "hack", "ip addresses we don't recognize",

    # Financial critical (T-007)
    "chargeback", "dispute the charge", "dispute with my bank",
    "credit card dispute",

    # Data loss (T-019, T-041)
    "disappeared", "tasks vanished", "data gone", "lost 3 hours of work",

    # Explicit human (T-007)
    "real person", "human", "speak to someone", "DEMAND to speak",
}

SOFT_ESCALATION_KEYWORDS = {
    # Billing (T-004, T-016, T-026, T-028)
    "refund", "money back", "invoice", "discount", "nonprofit",
    "prorated", "cancel and refund",

    # Compliance (T-024, T-049)
    "HIPAA", "BAA", "Business Associate Agreement", "SOC 2",
    "penetration test", "compliance",

    # Enterprise (T-021, T-045)
    "200+ employees", "Helm chart", "Kubernetes operator", "on-premises",
    "SLA guarantees", "data residency",

    # Account sensitive (T-028, T-053)
    "delete workspace", "transfer ownership", "ownership transfer",
    "cancel our subscription",

    # Cancellation threat (T-051)
    "i'm canceling", "canceling tomorrow", "going to cancel",
}
```

### 5.4 Skill 4: Channel Adaptation — Confirmed Parameters

```python
CHANNEL_PARAMS = {
    "email": {
        "greeting": "Hi {name}," if name else "Hi,",
        "max_words": 500,
        "numbered_steps": True,
        "signature": True,
        "ticket_reference": True,
        "empathy_opener": sentiment < 0.5,
        "markdown": True,
    },
    "whatsapp": {
        "greeting": None,           # Never greet on WhatsApp
        "max_chars": 300,           # Prefer. Hard limit: 1600
        "numbered_steps": False,    # Use line breaks not numbers
        "signature": False,
        "ticket_reference": True,   # Short: "Ref: NF-XXXX"
        "empathy_opener": sentiment < 0.35,
        "markdown": False,          # Plain text only
        "vocabulary": "simple",     # Non-native speakers common
    },
    "web_form": {
        "greeting": "Hi {name}," if name else None,
        "max_words": 300,
        "numbered_steps": True,     # Technical users expect them
        "signature": False,
        "ticket_reference": True,
        "empathy_opener": sentiment < 0.45,
        "markdown": False,          # Rendered in UI as plain text
        "include_code_snippets": True,  # DevOps/developer audience
    }
}
```

### 5.5 Skill 5: Knowledge Retrieval — Search Strategy

From the 35 resolvable tickets, KB hit patterns:

| Query Type | Optimal Strategy |
|-----------|-----------------|
| "how do i [action]" | Exact phrase match in Troubleshooting / Getting Started |
| "[product] not [working]" | Extract: product=app, integration=GitHub. Search by product + symptom |
| Error message quoted | Search content_hash first, then trigram on error string |
| Plan availability ("is X on growth plan") | Search: feature_name + "plan" in title |
| API/technical ("429 errors", "401") | Status code + endpoint → API & Webhooks section |

```python
# Multi-strategy search order:
1. vector_similarity(query_embedding, threshold=0.75) → max 5 results
2. if results < 2: vector_similarity(query_embedding, threshold=0.60) → max 5 results
3. if still no results: keyword_fallback(extracted_terms) → max 3 results
4. if all fail: escalate("knowledge_gap")
```

---

## Section 6: Edge Cases Master List

| # | Edge Case | Source Ticket | Symptom | Agent Handling | Test Written |
|---|-----------|--------------|---------|---------------|-------------|
| 1 | Empty message | T-046 | content="" | Ask: "It looks like your message was empty — what can I help with?" | Yes |
| 2 | Billing refund request | T-004 | "refund" keyword | Hard escalate → billing@ | Yes |
| 3 | Legal threat + security | T-011 | "legal team", "lawyers" | Critical dual-route → security@ + legal@ | Yes |
| 4 | Chargeback threat | T-007 | "dispute the charge with my bank" | Critical escalate → billing@ | Yes |
| 5 | Data loss report | T-019, T-041 | "disappeared", "DISAPPEARED" | Critical escalate → technical | Yes |
| 6 | Security incident | T-029 | "unauthorized access", "compromised" | Critical escalate → security@ | Yes |
| 7 | Repeat contact (3+) | T-051 | "RE: RE: RE:" in subject | Skip resolution, immediate escalate | Yes |
| 8 | Very negative sentiment | T-041 | sentiment=0.05, ALL CAPS | Empathy first, then escalate | Yes |
| 9 | Enterprise inquiry | T-021, T-045 | "200+ employees", "Kubernetes" | Escalate → csm@ / sales@ | Yes |
| 10 | Compliance / legal request | T-024, T-049 | "HIPAA BAA", "SOC 2", "penetration test" | Escalate → legal@ / security@ | Yes |
| 11 | Pricing negotiation | T-016 | "discount", "nonprofit discount" | Escalate → sales@ | Yes |
| 12 | Competitor comparison | T-052 | "vs Asana" | Redirect to NimbusFlow strengths, offer trial, no criticism | Yes |
| 13 | WhatsApp no customer ID | T-002 et al. | No email in message | Ask for account email before lookup | Yes |
| 14 | Workspace sensitive action | T-028, T-053 | "delete workspace", "transfer ownership" | Escalate — cannot do without identity verification | Yes |
| 15 | Feature not in docs | T-035 | "dark mode", "bulk editing" | Acknowledge, note roadmap (no timeline promise), share workaround | Yes |

---

## Section 7: Escalation Rules — Crystallised

### Hard Escalation (Immediate — 0 Resolution Attempts)

```
legal_keywords:      lawyer, sue, court, attorneys, litigation, legal action, legal team
security_keywords:   unauthorized access, compromised, data breach, hacked, security incident
chargeback_keywords: chargeback, dispute the charge, dispute with my bank, credit card dispute
data_loss_keywords:  disappeared, vanished, tasks gone, lost X hours of work, data loss
explicit_human:      real person, human agent, speak to someone, DEMAND, representative
sentiment < 0.1:     (any message)
```

### Soft Escalation (After 1 Resolution Attempt)

```
billing_keywords:    refund, money back, invoice, prorated refund, cancel subscription
compliance:          HIPAA, BAA, SOC 2, penetration test, data residency, audit report
enterprise_sales:    200+ users, Helm chart, Kubernetes operator, on-premises, SLA guarantee
account_sensitive:   delete workspace, transfer ownership, workspace deletion
sentiment < 0.25:    (if resolution attempt fails)
repeat_contact:      same issue 2+ prior tickets without resolution
```

### No-Touch Topics (Redirect Only — No Escalation)

```
competitor_mention:  "vs Asana", "vs Jira", "vs Trello", "compare to"
→ Action: Focus on NimbusFlow strengths, offer trial, don't criticise competitor
```

---

## Section 8: Performance Baseline

| Metric | Observed in Sample | Production Target | Gap |
|--------|-------------------|-------------------|-----|
| Escalation rate (pure) | 27.3% | < 20% | −7.3% |
| Escalation rate (conditional) | 34.5% | < 20% | −14.5% |
| WhatsApp escalation rate | 5.3% | < 10% | ✅ |
| Email escalation rate | 42.9% | < 35% | −7.9% |
| Web form escalation rate | 26.7% | < 20% | −6.7% |
| Resolvable tickets with good KB | 63.6% | > 80% | −16.4% |

**Key conclusion:** The gap between observed escalation rate and target (7–14%) must be closed by:
1. Accurate KB search (vector similarity, not keyword) — closes ~8%
2. Better handling of `resolve_or_escalate` tickets — closes ~4%
3. Better sub-categorisation of "general" tickets — closes ~3%

---

## Section 9: Response Templates (Channel-Confirmed)

### Email (High-Stakes, Detailed)
```
Hi {name},

{EMPATHY_OPENER if sentiment < 0.5}

{NUMBERED_STEPS or ANSWER}

{CONFIRMATION_OFFER: "Let me know if this resolves the issue or if you need any further help."}

— NimbusFlow Support
Ticket Reference: {ticket_id}
```

### WhatsApp (Direct, Plain Text, ≤ 300 chars preferred)
```
{DIRECT_ANSWER_NO_GREETING}

{OPTIONAL_LINK if complex}

Ref: {ticket_id}
```

### Web Form (Semi-Technical, Structured)
```
{OPTIONAL Hi {name},}

{ANSWER with numbered steps for technical issues}

{FOLLOW_UP_QUESTION if debugging needed}

Hope that helps! — NimbusFlow Support | Ticket: {ticket_id}
```

### Escalation (All Channels)
```
Email:    "I want to make sure you get the right help on this.
           I'm connecting you with our {team} team — they'll follow up within {SLA}.
           Your reference is {ticket_id}."

WhatsApp: "Connecting you to our team now. Ref: {ticket_id}.
           Response within {SLA}."

Web Form: "I've flagged this for our {team} team. Ticket {ticket_id} —
           they'll reach out to your email within {SLA}."
```
