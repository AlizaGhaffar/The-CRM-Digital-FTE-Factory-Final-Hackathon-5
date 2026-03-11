"""
Incubation Phase Prototype — NimbusFlow Customer Success FTE
Exercises 1.1 – 1.3: Core Loop + Memory + State

Run this to test the agent prototype before moving to production.
Usage:
    python src/agent/prototype.py
    python src/agent/prototype.py --channel whatsapp --message "how do i reset password"
"""

import asyncio
import argparse
import json
import os
import re
from datetime import datetime
from enum import Enum
from typing import Optional


class Channel(str, Enum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    WEB_FORM = "web_form"


class SentimentLevel(str, Enum):
    VERY_POSITIVE = "very_positive"   # 0.8 – 1.0
    POSITIVE = "positive"             # 0.6 – 0.8
    NEUTRAL = "neutral"               # 0.4 – 0.6
    NEGATIVE = "negative"             # 0.2 – 0.4
    VERY_NEGATIVE = "very_negative"   # 0.0 – 0.2


# ── In-memory state ────────────────────────────────────────────────────────
_conversations: dict[str, dict] = {}
_tickets: dict[str, dict] = {}


# ── Knowledge Base ──────────────────────────────────────────────────────────
def load_knowledge_base() -> list[dict]:
    """Load product docs from context folder."""
    docs_path = os.path.join(os.path.dirname(__file__), "../../context/product-docs.md")
    if not os.path.exists(docs_path):
        print("⚠️  product-docs.md not found")
        return []

    with open(docs_path, "r") as f:
        content = f.read()

    sections = re.split(r"\n## ", content)
    kb = []
    for section in sections:
        if section.strip():
            lines = section.strip().split("\n")
            title = lines[0].strip("# ")
            body = "\n".join(lines[1:]).strip()
            kb.append({"title": title, "content": body})

    print(f"✅ Loaded {len(kb)} knowledge base sections")
    return kb


KB = load_knowledge_base()


# ── Sentiment Analysis (Simple keyword-based for prototype) ─────────────────
def analyze_sentiment(message: str) -> tuple[float, SentimentLevel]:
    """
    Prototype sentiment analysis using keyword scoring.
    Production will use LLM-based scoring.
    """
    message_lower = message.lower()

    negative_words = [
        "frustrated", "angry", "terrible", "awful", "horrible", "disgusting",
        "unacceptable", "ridiculous", "useless", "broken", "worst", "hate",
        "furious", "pathetic", "scam", "lawsuit", "sue", "lawyer", "legal",
        "chargeback", "dispute", "cancel", "refund"
    ]
    very_negative_words = [
        "!!!", "???", "absolutely terrible", "complete garbage", "i will sue",
        "lawyer", "legal action", "data breach", "completely unacceptable"
    ]
    positive_words = [
        "thank", "great", "love", "awesome", "helpful", "excellent",
        "appreciate", "wonderful", "perfect", "fantastic"
    ]

    score = 0.5  # Neutral baseline

    for word in very_negative_words:
        if word in message_lower:
            score -= 0.3

    for word in negative_words:
        if word in message_lower:
            score -= 0.1

    for word in positive_words:
        if word in message_lower:
            score += 0.1

    # All caps check
    caps_ratio = sum(1 for c in message if c.isupper()) / max(len(message), 1)
    if caps_ratio > 0.3:
        score -= 0.15

    score = max(0.0, min(1.0, score))

    if score >= 0.8:
        level = SentimentLevel.VERY_POSITIVE
    elif score >= 0.6:
        level = SentimentLevel.POSITIVE
    elif score >= 0.4:
        level = SentimentLevel.NEUTRAL
    elif score >= 0.2:
        level = SentimentLevel.NEGATIVE
    else:
        level = SentimentLevel.VERY_NEGATIVE

    return score, level


# ── Knowledge Search ────────────────────────────────────────────────────────
def search_knowledge_base(query: str, max_results: int = 5) -> list[dict]:
    """Simple keyword-based search for prototype."""
    query_lower = query.lower()
    results = []

    for doc in KB:
        score = 0
        for word in query_lower.split():
            if len(word) > 3:  # Skip short words
                if word in doc["title"].lower():
                    score += 3
                if word in doc["content"].lower():
                    score += 1

        if score > 0:
            results.append((score, doc))

    results.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in results[:max_results]]


