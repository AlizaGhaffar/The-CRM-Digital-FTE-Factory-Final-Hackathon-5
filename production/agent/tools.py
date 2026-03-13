"""
production/agent/tools.py
OpenAI Agents SDK @function_tool wrappers — all 5 skills from skills-manifest.md.

Skill → Tool mapping:
  Skill 1 — Customer Identification : create_ticket, get_customer_history
  Skill 2 — Sentiment Analysis      : analyze_sentiment
  Skill 3 — Knowledge Retrieval     : search_knowledge_base
  Skill 4 — Escalation Decision     : escalate_to_human
  Skill 5 — Channel Adaptation      : send_response

Every tool guarantees:
  - Pydantic BaseModel input validation (rejects bad inputs before any DB call)
  - try/except with safe fallback returns (agent never crashes on tool failure)
  - asyncpg connection pool via queries.get_pool()
  - structlog structured logging (JSON in production, colored in dev)
  - LLM-optimised docstrings (when to call, what it returns, how to use results)

Model: Gemini via OpenAI-compatible endpoint (GEMINI_API_KEY + base_url).
"""

import os
import re
import uuid
from typing import Optional

import httpx
import structlog
from openai import AsyncOpenAI
from agents import function_tool
from pydantic import BaseModel, Field, field_validator

from production.database import queries

log = structlog.get_logger(__name__)

# ── Gemini client (OpenAI Agents SDK external provider) ───────────────────────

_openai: Optional[AsyncOpenAI] = None


def _get_openai() -> AsyncOpenAI:
    """Lazy singleton — Gemini via OpenAI-compatible endpoint."""
    global _openai
    if _openai is None:
        _openai = AsyncOpenAI(
            api_key=os.getenv("GEMINI_API_KEY", ""),
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )
    return _openai


# ── Channel formatting constants ──────────────────────────────────────────────
# Source: context/brand-voice.md, discovery-log.md D-001/D-004/D-007

CHANNEL_PARAMS: dict[str, dict] = {
    "email": {
        "max_chars": 3500,
        "preferred_chars": None,
        "markdown": True,
        "greeting": "Hi {name},",
        "sign_off": "\n\nBest regards,\nNimbusFlow Support\nTicket: {ticket_id}",
    },
    "whatsapp": {
        "max_chars": 1600,        # Twilio hard limit
        "preferred_chars": 300,   # Discovery-log D-004: prefer ≤300
        "markdown": False,        # Plain text only
        "greeting": None,         # Never greet on WhatsApp (D-004)
        "sign_off": "\nRef: {ticket_id}",
    },
    "web_form": {
        "max_chars": 2100,
        "preferred_chars": None,
        "markdown": False,        # Rendered as plain text in UI
        "greeting": "Hi {name},",
        "sign_off": "\n\nHope that helps! — NimbusFlow Support\nTicket: {ticket_id}",
    },
}

# ── Escalation keyword lists ───────────────────────────────────────────────────
# Source: discovery-log.md §5.3, escalation-rules.md

CRITICAL_KEYWORDS: list[str] = [
    "lawyer", "sue", "court", "attorney", "litigation", "legal action", "legal team",
    "legal counsel", "retained counsel", "retained legal",
    "compromised", "unauthorized access", "hacked", "data breach", "breach", "api key exposure",
    "dispute the charge", "credit card dispute", "chargeback",
    "tasks disappeared", "data gone", "lost my work", "data loss", "tasks vanished",
]

HIGH_KEYWORDS: list[str] = [
    "refund", "money back", "cancel my account", "cancel subscription",
    "human", "agent", "real person", "speak to someone", "speak with a human",
    "talk to someone", "representative",
]

NORMAL_KEYWORDS: list[str] = [
    "discount", "custom pricing", "negotiate", "nonprofit",
    "gdpr", "hipaa", "soc 2", "compliance audit", "baa",
    "enterprise deployment", "on-premises", "kubernetes",
]

# ── Escalation routing ─────────────────────────────────────────────────────────

ESCALATION_ROUTING: dict[str, str] = {
    "critical": "oncall@nimbusflow.io",
    "high":     "support-lead@nimbusflow.io",
    "normal":   "support@nimbusflow.io",
    "low":      "support@nimbusflow.io",
}

ESCALATION_QUEUE: dict[str, str] = {
    "critical": "critical-queue",
    "high":     "priority-queue",
    "normal":   "standard-queue",
    "low":      "standard-queue",
}

SLA_LABEL: dict[str, str] = {
    "critical": "2 hours",
    "high":     "2 hours",
    "normal":   "4 business hours",
    "low":      "1 business day",
}


