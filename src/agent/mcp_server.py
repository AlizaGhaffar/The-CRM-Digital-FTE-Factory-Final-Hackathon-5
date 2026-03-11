"""
Incubation Phase MCP Server — NimbusFlow Customer Success FTE
Exercise 1.4: Build the MCP Server

This is the prototype MCP server. Tools here will be migrated to
@function_tool decorated functions in production/agent/tools.py
"""

from mcp.server import Server
from mcp.types import Tool, TextContent
from enum import Enum
from typing import Optional
import json
import re


class Channel(str, Enum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    WEB_FORM = "web_form"


server = Server("nimbusflow-customer-success-fte")

# ── In-memory state for prototype ──────────────────────────────────────────
_tickets: dict = {}
_conversations: dict = {}
_customers: dict = {}
_knowledge_base: list = []


def _load_knowledge_base():
    """Load product docs into in-memory KB for prototype."""
    import os
    docs_path = os.path.join(os.path.dirname(__file__), "../../context/product-docs.md")
    if os.path.exists(docs_path):
        with open(docs_path, "r") as f:
            content = f.read()
        # Split by section headers
        sections = re.split(r"\n## ", content)
        for section in sections:
            if section.strip():
                lines = section.strip().split("\n")
                title = lines[0].strip("# ")
                body = "\n".join(lines[1:]).strip()
                _knowledge_base.append({"title": title, "content": body})


_load_knowledge_base()


# ── Tool: search_knowledge_base ────────────────────────────────────────────
@server.tool("search_knowledge_base")
async def search_knowledge_base(query: str, max_results: int = 5) -> str:
    """Search NimbusFlow product documentation for relevant information.

    Use this when a customer asks questions about product features,
    how to use something, or needs technical guidance.

    Args:
        query: The customer's question or topic to search for
        max_results: Maximum number of results to return (default: 5)

    Returns:
        Relevant documentation snippets with section titles
    """
    query_lower = query.lower()
    results = []

    for doc in _knowledge_base:
        title_lower = doc["title"].lower()
        content_lower = doc["content"].lower()

        # Simple keyword matching for prototype
        score = 0
        query_words = query_lower.split()
        for word in query_words:
            if word in title_lower:
                score += 3  # Title match weighted higher
            if word in content_lower:
                score += 1

        if score > 0:
            results.append((score, doc))

    # Sort by score, take top results
    results.sort(key=lambda x: x[0], reverse=True)
    top_results = results[:max_results]

    if not top_results:
        return "No relevant documentation found for this query. Consider escalating to human support."

    formatted = []
    for score, doc in top_results:
        snippet = doc["content"][:600] + ("..." if len(doc["content"]) > 600 else "")
        formatted.append(f"**{doc['title']}**\n{snippet}")

    return "\n\n---\n\n".join(formatted)


# ── Tool: create_ticket ────────────────────────────────────────────────────
@server.tool("create_ticket")
async def create_ticket(
    customer_id: str,
    issue: str,
    priority: str,
    channel: str,
    category: Optional[str] = None
) -> str:
    """Create a support ticket in the system with channel tracking.

    ALWAYS call this FIRST before any other action.
    Every customer interaction must have a ticket.

    Args:
        customer_id: Unique customer identifier (email or phone)
        issue: Brief description of the customer's issue
        priority: low | medium | high | critical
        channel: email | whatsapp | web_form
        category: general | technical | billing | bug_report | feedback

    Returns:
        ticket_id: Unique ticket reference number
    """
    import uuid
    ticket_id = f"NF-{str(uuid.uuid4())[:8].upper()}"

    _tickets[ticket_id] = {
        "ticket_id": ticket_id,
        "customer_id": customer_id,
        "issue": issue,
        "priority": priority,
        "channel": channel,
        "category": category or "general",
        "status": "open",
        "created_at": __import__("datetime").datetime.utcnow().isoformat()
    }

    return f"Ticket created: {ticket_id}"


# ── Tool: get_customer_history ─────────────────────────────────────────────
@server.tool("get_customer_history")
async def get_customer_history(customer_id: str) -> str:
    """Get customer's interaction history across ALL channels.

    Use this after creating a ticket to understand if this customer
    has contacted us before and what about.

    Args:
        customer_id: Customer's email or phone number

    Returns:
        Summary of past interactions or "No history found"
    """
    customer_tickets = [
        t for t in _tickets.values()
        if t["customer_id"] == customer_id
    ]

    if not customer_tickets:
        return "No previous interactions found for this customer."

    # Sort by most recent, take last 5
    recent = sorted(
        customer_tickets,
        key=lambda x: x["created_at"],
        reverse=True
    )[:5]

    history_lines = [f"Found {len(customer_tickets)} past interaction(s). Recent:"]
    for t in recent:
        history_lines.append(
            f"- [{t['ticket_id']}] {t['channel'].upper()} | {t['category']} | "
            f"{t['priority']} priority | {t['status']} | {t['issue'][:60]}"
        )

    return "\n".join(history_lines)


# ── Tool: escalate_to_human ────────────────────────────────────────────────
@server.tool("escalate_to_human")
async def escalate_to_human(
    ticket_id: str,
    reason: str,
    urgency: str = "normal"
) -> str:
    """Escalate conversation to human support team.

    Use when:
    - Customer asks about pricing or refunds
    - Legal threats or security incidents
    - Customer sentiment is very negative (< 0.3)
    - You cannot find relevant information after 2 searches
    - Customer explicitly requests human help
    - Data loss is reported

    Args:
        ticket_id: The ticket to escalate
        reason: Specific reason (e.g., "refund_request", "legal_threat", "sentiment_negative")
        urgency: low | normal | high | critical

    Returns:
        Escalation confirmation with reference ID
    """
    if ticket_id in _tickets:
        _tickets[ticket_id]["status"] = "escalated"
        _tickets[ticket_id]["escalation_reason"] = reason
        _tickets[ticket_id]["urgency"] = urgency

    sla_map = {
        "critical": "2 hours",
        "high": "2 hours",
        "normal": "4 business hours",
        "low": "1 business day"
    }

    sla = sla_map.get(urgency, "4 business hours")
    return (
        f"Escalated to human support. Reference: {ticket_id}\n"
        f"Reason: {reason}\n"
        f"Urgency: {urgency}\n"
        f"Expected response: within {sla}"
    )


# ── Tool: send_response ────────────────────────────────────────────────────
@server.tool("send_response")
async def send_response(
    ticket_id: str,
    message: str,
    channel: str
) -> str:
    """Send response to customer via their channel.

    ALWAYS call this last. Never respond to the customer directly.
    This tool handles channel-appropriate formatting.

    Args:
        ticket_id: The ticket this response belongs to
        message: The response content (will be formatted for channel)
        channel: email | whatsapp | web_form

    Returns:
        Delivery confirmation
    """
    # Format response per channel
    if channel == Channel.EMAIL:
        ticket = _tickets.get(ticket_id, {})
        formatted = (
            f"Hi,\n\n{message}\n\n"
            f"Let me know if there's anything else I can help with.\n"
            f"— NimbusFlow Support\n"
            f"Ticket: {ticket_id}"
        )
    elif channel == Channel.WHATSAPP:
        # Truncate for WhatsApp
        if len(message) > 280:
            message = message[:277] + "..."
        formatted = f"{message}\n\nRef: {ticket_id}"
    else:  # web_form
        formatted = f"{message}\n\n— NimbusFlow Support | Ticket: {ticket_id}"

    # In prototype, just log it (production will actually send)
    print(f"\n[SEND via {channel.upper()}]\n{formatted}\n")

    if ticket_id in _tickets:
        _tickets[ticket_id]["response"] = formatted
        _tickets[ticket_id]["status"] = "responded"

    return f"Response sent via {channel}. Ticket {ticket_id} updated."


# ── Entry point ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    server.run()