# ── Escalation Detection ─────────────────────────────────────────────────────
def check_escalation_triggers(message: str, sentiment_score: float) -> Optional[tuple[str, str]]:
    """
    Returns (reason, urgency) if escalation is needed, None otherwise.
    """
    message_lower = message.lower()

    # Hard triggers — immediate
    legal_words = ["lawyer", "attorney", "sue", "lawsuit", "court", "litigation", "legal action"]
    if any(word in message_lower for word in legal_words):
        return ("legal_threat", "critical")

    security_words = ["hacked", "compromised", "unauthorized access", "data breach", "security incident"]
    if any(word in message_lower for word in security_words):
        return ("security_incident", "critical")

    chargeback_words = ["chargeback", "dispute the charge", "credit card dispute", "dispute with my bank"]
    if any(word in message_lower for word in chargeback_words):
        return ("chargeback_threat", "critical")

    data_loss_words = ["disappeared", "lost my data", "data gone", "tasks vanished", "data loss"]
    if any(word in message_lower for word in data_loss_words):
        return ("data_loss_reported", "critical")

    refund_words = ["refund", "money back", "cancel and refund"]
    if any(word in message_lower for word in refund_words):
        return ("refund_request", "high")

    human_words = ["human", "real person", "speak to someone", "live agent", "representative"]
    if any(word in message_lower for word in human_words):
        return ("explicit_human_request", "high")

    # Sentiment trigger
    if sentiment_score < 0.2:
        return ("extreme_negative_sentiment", "high")

    return None


# ── Channel Formatting ───────────────────────────────────────────────────────
def format_response(response: str, channel: Channel, ticket_id: str, customer_name: str = "") -> str:
    """Format response appropriately for each channel."""
    name = customer_name or "there"

    if channel == Channel.EMAIL:
        return (
            f"Hi {name},\n\n"
            f"{response}\n\n"
            f"Let me know if there's anything else I can help with.\n"
            f"— NimbusFlow Support\n"
            f"Ticket Reference: {ticket_id}"
        )

    elif channel == Channel.WHATSAPP:
        # Keep concise
        if len(response) > 250:
            response = response[:247] + "..."
        return f"{response}\n\nRef: {ticket_id}"

    else:  # web_form
        return (
            f"{response}\n\n"
            f"Hope that helps! Reach out if you need anything else.\n"
            f"Ticket: {ticket_id}"
        )