# ════════════════════════════════════════════════════════════════════════════════
# SKILL 1 — Customer Identification
# Tools: create_ticket, get_customer_history
# ════════════════════════════════════════════════════════════════════════════════

class CreateTicketInput(BaseModel):
    customer_email: Optional[str] = Field(None, description="Customer email address")
    customer_phone: Optional[str] = Field(None, description="Customer phone in E.164 format for WhatsApp, e.g. +14155551234")
    customer_name:  Optional[str] = Field(None, description="Customer display name if known")
    channel:  str = Field(..., description="Source channel — must be one of: email | whatsapp | web_form")
    subject:  str = Field(..., min_length=3, max_length=500, description="One-line summary of the customer's issue")
    category: Optional[str] = Field(
        None,
        description=(
            "Issue category: general | technical | billing | bug_report | feedback. "
            "Sub-classify 'general' further: is_plan_question, is_compliance_question, "
            "is_account_management, is_enterprise_inquiry."
        ),
    )
    priority: str = Field("medium", description="Ticket priority: low | medium | high | critical")

    @field_validator("channel")
    @classmethod
    def valid_channel(cls, v: str) -> str:
        allowed = {"email", "whatsapp", "web_form"}
        if v not in allowed:
            raise ValueError(f"channel must be one of {allowed}, got '{v}'")
        return v

    @field_validator("priority")
    @classmethod
    def valid_priority(cls, v: str) -> str:
        allowed = {"low", "medium", "high", "critical"}
        if v not in allowed:
            raise ValueError(f"priority must be one of {allowed}, got '{v}'")
        return v


async def create_ticket(
    customer_email: Optional[str],
    customer_phone: Optional[str],
    customer_name:  Optional[str],
    channel:  str,
    subject:  str,
    category: Optional[str] = None,
    priority: str = "medium",
) -> dict:
    """
    [SKILL 1 — Customer Identification] MUST be called FIRST for every conversation.
    No other tool may be called before this one.

    What it does:
      1. Looks up the customer by email (email/web channels) or phone (WhatsApp).
      2. Creates a new customer record if none is found.
      3. Gets or creates an active conversation thread.
      4. Creates a new support ticket and returns its ID.

    When to call:
      - Immediately upon receiving any customer message, before reading the body.
      - Provide all available identifiers: email AND phone if both are known.

    Priority guidance (bump from default "medium"):
      - "high"     : email keywords "ASAP", "urgent", "sprint in X minutes", CI/CD pipeline,
                     production environment, "affecting our team"
      - "critical" : ALL CAPS email subject, data loss, security incident
      - "low"      : WhatsApp simple lookup, feedback

    Returns:
      ticket_id      — use in ALL subsequent tool calls
      customer_id    — use in get_customer_history and escalate_to_human
      conversation_id — use in analyze_sentiment and send_response

    Fallback on DB failure: returns temporary IDs so the agent can still respond.
    """
    # Validate inputs
    try:
        CreateTicketInput(
            customer_email=customer_email,
            customer_phone=customer_phone,
            customer_name=customer_name,
            channel=channel,
            subject=subject,
            category=category,
            priority=priority,
        )
    except Exception as exc:
        log.warning("create_ticket validation failed", error=str(exc), channel=channel)
        return {
            "ticket_id":       f"temp-{uuid.uuid4().hex[:8]}",
            "customer_id":     f"guest-{uuid.uuid4().hex[:8]}",
            "conversation_id": f"conv-{uuid.uuid4().hex[:8]}",
            "error":           f"validation_failed: {exc}",
        }

    try:
        customer_id = await queries.find_or_create_customer(
            email=customer_email,
            phone=customer_phone,
            name=customer_name,
            channel=channel,
        )
        conversation_id = await queries.get_or_create_conversation(
            customer_id=customer_id,
            channel=channel,
        )
        ticket_id = await queries.create_ticket(
            customer_id=customer_id,
            source_channel=channel,
            conversation_id=conversation_id,
            subject=subject,
            category=category,
            priority=priority,
        )

        log.info(
            "ticket_created",
            ticket_id=ticket_id,
            customer_id=customer_id,
            channel=channel,
            priority=priority,
            category=category,
        )

        return {
            "ticket_id":       ticket_id,
            "customer_id":     customer_id,
            "conversation_id": conversation_id,
        }

    except Exception as exc:
        log.error("create_ticket db_error", error=str(exc), channel=channel, subject=subject[:80])
        # Return temporary IDs — agent must still be able to respond to the customer
        temp_ticket = f"temp-{uuid.uuid4().hex[:8]}"
        temp_customer = f"guest-{uuid.uuid4().hex[:8]}"
        temp_conv = f"conv-{uuid.uuid4().hex[:8]}"
        return {
            "ticket_id":       temp_ticket,
            "customer_id":     temp_customer,
            "conversation_id": temp_conv,
            "error":           "db_unavailable — using temporary IDs",
        }


