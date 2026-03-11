"""
Exercise 1.2 — Core Agent Loop
src/agent/core.py

Six-step pipeline:
  1. Ingest     - Accept raw channel payload + metadata
  2. Normalize  - Produce canonical InboundMessage regardless of source
  3. Search     - Query product-docs.md for relevant sections
  4. Generate   - Build brand-voice response via OpenAI (KB fallback when unavailable)
  5. Format     - Shape for channel (email / whatsapp / web_form)
  6. Escalate   - Apply escalation-rules.md; short-circuits steps 4-5 when triggered

Run:
    python src/agent/core.py --ticket T-001
    python src/agent/core.py --all-tickets
    python src/agent/core.py --channel whatsapp --message "how do i reset password"
"""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).parent.parent.parent
CONTEXT_DIR = _ROOT / "context"

KB_PATH = CONTEXT_DIR / "product-docs.md"
COMPANY_PROFILE_PATH = CONTEXT_DIR / "company-profile.md"
BRAND_VOICE_PATH = CONTEXT_DIR / "brand-voice.md"
ESCALATION_RULES_PATH = CONTEXT_DIR / "escalation-rules.md"
SAMPLE_TICKETS_PATH = CONTEXT_DIR / "sample-tickets.json"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Channel(str, Enum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    WEB_FORM = "web_form"


class Urgency(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"

    @property
    def sla(self) -> str:
        return {
            "critical": "2 hours",
            "high": "2 hours",
            "normal": "4 business hours",
            "low": "1 business day",
        }[self.value]


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class InboundMessage:
    """Channel-agnostic canonical message produced by the normalize step."""
    customer_id: str        # email address or phone number
    customer_name: str
    channel: Channel
    body: str               # cleaned message text
    subject: str            # subject line; empty string for WhatsApp
    raw_payload: dict       # original payload for audit/replay
    ticket_id: str = field(default_factory=lambda: f"NF-{uuid.uuid4().hex[:8].upper()}")
    received_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class KBSection:
    title: str
    content: str
    relevance_score: float


@dataclass
class EscalationDecision:
    reason: str
    urgency: Urgency
    route_to: str   # destination email / team


@dataclass
class AgentResponse:
    ticket_id: str
    channel: Channel
    customer_id: str
    raw_answer: str             # answer text before channel formatting
    formatted_response: str     # final string ready to send
    escalation: Optional[EscalationDecision]
    sentiment_score: float
    kb_sections_used: list[str]
    processing_steps: list[str]


# ---------------------------------------------------------------------------
# Step 1 + 2: Ingest & Normalize
# ---------------------------------------------------------------------------

def normalize_message(raw_payload: dict, channel: Channel | str) -> InboundMessage:
    """
    Convert any raw channel payload into a canonical InboundMessage.

    Email keys:    customer_email, customer_name, subject, content
    WhatsApp keys: customer_phone, customer_name, content
    Web Form keys: customer_email, customer_name, subject, message
    """
    ch = Channel(channel) if isinstance(channel, str) else channel

    customer_id = (
        raw_payload.get("customer_email")
        or raw_payload.get("customer_phone")
        or "unknown"
    )
    customer_name = (raw_payload.get("customer_name") or "").strip()

    # Different channels use different body field names
    body_raw = (
        raw_payload.get("content")   # email + whatsapp
        or raw_payload.get("message")  # web_form
        or ""
    )
    # Collapse whitespace; strip leading/trailing spaces
    body = re.sub(r"\s+", " ", body_raw).strip()

    subject = (raw_payload.get("subject") or "").strip()

    return InboundMessage(
        customer_id=customer_id,
        customer_name=customer_name,
        channel=ch,
        body=body,
        subject=subject,
        raw_payload=raw_payload,
    )


# ---------------------------------------------------------------------------
# Context loader (company profile + brand voice + escalation rules)
# ---------------------------------------------------------------------------

def _read_file(path: Path, label: str) -> str:
    if not path.exists():
        print(f"  [warn] {label} not found at {path}")
        return ""
    return path.read_text(encoding="utf-8")


def _load_system_context() -> str:
    """Build the OpenAI system prompt from brand-voice + company-profile."""
    company = _read_file(COMPANY_PROFILE_PATH, "company-profile.md")
    brand = _read_file(BRAND_VOICE_PATH, "brand-voice.md")
    escalation = _read_file(ESCALATION_RULES_PATH, "escalation-rules.md")
    return (
        "You are the NimbusFlow Customer Success AI — a knowledgeable, warm, and "
        "efficient support agent. Use the context below to answer customer questions "
        "accurately and in-brand. Do NOT include a greeting or sign-off in your reply; "
        "those are added separately. Be concise and direct.\n\n"
        f"## Company Context\n{company}\n\n"
        f"## Brand Voice\n{brand}\n\n"
        f"## Escalation Rules (reference only — escalation is handled by code)\n{escalation}"
    )


# ---------------------------------------------------------------------------
# Step 3: Search product-docs.md
# ---------------------------------------------------------------------------

_KB_CACHE: list[KBSection] | None = None


def _load_kb() -> list[KBSection]:
    content = _read_file(KB_PATH, "product-docs.md")
    if not content:
        return []
    raw_sections = re.split(r"\n## ", content)
    sections: list[KBSection] = []
    for raw in raw_sections:
        if not raw.strip():
            continue
        lines = raw.strip().splitlines()
        title = lines[0].lstrip("# ").strip()
        body = "\n".join(lines[1:]).strip()
        sections.append(KBSection(title=title, content=body, relevance_score=0.0))
    return sections


def _get_kb() -> list[KBSection]:
    global _KB_CACHE
    if _KB_CACHE is None:
        _KB_CACHE = _load_kb()
        print(f"  [kb] loaded {len(_KB_CACHE)} sections from product-docs.md")
    return _KB_CACHE


def search_docs(query: str, max_results: int = 5) -> list[KBSection]:
    """
    Keyword-based relevance search over product-docs.md sections.
    Title matches weighted 3x over body matches.
    Returns up to max_results sections sorted by score descending.
    """
    tokens = [w.lower() for w in query.split() if len(w) > 2]
    scored: list[KBSection] = []

    for sec in _get_kb():
        score = 0.0
        title_l = sec.title.lower()
        content_l = sec.content.lower()
        for token in tokens:
            if token in title_l:
                score += 3.0
            if token in content_l:
                score += 1.0
        if score > 0:
            scored.append(KBSection(title=sec.title, content=sec.content, relevance_score=score))

    scored.sort(key=lambda s: s.relevance_score, reverse=True)
    return scored[:max_results]


# ---------------------------------------------------------------------------
# Step 6: Escalation detection (runs before generation to short-circuit)
# ---------------------------------------------------------------------------

# Each entry: (trigger_keywords, reason, urgency, route_to)
_HARD_TRIGGERS: list[tuple[list[str], str, Urgency, str]] = [
    (
        ["lawyer", "attorney", "sue", "lawsuit", "court", "litigation", "legal action"],
        "legal_threat", Urgency.CRITICAL, "legal@nimbusflow.io",
    ),
    (
        ["hacked", "unauthorized access", "data breach", "security incident", "compromised"],
        "security_incident", Urgency.CRITICAL, "security@nimbusflow.io",
    ),
    (
        ["chargeback", "dispute the charge", "dispute with my bank", "credit card dispute"],
        "chargeback_threat", Urgency.CRITICAL, "billing@nimbusflow.io",
    ),
    (
        ["tasks disappeared", "tasks vanished", "data gone", "lost my data", "data loss",
         "disappeared", "vanish"],
        "data_loss_reported", Urgency.CRITICAL, "oncall@nimbusflow.io",
    ),
    (
        ["refund", "money back", "cancel and refund"],
        "refund_request", Urgency.HIGH, "billing@nimbusflow.io",
    ),
    (
        ["human", "real person", "speak to someone", "live agent", "representative",
         "talk to a person", "talk to someone"],
        "explicit_human_request", Urgency.HIGH, "support@nimbusflow.io",
    ),
    (
        ["hipaa", "baa ", "business associate agreement", "compliance audit"],
        "compliance_legal_request", Urgency.HIGH, "legal@nimbusflow.io",
    ),
    (
        ["delete workspace", "cancel subscription", "delete account"],
        "account_level_action", Urgency.NORMAL, "support@nimbusflow.io",
    ),
    (
        ["transfer ownership", "transfer workspace"],
        "ownership_transfer", Urgency.NORMAL, "support@nimbusflow.io",
    ),
    (
        ["enterprise pricing", "custom pricing", "volume discount", "nonprofit discount",
         "can you offer", "better deal"],
        "pricing_negotiation", Urgency.LOW, "sales@nimbusflow.io",
    ),
    (
        ["soc 2 report", "pen test", "penetration test", "security audit report"],
        "security_audit_request", Urgency.NORMAL, "security@nimbusflow.io",
    ),
]


def check_escalation(msg: InboundMessage, sentiment_score: float) -> Optional[EscalationDecision]:
    """
    Apply escalation-rules.md hard triggers against the combined subject + body.
    Returns EscalationDecision if escalation required, None otherwise.
    """
    combined = f"{msg.subject} {msg.body}".lower()

    for keywords, reason, urgency, route_to in _HARD_TRIGGERS:
        if any(kw in combined for kw in keywords):
            return EscalationDecision(reason=reason, urgency=urgency, route_to=route_to)

    # Sentiment-based soft trigger (very negative)
    if sentiment_score < 0.2:
        return EscalationDecision(
            reason="extreme_negative_sentiment",
            urgency=Urgency.HIGH,
            route_to="support@nimbusflow.io",
        )

    return None


# ---------------------------------------------------------------------------
# Sentiment scoring (keyword-based, incubation phase)
# ---------------------------------------------------------------------------

def score_sentiment(text: str) -> float:
    """
    Returns a score from 0.0 (very negative) to 1.0 (very positive).
    Baseline is 0.5. Production would use LLM-based scoring.
    """
    tl = text.lower()
    score = 0.5

    very_neg_phrases = [
        "absolutely terrible", "completely unacceptable", "i will sue",
        "data breach", "complete garbage", "!!!",
    ]
    neg_words = [
        "frustrated", "angry", "terrible", "broken", "worst", "hate",
        "furious", "ridiculous", "unacceptable", "cancel", "disgusting",
        "pathetic", "useless", "horrible", "awful",
    ]
    pos_words = [
        "thank", "great", "love", "awesome", "helpful", "excellent",
        "appreciate", "wonderful", "perfect", "fantastic", "quick question",
    ]

    for phrase in very_neg_phrases:
        if phrase in tl:
            score -= 0.3

    for w in neg_words:
        if w in tl:
            score -= 0.08

    for w in pos_words:
        if w in tl:
            score += 0.08

    # All-caps ratio penalty
    caps_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)
    if caps_ratio > 0.3:
        score -= 0.15

    return max(0.0, min(1.0, score))


# ---------------------------------------------------------------------------
# Step 4: Generate response
# ---------------------------------------------------------------------------

def _build_user_prompt(msg: InboundMessage, kb_sections: list[KBSection]) -> str:
    kb_context = "\n\n".join(
        f"### {s.title}\n{s.content}" for s in kb_sections
    ) or "No relevant documentation sections found."

    return (
        f"Channel: {msg.channel.value}\n"
        f"Customer name: {msg.customer_name or 'Unknown'}\n"
        f"Subject: {msg.subject or '(none)'}\n"
        f"Message:\n{msg.body}\n\n"
        "---\n"
        f"Relevant product documentation:\n{kb_context}\n\n"
        "Write a helpful, accurate response to this customer message. "
        "Follow the brand voice for this channel. "
        "Do NOT include a greeting or sign-off — those are added by the formatter. "
        "If the documentation does not cover the issue, say so clearly and offer to "
        "connect the customer with the support team."
    )


def generate_response(msg: InboundMessage, kb_sections: list[KBSection]) -> str:
    """
    Generate a response using the OpenAI API when available.
    Falls back to a template-based KB response when OPENAI_API_KEY is not set.
    """
    api_key = os.getenv("OPENAI_API_KEY", "")
    if api_key and not api_key.startswith("sk-..."):
        try:
            from openai import OpenAI  # type: ignore
            client = OpenAI(api_key=api_key)
            system_prompt = _load_system_context()
            user_prompt = _build_user_prompt(msg, kb_sections)
            completion = client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o"),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=600,
            )
            return completion.choices[0].message.content.strip()
        except Exception as exc:
            print(f"  [warn] OpenAI call failed ({exc}), using KB fallback")

    return _kb_fallback(msg, kb_sections)