# ── Core Agent Loop ──────────────────────────────────────────────────────────
def run_agent(
    message: str,
    channel: Channel,
    customer_id: str,
    customer_name: str = "",
    ticket_subject: str = "Support Request"
) -> dict:
    """
    Main agent interaction loop.
    Returns dict with: response, ticket_id, escalated, escalation_reason, sentiment_score
    """
    import uuid

    result = {
        "ticket_id": None,
        "response": None,
        "escalated": False,
        "escalation_reason": None,
        "sentiment_score": None,
        "channel": channel.value
    }

    # ── Step 1: Create ticket ───────────────────────────────────────────────
    ticket_id = f"NF-{str(uuid.uuid4())[:8].upper()}"
    _tickets[ticket_id] = {
        "ticket_id": ticket_id,
        "customer_id": customer_id,
        "channel": channel.value,
        "issue": ticket_subject,
        "status": "open",
        "created_at": datetime.utcnow().isoformat()
    }
    result["ticket_id"] = ticket_id
    print(f"\n📋 Ticket created: {ticket_id}")

    # ── Step 2: Check customer history ──────────────────────────────────────
    past_tickets = [t for t in _tickets.values() if t["customer_id"] == customer_id and t["ticket_id"] != ticket_id]
    is_repeat = len(past_tickets) >= 2
    if is_repeat:
        print(f"⚠️  Repeat contact detected: {len(past_tickets)} previous tickets")

    # ── Step 3: Analyze sentiment ───────────────────────────────────────────
    if not message or len(message.strip()) < 3:
        result["response"] = format_response(
            "It looks like your message was empty — could you describe what you need help with?",
            channel, ticket_id, customer_name
        )
        return result

    sentiment_score, sentiment_level = analyze_sentiment(message)
    result["sentiment_score"] = sentiment_score
    print(f"💭 Sentiment: {sentiment_score:.2f} ({sentiment_level.value})")

    # ── Step 4: Check escalation triggers ──────────────────────────────────
    # Check repeat contact
    if is_repeat:
        escalation = ("repeat_contact", "high")
    else:
        escalation = check_escalation_triggers(message, sentiment_score)

    if escalation:
        reason, urgency = escalation
        _tickets[ticket_id]["status"] = "escalated"
        result["escalated"] = True
        result["escalation_reason"] = reason

        sla = {"critical": "2 hours", "high": "2 hours", "normal": "4 business hours", "low": "1 business day"}.get(urgency, "4 business hours")

        empathy = ""
        if sentiment_score < 0.4:
            empathy = "I understand this has been frustrating, and I'm sorry for the trouble. "

        escalation_msg = (
            f"{empathy}I want to make sure you get the best help possible. "
            f"I'm connecting you with our team right away.\n\n"
            f"A team member will follow up within {sla}. "
            f"Your reference number is {ticket_id}."
        )
        result["response"] = format_response(escalation_msg, channel, ticket_id, customer_name)
        print(f"🚨 Escalated: {reason} ({urgency})")
        return result

    # ── Step 5: Add empathy opener if needed ────────────────────────────────
    empathy_opener = ""
    if sentiment_score < 0.4:
        if sentiment_score < 0.3:
            empathy_opener = "That sounds really frustrating — let's sort this out. "
        else:
            empathy_opener = "Thanks for reaching out. "

    # ── Step 6: Search knowledge base ───────────────────────────────────────
    kb_results = search_knowledge_base(message)

    if not kb_results:
        # Second search with broader terms
        words = message.split()
        broad_query = " ".join(words[:3]) if len(words) > 3 else message
        kb_results = search_knowledge_base(broad_query)

    if not kb_results:
        # Escalate after 2 failed searches
        _tickets[ticket_id]["status"] = "escalated"
        result["escalated"] = True
        result["escalation_reason"] = "knowledge_gap"
        escalation_msg = (
            "I want to make sure you get accurate help on this. "
            "I'm connecting you with our technical team who can assist further. "
            f"Reference: {ticket_id}"
        )
        result["response"] = format_response(escalation_msg, channel, ticket_id, customer_name)
        print("📚 Knowledge gap — escalating")
        return result

    # ── Step 7: Generate response ────────────────────────────────────────────
    # Use first KB result as basis for response
    top_result = kb_results[0]
    content_snippet = top_result["content"]

    # Channel-specific length limits
    if channel == Channel.WHATSAPP:
        content_snippet = content_snippet[:200]
    elif channel == Channel.WEB_FORM:
        content_snippet = content_snippet[:800]
    else:
        content_snippet = content_snippet[:1500]

    answer = f"{empathy_opener}{content_snippet}"

    result["response"] = format_response(answer, channel, ticket_id, customer_name)
    _tickets[ticket_id]["status"] = "responded"
    print(f"✅ Response generated ({len(result['response'])} chars)")

    return result


# ── CLI Interface ──────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="NimbusFlow Customer Success FTE Prototype")
    parser.add_argument("--channel", choices=["email", "whatsapp", "web_form"], default="email")
    parser.add_argument("--message", type=str, default="")
    parser.add_argument("--customer-id", type=str, default="test@example.com")
    parser.add_argument("--customer-name", type=str, default="")
    parser.add_argument("--interactive", action="store_true", help="Run interactive mode")
    args = parser.parse_args()

    channel = Channel(args.channel)

    if args.interactive or not args.message:
        print(f"\n🤖 NimbusFlow Customer Success FTE — Prototype")
        print(f"   Channel: {channel.value}")
        print(f"   Customer: {args.customer_id}")
        print(f"   Type 'quit' to exit\n")

        while True:
            message = input(f"[{channel.value}] Customer: ").strip()
            if message.lower() == "quit":
                break

            result = run_agent(
                message=message,
                channel=channel,
                customer_id=args.customer_id,
                customer_name=args.customer_name
            )

            print(f"\n[Agent Response]")
            print("─" * 60)
            print(result["response"])
            print("─" * 60)
            if result["escalated"]:
                print(f"⚠️  ESCALATED: {result['escalation_reason']}")
            print()
    else:
        result = run_agent(
            message=args.message,
            channel=channel,
            customer_id=args.customer_id,
            customer_name=args.customer_name
        )
        print(f"\n{'='*60}")
        print(result["response"])
        print(f"{'='*60}")
        print(json.dumps({k: v for k, v in result.items() if k != "response"}, indent=2))


if __name__ == "__main__":
    main()