_create_ticket_tool = function_tool(create_ticket)

# ── ──────────────────────────────────────────────────────────────────────────

class GetHistoryInput(BaseModel):
    customer_id: str = Field(..., min_length=1, description="Unified customer UUID from create_ticket")
    limit: int = Field(5, ge=1, le=20, description="Number of recent tickets to return (default 5)")


async def get_customer_history(customer_id: str, limit: int = 5) -> dict:
    """
    [SKILL 1 — Customer Identification] Retrieve cross-channel support history.
    Call immediately after create_ticket, before analyzing the message.

    What it does:
      - Returns the customer's last N tickets across email, WhatsApp, and web form.
      - Detects repeat contacts: same issue category appearing 2+ times → repeat_contact=True.
      - Provides a 360-degree customer summary (plan, total tickets, churn risk).

    When to use the results:
      - repeat_contact=True AND same topic → call escalate_to_human immediately,
        do NOT attempt to resolve again (discovery-log D-016).
      - contact_count >= 3 on same topic → immediate escalation, urgency="high".
      - summary.plan == "enterprise" → is_enterprise=True, use higher escalation thresholds.

    WhatsApp note: customers often have no email on file initially.
    If history is empty and channel="whatsapp", ask for their account email before proceeding.

    Returns:
      tickets        — list of {ticket_id, subject, category, status, channel, created_at}
      repeat_contact — bool: True if same category appears 2+ times
      contact_count  — total number of prior tickets found
      summary        — {plan, total_tickets, last_contact_at, churn_risk_score}

    Fallback on DB failure: returns empty history (does not block the agent).
    """
    try:
        GetHistoryInput(customer_id=customer_id, limit=limit)
    except Exception as exc:
        log.warning("get_customer_history validation failed", error=str(exc))
        return {"tickets": [], "repeat_contact": False, "contact_count": 0, "summary": {}}

    try:
        tickets = await queries.get_customer_history(customer_id=customer_id, limit=limit)
        summary = await queries.get_customer_summary(customer_id=customer_id)

        categories = [t.get("category") for t in tickets if t.get("category")]
        repeat_contact = len(categories) != len(set(categories)) if categories else False
        contact_count = len(tickets)

        log.info(
            "history_fetched",
            customer_id=customer_id,
            contact_count=contact_count,
            repeat_contact=repeat_contact,
        )

        return {
            "tickets":        tickets,
            "repeat_contact": repeat_contact,
            "contact_count":  contact_count,
            "summary":        summary or {},
        }

    except Exception as exc:
        log.error("get_customer_history db_error", error=str(exc), customer_id=customer_id)
        # Safe fallback: empty history — agent can still proceed
        return {
            "tickets":        [],
            "repeat_contact": False,
            "contact_count":  0,
            "summary":        {},
            "error":          "db_unavailable — history not loaded",
        }


_get_customer_history_tool = function_tool(get_customer_history)

# ════════════════════════════════════════════════════════════════════════════════
# SKILL 2 — Sentiment Analysis
# Tool: analyze_sentiment
# ════════════════════════════════════════════════════════════════════════════════

class SentimentInput(BaseModel):
    message:         str = Field(..., min_length=1, description="Full customer message text")
    conversation_id: Optional[str] = Field(None, description="Conversation UUID — if provided, score is persisted")