def _kb_fallback(msg: InboundMessage, kb_sections: list[KBSection]) -> str:
    """
    Template-based response from the top KB section.
    Used when OpenAI is unavailable.
    """
    if not kb_sections:
        return (
            "I want to make sure you get the right help on this. "
            "Let me connect you with our support team who can look into this further."
        )

    top = kb_sections[0]
    paragraphs = [p.strip() for p in top.content.split("\n\n") if p.strip()]
    snippet = paragraphs[0] if paragraphs else top.content[:500]

    # Empathy opener for frustrated tone
    sentiment = score_sentiment(msg.body)
    if sentiment < 0.35:
        opener = "That sounds frustrating — let's sort this out. "
    elif sentiment < 0.45:
        opener = "Thanks for reaching out. "
    else:
        opener = ""

    return f"{opener}{snippet}"


# ---------------------------------------------------------------------------
# Step 5: Format for channel
# ---------------------------------------------------------------------------

def format_for_channel(
    text: str,
    channel: Channel,
    customer_name: str,
    ticket_id: str,
    escalation: Optional[EscalationDecision] = None,
) -> str:
    """
    Apply channel-specific formatting per brand-voice.md.
    Escalation messages use a different template that hands off cleanly.
    """
    if escalation:
        sla = escalation.urgency.sla
        empathy = (
            "I understand this has been frustrating. "
            if escalation.urgency in (Urgency.CRITICAL, Urgency.HIGH)
            else ""
        )
        if channel == Channel.EMAIL:
            name = customer_name or "there"
            return (
                f"Hi {name},\n\n"
                f"{empathy}I want to make sure you get the best help on this. "
                f"I'm connecting you with our team now — they'll follow up within {sla}.\n\n"
                f"Your ticket reference is {ticket_id}.\n\n"
                f"— NimbusFlow Support"
            )
        elif channel == Channel.WHATSAPP:
            return (
                f"Connecting you to our team now. "
                f"Ref: {ticket_id}. You'll hear back within {sla}."
            )
        else:  # web_form
            return (
                f"I've flagged this for our team. "
                f"Ticket {ticket_id} — they'll reach out within {sla}."
            )

    if channel == Channel.EMAIL:
        name = customer_name or "there"
        if len(text) > 2000:
            text = text[:1997] + "..."
        return (
            f"Hi {name},\n\n"
            f"{text}\n\n"
            f"Let me know if there's anything else I can help with.\n"
            f"— NimbusFlow Support\n\n"
            f"Ticket Reference: {ticket_id}"
        )

    elif channel == Channel.WHATSAPP:
        # Plain text, under 300 chars
        text = re.sub(r"[*_`#]", "", text)  # strip markdown symbols
        if len(text) > 280:
            text = text[:277] + "..."
        return f"{text}\n\nRef: {ticket_id}"

    else:  # web_form — medium length, semi-formal
        if len(text) > 1000:
            text = text[:997] + "..."
        return (
            f"{text}\n\n"
            f"Hope that helps! Reach out if you need anything else.\n"
            f"Ticket: {ticket_id}"
        )