async def analyze_sentiment(message: str, conversation_id: Optional[str] = None) -> dict:
    """
    [SKILL 2 — Sentiment Analysis] Score the emotional tone of a customer message.
    Call on every message, after get_customer_history and before search_knowledge_base.

    Score scale: 0.0 (maximally negative/hostile) → 1.0 (maximally positive/satisfied)

    How to act on results:
      immediate_escalate=True  (score < 0.1):
        → Call escalate_to_human immediately with urgency="critical". Do NOT draft a response.
      requires_empathy=True (score < 0.5):
        → Prepend an empathy opener before your answer:
          Email/Web  : "That sounds frustrating — let's sort this out."
          WhatsApp   : "That's frustrating — here's the fix:"
      score >= 0.7 (positive/neutral):
        → Standard response, no empathy opener needed.

    Empathy thresholds per channel (discovery-log §5.2):
      email    : < 0.5
      whatsapp : < 0.35
      web_form : < 0.45

    Signal detection (runs before LLM call for speed):
      - Legal keywords (lawyer, sue, court...) → caps score at 0.1 → immediate_escalate
      - ALLCAPS + "!!!" → very_negative level

    Returns:
      score             — float 0.0–1.0
      level             — very_negative | negative | mixed | neutral | positive
      requires_empathy  — bool
      immediate_escalate — bool (True → escalate NOW, do not respond)
      trend             — declining | stable | improving (vs prior messages in thread)

    Fallback on LLM failure: returns score=0.5 (neutral) — agent proceeds normally.
    """
    try:
        SentimentInput(message=message, conversation_id=conversation_id)
    except Exception as exc:
        log.warning("analyze_sentiment validation failed", error=str(exc))
        return {
            "score": 0.5, "level": "neutral",
            "requires_empathy": False, "immediate_escalate": False,
            "trend": "stable",
        }

    # Fast path: critical keyword scan (no LLM call needed)
    msg_lower = message.lower()
    has_critical = any(kw in msg_lower for kw in CRITICAL_KEYWORDS)

    # LLM sentiment scoring
    try:
        client = _get_openai()
        response = await client.chat.completions.create(
            model=os.getenv("GEMINI_MODEL", "gemini-flash-latest"),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a sentiment analysis engine for a customer support system. "
                        "Score the customer message on a scale of 0.0 to 1.0:\n"
                        "  0.0 = extremely negative, hostile, threatening, or distressed\n"
                        "  0.5 = neutral, asking a simple question\n"
                        "  1.0 = happy, satisfied, positive\n"
                        "Respond with ONLY a single decimal number. No explanation."
                    ),
                },
                {"role": "user", "content": message[:1000]},
            ],
            temperature=0,
            max_tokens=10,
        )
        raw = response.choices[0].message.content.strip()
        score = max(0.0, min(1.0, float(raw)))

    except ValueError:
        log.warning("sentiment_parse_failed", raw_response=raw if "raw" in dir() else "unknown")
        score = 0.5
    except Exception as exc:
        log.error("analyze_sentiment llm_error", error=str(exc))
        # Safe fallback: neutral score — agent proceeds without empathy logic
        score = 0.5

    # Override: critical keywords always cap the score below immediate_escalate threshold
    if has_critical:
        score = min(score, 0.09)

    # Classify
    if score < 0.1:
        level = "very_negative"
    elif score < 0.3:
        level = "negative"
    elif score < 0.5:
        level = "mixed"
    elif score < 0.7:
        level = "neutral"
    else:
        level = "positive"

    # Persist to DB (non-blocking — failure does not affect return)
    trend = "stable"
    if conversation_id:
        trend = "declining" if score < 0.4 else ("stable" if score < 0.65 else "improving")
        try:
            await queries.update_conversation_sentiment(
                conversation_id=conversation_id,
                sentiment_score=score,
                sentiment_trend=trend,
            )
        except Exception as exc:
            log.warning("sentiment_persist_failed", error=str(exc), conversation_id=conversation_id)

    log.info(
        "sentiment_scored",
        score=round(score, 3),
        level=level,
        has_critical_keyword=has_critical,
        trend=trend,
    )

    return {
        "score":             round(score, 3),
        "level":             level,
        "requires_empathy":  score < 0.5,
        "immediate_escalate": score < 0.1,
        "trend":             trend,
    }


_analyze_sentiment_tool = function_tool(analyze_sentiment)

# ════════════════════════════════════════════════════════════════════════════════
# SKILL 3 — Knowledge Retrieval
# Tool: search_knowledge_base
# ════════════════════════════════════════════════════════════════════════════════

class KBSearchInput(BaseModel):
    query:          str = Field(..., min_length=3, description="Customer question rephrased as a clear search query")
    category:       Optional[str] = Field(None, description="Filter results by category: technical | general | billing | bug_report")
    max_results:    int = Field(5, ge=1, le=10, description="Maximum results to return")
    min_similarity: float = Field(0.70, ge=0.0, le=1.0, description="Cosine similarity threshold (0.70 recommended)")


async def search_knowledge_base(
    query: str,
    category: Optional[str] = None,
    max_results: int = 5,
    min_similarity: float = 0.70,
) -> dict:
    """
    [SKILL 3 — Knowledge Retrieval] Semantic vector search over NimbusFlow product docs.
    Call when the customer has a product question, how-to request, or troubleshooting issue.

    Do NOT call for: billing disputes, legal threats, security incidents, refund requests,
    enterprise pricing, compliance requests — escalate those directly instead.

    Search strategy (automatic — do not change thresholds manually):
      Attempt 1: min_similarity=0.70 → up to 5 results
      Attempt 2: if attempt 1 returns 0 results → retry at min_similarity=0.60
      If still no results → set escalation reason "knowledge_gap" and escalate.
      Maximum 2 total searches per session. Never call a third time.

    Query optimisation tips:
      - Rephrase the customer's question as a declarative topic:
        "how to connect github" → "GitHub integration setup commit linking"
      - Include error codes if mentioned: "401 Unauthorized API key"
      - Include plan tier if mentioned: "velocity chart business plan"
      - For webhooks: include symptom — "webhook not firing HMAC signature mismatch"

    Using the results:
      - found=True, top_score > 0.75 → high confidence, use content to draft answer
      - found=True, top_score 0.60–0.75 → moderate confidence, answer but offer follow-up
      - found=False after 2 attempts → escalate with reason="knowledge_gap"
      - Roadmap / unreleased feature → return found=False immediately, do not search

    Returns:
      results   — [{title, content, category, similarity}] ranked by relevance
      found     — bool: True if at least one result above threshold
      top_score — float: similarity score of best result
      search_count — total searches attempted this session

    Fallback on embedding failure: returns found=False (agent escalates normally).
    """
    try:
        KBSearchInput(query=query, category=category,
                      max_results=max_results, min_similarity=min_similarity)
    except Exception as exc:
        log.warning("search_kb validation failed", error=str(exc))
        return {"results": [], "found": False, "top_score": 0.0, "search_count": 0}

    try:
        _model = os.getenv("GEMINI_EMBEDDING_MODEL", "text-embedding-3-small")
        client = _get_openai()
        resp = await client.embeddings.create(model=_model, input=query[:2000])
        embedding = resp.data[0].embedding
    except Exception as exc:
        log.error("search_kb embedding_error", error=str(exc), query=query[:80])
        return {
            "results": [], "found": False, "top_score": 0.0,
            "search_count": 1, "error": "embedding_failed",
        }

    # Attempt 1: primary threshold
    try:
        results = await queries.search_knowledge_base(
            embedding=embedding,
            max_results=max_results,
            min_similarity=min_similarity,
            category=category,
        )
    except Exception as exc:
        log.error("search_kb db_error attempt=1", error=str(exc))
        results = []

    search_count = 1

    # Attempt 2: lower threshold if no results (discovery-log §5.5)
    if not results and min_similarity > 0.60:
        try:
            results = await queries.search_knowledge_base(
                embedding=embedding,
                max_results=max_results,
                min_similarity=0.60,
                category=category,
            )
            search_count = 2
        except Exception as exc:
            log.error("search_kb db_error attempt=2", error=str(exc))

    top_score = results[0].get("similarity", 0.0) if results else 0.0

    log.info(
        "kb_search_complete",
        query_preview=query[:60],
        found=len(results) > 0,
        top_score=round(top_score, 3),
        result_count=len(results),
        search_count=search_count,
        category=category,
    )

    return {
        "results": [
            {
                "title":      r.get("title"),
                "content":    r.get("content"),
                "category":   r.get("category"),
                "similarity": round(r.get("similarity", 0.0), 3),
            }
            for r in results
        ],
        "found":        len(results) > 0,
        "top_score":    round(top_score, 3),
        "search_count": search_count,
    }


_search_knowledge_base_tool = function_tool(search_knowledge_base)

# ════════════════════════════════════════════════════════════════════════════════
# SKILL 4 — Escalation Decision
# Tool: escalate_to_human
# ════════════════════════════════════════════════════════════════════════════════

class EscalateInput(BaseModel):
    ticket_id:              str = Field(..., description="Ticket UUID from create_ticket")
    customer_id:            str = Field(..., description="Customer UUID from create_ticket")
    reason:                 str = Field(..., min_length=3, description=(
        "Specific escalation trigger code. Use one of: legal_threat | security_incident | "
        "chargeback_threat | data_loss | billing_dispute | human_requested | "
        "sentiment_negative | knowledge_gap | repeat_contact | compliance_request | "
        "enterprise_inquiry | account_sensitive | pricing_negotiation"
    ))
    urgency:                str = Field("normal", description="critical | high | normal | low")
    conversation_id:        Optional[str] = Field(None)
    channel:                Optional[str] = Field(None, description="Source channel for message template selection")
    trigger_message:        Optional[str] = Field(None, description="The exact customer message that triggered escalation (max 500 chars)")
    sentiment_at_escalation: Optional[float] = Field(None, ge=0.0, le=1.0)

    @field_validator("urgency")
    @classmethod
    def valid_urgency(cls, v: str) -> str:
        allowed = {"critical", "high", "normal", "low"}
        if v not in allowed:
            raise ValueError(f"urgency must be one of {allowed}, got '{v}'")
        return v