# ---------------------------------------------------------------------------
# Core loop orchestrator
# ---------------------------------------------------------------------------

def run_core_loop(raw_payload: dict, channel: Channel | str) -> AgentResponse:
    """
    Execute the six-step agent pipeline and return an AgentResponse.

    Steps:
        1+2. Normalize raw payload into InboundMessage
        3.   Score sentiment
        6.   Check escalation triggers (short-circuits if triggered)
        3.   Search product-docs.md for relevant KB sections
        4.   Generate response (OpenAI or KB fallback)
        5.   Format response for channel
    """
    steps: list[str] = []

    # Steps 1 + 2: Ingest & Normalize
    msg = normalize_message(raw_payload, channel)
    steps.append(f"normalize | channel={msg.channel.value} | ticket={msg.ticket_id}")
    print(f"\n[{msg.ticket_id}] {msg.channel.value} from {msg.customer_id}")

    # Handle empty body immediately
    if not msg.body:
        steps.append("empty_body")
        clarification = (
            "It looks like your message came through empty — "
            "could you tell me what you need help with?"
        )
        return AgentResponse(
            ticket_id=msg.ticket_id,
            channel=msg.channel,
            customer_id=msg.customer_id,
            raw_answer=clarification,
            formatted_response=format_for_channel(
                clarification, msg.channel, msg.customer_name, msg.ticket_id
            ),
            escalation=None,
            sentiment_score=0.5,
            kb_sections_used=[],
            processing_steps=steps,
        )

    # Sentiment scoring
    sentiment = score_sentiment(f"{msg.subject} {msg.body}")
    steps.append(f"sentiment={sentiment:.2f}")
    print(f"  sentiment: {sentiment:.2f}")

    # Step 6: Escalation check (before KB search to avoid wasted work)
    escalation = check_escalation(msg, sentiment)
    if escalation:
        steps.append(f"escalate | reason={escalation.reason} | urgency={escalation.urgency.value}")
        print(f"  escalate: {escalation.reason} -> {escalation.route_to}")
        return AgentResponse(
            ticket_id=msg.ticket_id,
            channel=msg.channel,
            customer_id=msg.customer_id,
            raw_answer="[escalated]",
            formatted_response=format_for_channel(
                "", msg.channel, msg.customer_name, msg.ticket_id, escalation=escalation
            ),
            escalation=escalation,
            sentiment_score=sentiment,
            kb_sections_used=[],
            processing_steps=steps,
        )

    # Step 3: Search product-docs.md
    search_query = f"{msg.subject} {msg.body}".strip()
    kb_hits = search_docs(search_query)

    # Retry with shorter query if nothing found
    if not kb_hits:
        fallback_query = " ".join(msg.body.split()[:5])
        kb_hits = search_docs(fallback_query)

    steps.append(f"search | hits={len(kb_hits)}")
    print(f"  search: {len(kb_hits)} KB sections matched")

    # Knowledge gap -> escalate
    if not kb_hits:
        gap = EscalationDecision(
            reason="knowledge_gap",
            urgency=Urgency.LOW,
            route_to="support@nimbusflow.io",
        )
        steps.append("escalate | reason=knowledge_gap")
        print("  knowledge gap — escalating")
        return AgentResponse(
            ticket_id=msg.ticket_id,
            channel=msg.channel,
            customer_id=msg.customer_id,
            raw_answer="[knowledge gap]",
            formatted_response=format_for_channel(
                "", msg.channel, msg.customer_name, msg.ticket_id, escalation=gap
            ),
            escalation=gap,
            sentiment_score=sentiment,
            kb_sections_used=[],
            processing_steps=steps,
        )

    # Step 4: Generate response
    raw_answer = generate_response(msg, kb_hits)
    steps.append(f"generate | chars={len(raw_answer)}")
    print(f"  generated: {len(raw_answer)} chars")

    # Step 5: Format for channel
    formatted = format_for_channel(
        raw_answer, msg.channel, msg.customer_name, msg.ticket_id
    )
    steps.append(f"format | channel={msg.channel.value} | chars={len(formatted)}")
    print(f"  formatted: {len(formatted)} chars")

    return AgentResponse(
        ticket_id=msg.ticket_id,
        channel=msg.channel,
        customer_id=msg.customer_id,
        raw_answer=raw_answer,
        formatted_response=formatted,
        escalation=None,
        sentiment_score=sentiment,
        kb_sections_used=[s.title for s in kb_hits],
        processing_steps=steps,
    )