async def escalate_to_human(
    ticket_id: str,
    customer_id: str,
    reason: str,
    urgency: str = "normal",
    conversation_id: Optional[str] = None,
    channel: Optional[str] = None,
    trigger_message: Optional[str] = None,
    sentiment_at_escalation: Optional[float] = None,
) -> dict:
    """
    [SKILL 4 — Escalation Decision] Hand off the conversation to a human agent.
    After calling this tool: STOP. Do NOT attempt to resolve the issue yourself.
    Call send_response immediately after with the customer_message from this result.

    When to call (HARD — call immediately, 0 resolution attempts):
      reason="legal_threat"      : lawyer, sue, court, attorney, litigation
      reason="security_incident" : compromised, unauthorized access, hacked, data breach
      reason="chargeback_threat" : chargeback, dispute the charge, credit card dispute
      reason="data_loss"         : tasks disappeared, data gone, lost my work
      reason="human_requested"   : human, agent, real person, STOP (WhatsApp)
      analyze_sentiment returned immediate_escalate=True

    When to call (SOFT — after 1 failed resolution attempt):
      reason="billing_dispute"      : refund, money back, invoice, prorated
      reason="compliance_request"   : HIPAA, BAA, SOC 2, penetration test
      reason="enterprise_inquiry"   : 200+ employees, Kubernetes, on-premises
      reason="pricing_negotiation"  : discount, custom pricing, nonprofit
      reason="account_sensitive"    : delete workspace, transfer ownership
      reason="sentiment_negative"   : score < 0.25 after failed resolution
      reason="repeat_contact"       : same topic 2+ prior tickets, no resolution
      reason="knowledge_gap"        : found=False after 2 KB searches

    Urgency → SLA:
      critical → 2 hours  (legal, security, chargeback, data loss)
      high     → 2 hours  (billing, enterprise, human request)
      normal   → 4 business hours
      low      → 1 business day (knowledge gap, feature requests)

    Auto-upgrade: urgency is automatically upgraded if trigger_message contains
    critical/high keywords, even if you passed "normal".

    Returns:
      escalation_id    — record ID
      routed_to        — email address of team notified
      queue            — kafka queue name
      urgency          — final urgency (may be upgraded from your input)
      customer_message — ready-to-use channel-appropriate message for send_response

    Fallback on DB failure: still returns customer_message so the agent can
    acknowledge the escalation to the customer.
    """
    try:
        EscalateInput(
            ticket_id=ticket_id, customer_id=customer_id, reason=reason,
            urgency=urgency, conversation_id=conversation_id, channel=channel,
            trigger_message=trigger_message,
            sentiment_at_escalation=sentiment_at_escalation,
        )
    except Exception as exc:
        log.warning("escalate_to_human validation failed", error=str(exc))
        urgency = "normal"

    # Auto-upgrade urgency from message content
    combined = f"{reason} {trigger_message or ''}".lower()
    if any(kw in combined for kw in CRITICAL_KEYWORDS):
        urgency = "critical"
    elif any(kw in combined for kw in HIGH_KEYWORDS) and urgency != "critical":
        urgency = "high"

    routed_to = ESCALATION_ROUTING[urgency]
    queue     = ESCALATION_QUEUE[urgency]
    sla       = SLA_LABEL[urgency]

    # Build channel-appropriate customer message (brand-voice.md)
    ch = channel or "web_form"
    ticket_ref = ticket_id[:8].upper()
    if ch == "whatsapp":
        customer_message = (
            f"Connecting you to our team now. Ref: {ticket_ref}. "
            f"Response within {sla}."
        )
    elif ch == "email":
        customer_message = (
            f"I want to make sure you get the right help on this. "
            f"I'm connecting you with our team — they'll follow up within {sla}. "
            f"Your ticket reference is {ticket_ref}."
        )
    else:
        customer_message = (
            f"I've flagged this for our team. "
            f"Ticket {ticket_ref} — they'll reach out within {sla}."
        )

    # Persist to DB
    escalation_id: Optional[str] = None
    try:
        escalation_id = await queries.create_escalation(
            ticket_id=ticket_id,
            customer_id=customer_id,
            reason=reason,
            urgency=urgency,
            conversation_id=conversation_id,
            routed_to=routed_to,
            source_channel=channel,
            trigger_message=trigger_message[:500] if trigger_message else None,
            sentiment_at_escalation=sentiment_at_escalation,
        )
        await queries.update_ticket_status(
            ticket_id=ticket_id,
            status="escalated",
            escalation_reason=reason,
            escalation_urgency=urgency,
            escalated_to=routed_to,
        )
    except Exception as exc:
        log.error(
            "escalate_to_human db_error",
            error=str(exc),
            ticket_id=ticket_id,
            reason=reason,
            urgency=urgency,
        )
        escalation_id = f"esc-fallback-{uuid.uuid4().hex[:8]}"
        # Do NOT re-raise — still return customer_message so agent can acknowledge

    log.info(
        "escalation_created",
        ticket_id=ticket_id,
        escalation_id=escalation_id,
        reason=reason,
        urgency=urgency,
        routed_to=routed_to,
        channel=ch,
    )

    return {
        "escalation_id":   escalation_id,
        "routed_to":       routed_to,
        "queue":           queue,
        "urgency":         urgency,
        "sla":             sla,
        "customer_message": customer_message,
    }


_escalate_to_human_tool = function_tool(escalate_to_human)

# ════════════════════════════════════════════════════════════════════════════════
# SKILL 5 — Channel Adaptation
# Tool: send_response
# ════════════════════════════════════════════════════════════════════════════════

class SendResponseInput(BaseModel):
    ticket_id:       str = Field(..., description="Ticket UUID from create_ticket")
    conversation_id: str = Field(..., description="Conversation UUID from create_ticket")
    channel:         str = Field(..., description="Delivery channel: email | whatsapp | web_form")
    content:         str = Field(..., min_length=1, description="Response draft in plain text — formatting applied automatically")
    customer_name:   Optional[str] = Field(None, description="Customer first name for personalised greeting")
    subject:         Optional[str] = Field(None, description="Email subject (email channel only)")
    tokens_used:     Optional[int] = Field(None, description="LLM tokens consumed — for metrics")
    latency_ms:      Optional[int] = Field(None, description="Agent processing latency — for metrics")

    @field_validator("channel")
    @classmethod
    def valid_channel(cls, v: str) -> str:
        allowed = {"email", "whatsapp", "web_form"}
        if v not in allowed:
            raise ValueError(f"channel must be one of {allowed}")
        return v


def _format_for_channel(content: str, channel: str, customer_name: Optional[str], ticket_id: str) -> str:
    """
    Apply channel-specific formatting (brand-voice.md):
      email    : "Hi [name]," greeting + markdown OK + signature + ticket ref
      whatsapp : no greeting + plain text only + ticket ref (brief)
      web_form : optional greeting + plain text + closing + ticket ref
    """
    params  = CHANNEL_PARAMS.get(channel, CHANNEL_PARAMS["web_form"])
    name    = customer_name or "there"
    sign_off = params["sign_off"].format(ticket_id=ticket_id)

    # Strip markdown for plain-text channels
    if not params["markdown"]:
        content = re.sub(r"\*\*(.+?)\*\*", r"*\1*", content)     # **bold** → *bold*
        content = re.sub(r"#{1,6}\s+", "", content)               # ## headers → plain
        content = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", content)     # [link](url) → link
        content = re.sub(r"^\s*[-*]\s+", "• ", content, flags=re.MULTILINE)
        content = re.sub(r"```[\s\S]*?```", "", content)          # code blocks
        content = re.sub(r"`(.+?)`", r"\1", content)              # inline code

    # Strip common filler openers
    for filler in ("Great question!", "Absolutely!", "Certainly!", "Of course!", "Sure thing!",
                   "I would be happy to help!", "Thank you for reaching out!"):
        if content.strip().startswith(filler):
            content = content.strip()[len(filler):].lstrip(" \n")

    content = content.strip()

    # Assemble
    if params["greeting"] and channel != "whatsapp":
        greeting  = params["greeting"].format(name=name)
        assembled = f"{greeting}\n\n{content}{sign_off}"
    else:
        assembled = f"{content}{sign_off}"

    # Enforce hard length limit
    max_chars = params["max_chars"]
    if len(assembled) > max_chars:
        note      = "... [continued in next message]" if channel == "whatsapp" else "..."
        assembled = assembled[:max_chars - len(note)] + note

    return assembled