# ---------------------------------------------------------------------------
# CLI / sample-tickets runner
# ---------------------------------------------------------------------------

def _run_ticket(ticket: dict) -> None:
    channel = Channel(ticket["channel"])
    result = run_core_loop(ticket, channel)

    expected = ticket.get("expected_action", "")
    actual = "escalate" if result.escalation else "resolve"
    match = "PASS" if expected.startswith(actual) or expected == "resolve_or_escalate" else "FAIL"

    print(f"  expected={expected} | actual={actual} | [{match}]")
    print(f"  escalation={result.escalation.reason if result.escalation else 'none'}")
    print()
    print(result.formatted_response)
    print("-" * 70)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="NimbusFlow core loop runner")
    parser.add_argument("--ticket", help="Run a single ticket by ID, e.g. T-001")
    parser.add_argument("--all-tickets", action="store_true", help="Run all sample tickets")
    parser.add_argument("--channel", choices=["email", "whatsapp", "web_form"], default="email")
    parser.add_argument("--message", default="", help="Ad-hoc message to process")
    parser.add_argument("--name", default="", help="Customer name for ad-hoc message")
    args = parser.parse_args()

    if not SAMPLE_TICKETS_PATH.exists() and (args.ticket or args.all_tickets):
        print(f"sample-tickets.json not found at {SAMPLE_TICKETS_PATH}")
        return

    if args.ticket or args.all_tickets:
        data = json.loads(SAMPLE_TICKETS_PATH.read_text(encoding="utf-8"))
        tickets = data["tickets"]

        if args.ticket:
            matches = [t for t in tickets if t["id"] == args.ticket]
            if not matches:
                print(f"Ticket {args.ticket} not found")
                return
            tickets = matches

        passed = failed = 0
        for ticket in tickets:
            print(f"\n{'='*70}")
            print(f"Ticket {ticket['id']} | {ticket['channel']} | {ticket.get('subject', '')}")
            print(f"{'='*70}")
            channel = Channel(ticket["channel"])
            result = run_core_loop(ticket, channel)

            expected = ticket.get("expected_action", "")
            actual = "escalate" if result.escalation else "resolve"
            ok = expected.startswith(actual) or expected == "resolve_or_escalate"
            label = "PASS" if ok else "FAIL"
            if ok:
                passed += 1
            else:
                failed += 1

            print(f"  expected={expected} | actual={actual} | [{label}]")
            if result.escalation:
                print(f"  escalation reason : {result.escalation.reason}")
                print(f"  route to          : {result.escalation.route_to}")
            print(f"  KB sections used  : {result.kb_sections_used or 'none'}")
            print()
            print(result.formatted_response)
            print()

        if args.all_tickets:
            total = passed + failed
            print(f"\n{'='*70}")
            print(f"Results: {passed}/{total} PASS  |  {failed}/{total} FAIL")

    else:
        # Ad-hoc message
        message = args.message or input("Customer message: ").strip()
        payload = {
            "customer_email": "test@example.com",
            "customer_name": args.name,
            "subject": "",
            "content": message,
        }
        result = run_core_loop(payload, Channel(args.channel))
        print(f"\n{'='*70}")
        print(result.formatted_response)
        print(f"{'='*70}")
        if result.escalation:
            print(f"ESCALATED: {result.escalation.reason} ({result.escalation.urgency.value})")
        print(json.dumps(
            {
                "ticket_id": result.ticket_id,
                "escalated": result.escalation is not None,
                "escalation_reason": result.escalation.reason if result.escalation else None,
                "sentiment_score": round(result.sentiment_score, 2),
                "kb_sections_used": result.kb_sections_used,
                "steps": result.processing_steps,
            },
            indent=2,
        ))


if __name__ == "__main__":
    main()