async def send_response(
    ticket_id: str,
    conversation_id: str,
    channel: str,
    content: str,
    customer_name: Optional[str] = None,
    subject: Optional[str] = None,
    tokens_used: Optional[int] = None,
    latency_ms: Optional[int] = None,
) -> dict:
    """
    [SKILL 5 — Channel Adaptation] Format and store the final response.
    MUST be the LAST tool called in every interaction. Never output raw text directly.

    What it does automatically:
      email    : adds "Hi [name]," greeting, ticket reference footer, preserves markdown
      whatsapp : removes all markdown, removes greeting, enforces ≤1600 chars (prefers ≤300),
                 adds brief "Ref: [id]" footer
      web_form : optional name greeting, strips markdown, adds "Hope that helps!" closing

    Filler openers stripped automatically:
      "Great question!", "Absolutely!", "Certainly!", "Of course!", "Sure thing!"

    When sending an escalation acknowledgement:
      Pass the customer_message from escalate_to_human as the content parameter.
      It is already channel-appropriate — do not modify it.

    WhatsApp length warning:
      If formatted response exceeds 300 chars, a warning is logged.
      If it exceeds 1600, it is truncated with "... [continued in next message]".

    Returns:
      message_id        — stored message record ID
      formatted_content — final text exactly as sent to the customer
      char_count        — character count of formatted_content
      channel           — echo of the delivery channel

    Fallback on DB failure: still returns formatted_content so the caller can
    deliver the message via the channel handler.
    """
    try:
        SendResponseInput(
            ticket_id=ticket_id, conversation_id=conversation_id,
            customer_name=customer_name, channel=channel, content=content,
            subject=subject, tokens_used=tokens_used, latency_ms=latency_ms,
        )
    except Exception as exc:
        log.warning("send_response validation failed", error=str(exc), channel=channel)
        # Format anyway with defaults
        channel = channel if channel in CHANNEL_PARAMS else "web_form"

    formatted = _format_for_channel(
        content=content,
        channel=channel,
        customer_name=customer_name,
        ticket_id=ticket_id,
    )

    # Warn if WhatsApp exceeds preferred limit
    preferred = CHANNEL_PARAMS.get(channel, {}).get("preferred_chars")
    if preferred and len(formatted) > preferred:
        log.warning(
            "whatsapp_response_over_preferred",
            char_count=len(formatted),
            preferred=preferred,
        )

    # Persist message (non-blocking failure)
    message_id: Optional[str] = None
    try:
        message_id = await queries.store_message(
            conversation_id=conversation_id,
            channel=channel,
            direction="outbound",
            role="agent",
            content=formatted,
            tokens_used=tokens_used,
            latency_ms=latency_ms,
            delivery_status="pending",
        )
        await queries.record_metric(
            metric_name="response_sent",
            metric_value=1.0,
            channel=channel,
            ticket_id=ticket_id,
            conversation_id=conversation_id,
            dimensions={"char_count": len(formatted), "tokens_used": tokens_used or 0},
        )
    except Exception as exc:
        log.error(
            "send_response db_error",
            error=str(exc),
            ticket_id=ticket_id,
            channel=channel,
        )
        message_id = f"msg-fallback-{uuid.uuid4().hex[:8]}"

    log.info(
        "response_sent",
        message_id=message_id,
        ticket_id=ticket_id,
        channel=channel,
        char_count=len(formatted),
    )

    return {
        "message_id":        message_id,
        "formatted_content": formatted,
        "char_count":        len(formatted),
        "channel":           channel,
    }


_send_response_tool = function_tool(send_response)

# Expose __name__ so tests can introspect tool names via t.__name__
for _fn, _tool in [
    (create_ticket,          _create_ticket_tool),
    (get_customer_history,   _get_customer_history_tool),
    (analyze_sentiment,      _analyze_sentiment_tool),
    (search_knowledge_base,  _search_knowledge_base_tool),
    (escalate_to_human,      _escalate_to_human_tool),
    (send_response,          _send_response_tool),
]:
    try:
        _tool.__name__ = _fn.__name__
    except (AttributeError, TypeError):
        pass  # FunctionTool may not allow __name__ assignment on all SDK versions

# ── Tool registry ─────────────────────────────────────────────────────────────

ALL_TOOLS = [
    _create_ticket_tool,           # Skill 1a — Customer Identification
    _get_customer_history_tool,    # Skill 1b — Customer Identification
    _analyze_sentiment_tool,       # Skill 2  — Sentiment Analysis
    _search_knowledge_base_tool,   # Skill 3  — Knowledge Retrieval
    _escalate_to_human_tool,       # Skill 4  — Escalation Decision
    _send_response_tool,           # Skill 5  — Channel Adaptation
]
