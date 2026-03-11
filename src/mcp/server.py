"""
Exercise 1.4 — MCP Server
src/mcp/server.py

Exposes the NimbusFlow Customer Success FTE as an MCP server with five tools.
MCP clients (Claude Desktop, custom agents) connect and call these tools.

Tools (per hackathon spec):
    1. search_knowledge_base   — Query product-docs.md for relevant info
    2. create_ticket           — Log a support interaction with channel tracking
    3. get_customer_history    — Cross-channel customer lookup (ALL channels)
    4. escalate_to_human       — Hand off ticket to human agent with urgency routing
    5. send_response           — Format and deliver response for a given channel

MCP version: 1.26.0  (FastMCP high-level API)
    The hackathon template's `@server.tool()` maps 1-for-1 to FastMCP's `@mcp.tool()`.
    FastMCP is the correct high-level API in mcp >=1.0; the low-level Server class
    does not expose a .tool() decorator in this version.

Transport:
    Default  — stdio  (used by Claude Desktop and most MCP hosts)
    --sse    — Server-Sent Events HTTP transport (useful for debugging)

Run:
    python src/mcp/server.py
    python src/mcp/server.py --sse
"""

from __future__ import annotations

import argparse
import logging
import sys
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Logging — structured, goes to stderr so MCP stdio transport stays clean
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stderr,
)
logger = logging.getLogger("nimbusflow.mcp")

# ---------------------------------------------------------------------------
# Imports from sibling modules (core loop + memory)
# ---------------------------------------------------------------------------

# Adjust path so this module is importable both as a script and as a package
import os
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.agent.core import search_docs, format_for_channel, Channel  # noqa: E402
from src.agent.memory import MemoryStore                              # noqa: E402

# ---------------------------------------------------------------------------
# Shared state (in-memory for incubation; production swaps for asyncpg pool)
# ---------------------------------------------------------------------------

_store = MemoryStore()

# ---------------------------------------------------------------------------
# Channel validation helper
# ---------------------------------------------------------------------------

_VALID_CHANNELS = {c.value for c in Channel}
_URGENCY_MAP: dict[str, str] = {
    "legal_threat": "critical",
    "security_incident": "critical",
    "data_breach": "critical",
    "chargeback_threat": "critical",
    "data_loss_reported": "critical",
    "refund_request": "high",
    "explicit_human_request": "high",
    "billing_dispute": "high",
    "compliance_legal_request": "high",
    "repeat_contact": "normal",
    "extreme_negative_sentiment": "normal",
    "sentiment_negative": "normal",
    "knowledge_gap": "low",
    "feature_request": "low",
    "pricing_negotiation": "low",
    "enterprise_inquiry": "low",
}
_ROUTE_MAP: dict[str, str] = {
    "legal_threat": "legal@nimbusflow.io",
    "security_incident": "security@nimbusflow.io",
    "data_breach": "security@nimbusflow.io",
    "chargeback_threat": "billing@nimbusflow.io",
    "data_loss_reported": "oncall@nimbusflow.io",
    "refund_request": "billing@nimbusflow.io",
    "billing_dispute": "billing@nimbusflow.io",
    "compliance_legal_request": "legal@nimbusflow.io",
    "enterprise_inquiry": "csm@nimbusflow.io",
    "pricing_negotiation": "sales@nimbusflow.io",
}
_SLA_MAP: dict[str, str] = {
    "critical": "2 hours",
    "high": "2 hours",
    "normal": "4 business hours",
    "low": "1 business day",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_channel(channel: str) -> str:
    """Normalise and validate a channel string. Raises ValueError if invalid."""
    ch = channel.strip().lower()
    if ch not in _VALID_CHANNELS:
        raise ValueError(
            f"Invalid channel '{channel}'. Must be one of: {', '.join(sorted(_VALID_CHANNELS))}"
        )
    return ch


# ---------------------------------------------------------------------------
# MCP server definition — matches hackathon template exactly
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="customer-success-fte",
    instructions=(
        "NimbusFlow Customer Success FTE — AI employee handling support across "
        "Email, WhatsApp, and Web Form. Use these tools in order: "
        "1) create_ticket  2) get_customer_history  3) search_knowledge_base  "
        "4) send_response (or escalate_to_human if needed)."
    ),
)


# ---------------------------------------------------------------------------
# Tool 1: search_knowledge_base
# ---------------------------------------------------------------------------

@mcp.tool()
async def search_knowledge_base(query: str) -> str:
    """Search NimbusFlow product documentation for relevant information.

    Use this when a customer asks questions about product features, how-to
    guidance, integrations, billing, security, or troubleshooting. Run this
    BEFORE generating a response to ground the answer in accurate docs.

    Args:
        query: The customer's question or topic to search for.
               Include key terms from the customer's message.
               Examples: "reset password", "GitHub webhook not firing",
                         "API rate limits growth plan", "SSO SAML Okta setup"

    Returns:
        Relevant documentation sections with titles and content snippets,
        separated by dividers. Returns an error message string if the search
        fails. Returns "No results found" if no docs match the query.
    """
    logger.info("search_knowledge_base | query=%r", query)

    if not query or not query.strip():
        logger.warning("search_knowledge_base called with empty query")
        return "Error: query must not be empty."

    try:
        results = search_docs(query.strip(), max_results=5)

        if not results:
            # Second attempt with shortened query (first 4 words)
            short_query = " ".join(query.split()[:4])
            results = search_docs(short_query, max_results=5)

        if not results:
            logger.info("search_knowledge_base | no results for query=%r", query)
            return (
                "No relevant documentation found for this query. "
                "Consider escalating to the human support team."
            )

        sections = []
        for r in results:
            # Cap each section to 600 chars to keep context window manageable
            snippet = r.content[:600] + ("..." if len(r.content) > 600 else "")
            sections.append(f"**{r.title}**\n{snippet}")

        logger.info(
            "search_knowledge_base | query=%r | results=%d", query, len(results)
        )
        return "\n\n---\n\n".join(sections)

    except Exception as exc:
        logger.error("search_knowledge_base | error: %s", exc, exc_info=True)
        return f"Error searching knowledge base: {exc}"


# ---------------------------------------------------------------------------
# Tool 2: create_ticket
# ---------------------------------------------------------------------------

@mcp.tool()
async def create_ticket(
    customer_id: str,
    issue: str,
    priority: str,
    channel: str,
) -> str:
    """Create a support ticket in the system with channel tracking.

    ALWAYS call this FIRST before any other action. Every customer interaction
    must have a ticket for audit trail and SLA tracking.

    Args:
        customer_id: Unique customer identifier — use email address as primary
                     identifier (e.g. "alex@company.com"). For WhatsApp-only
                     contacts use their E.164 phone number (e.g. "+14155551234").
        issue:       Brief description of the customer's issue (max ~120 chars).
                     Examples: "Account locked after failed logins",
                               "GitHub webhook not firing after reconnect",
                               "Requesting refund for annual subscription"
        priority:    Ticket priority — one of: low | medium | high | critical
                     Use 'critical' only for data loss, security incidents,
                     enterprise SLA breaches. Use 'high' for billing/legal.
        channel:     Inbound channel — one of: email | whatsapp | web_form

    Returns:
        Ticket ID string in NF-XXXXXXXX format, e.g. "Ticket created: NF-A1B2C3D4".
        Returns an error message string on failure.
    """
    logger.info(
        "create_ticket | customer=%r | priority=%s | channel=%s | issue=%r",
        customer_id, priority, channel, issue[:80],
    )

    # Validate inputs
    if not customer_id or not customer_id.strip():
        return "Error: customer_id must not be empty."
    if not issue or not issue.strip():
        return "Error: issue must not be empty."

    valid_priorities = {"low", "medium", "high", "critical"}
    priority_norm = priority.strip().lower()
    if priority_norm not in valid_priorities:
        return (
            f"Error: invalid priority '{priority}'. "
            f"Must be one of: {', '.join(sorted(valid_priorities))}"
        )

    try:
        channel_norm = _validate_channel(channel)
    except ValueError as exc:
        return f"Error: {exc}"

    try:
        # Resolve or create customer (email as primary key)
        email = customer_id.strip() if "@" in customer_id else None
        phone = customer_id.strip() if "@" not in customer_id else None
        profile = _store.find_or_create_customer(
            email=email, phone=phone, channel=channel_norm
        )

        # Get or create active conversation for this session
        conv = _store.get_or_create_conversation(profile.customer_id, channel_norm)

        # Create ticket
        ticket = _store.create_ticket(
            customer_id=profile.customer_id,
            conversation_id=conv.conversation_id,
            source_channel=channel_norm,
            subject=issue.strip(),
            priority=priority_norm,
        )

        logger.info(
            "create_ticket | ticket=%s | customer_id=%s | conv=%s",
            ticket.ticket_id, profile.customer_id[:8], conv.conversation_id[:8],
        )
        return f"Ticket created: {ticket.ticket_id}"

    except Exception as exc:
        logger.error("create_ticket | error: %s", exc, exc_info=True)
        return f"Error creating ticket: {exc}"


# ---------------------------------------------------------------------------
# Tool 3: get_customer_history
# ---------------------------------------------------------------------------

@mcp.tool()
async def get_customer_history(customer_id: str) -> str:
    """Get a customer's interaction history across ALL channels.

    Call this after create_ticket to understand whether this customer has
    contacted us before, what their issues were, which channels they used,
    and what their sentiment trend has been. Use this context to personalise
    the response and detect repeat contacts (which may trigger escalation).

    Args:
        customer_id: Customer email address or E.164 phone number.
                     Same value used in create_ticket.

    Returns:
        Formatted multi-line string with:
        - Customer profile (name, plan, preferred channel)
        - Conversation context (status, channel switches, sentiment)
        - Last 5 tickets (id, channel, category, status, subject)
        - Repeat contact flag
        Returns "No history found" for new customers.
        Returns an error message string on failure.
    """
    logger.info("get_customer_history | customer_id=%r", customer_id)

    if not customer_id or not customer_id.strip():
        return "Error: customer_id must not be empty."

    try:
        resolved_id = _store.resolve_customer_id(customer_id.strip())

        if not resolved_id:
            logger.info("get_customer_history | no record for %r", customer_id)
            return "No previous interactions found for this customer."

        ctx = _store.build_agent_context(resolved_id)
        if not ctx.get("found"):
            return "No previous interactions found for this customer."

        c = ctx["customer"]
        conv = ctx["conversation"]
        tickets = ctx["recent_tickets"]

        lines: list[str] = [
            f"Customer: {c['name'] or '(unknown name)'} | {c['email'] or c['phone']}",
            f"Plan: {c['plan'] or 'unknown'} | Preferred channel: {c['preferred_channel']}",
            f"Lifetime tickets: {c['lifetime_tickets']} | Open tickets: {c['open_tickets']}",
            f"Last contact: {c['last_contact_at'] or 'never'} via {c['last_channel'] or 'unknown'}",
        ]

        if ctx["is_repeat_contact"]:
            lines.append("⚠ REPEAT CONTACT — customer has contacted us before")

        if conv and conv.get("conversation_id"):
            lines.append("")
            lines.append(f"Active conversation: {conv['conversation_id']}")
            lines.append(
                f"  Channel: {conv['initial_channel']} → {conv['current_channel']}"
            )
            if conv["channel_switches"]:
                switches = ", ".join(
                    f"{s['from']}→{s['to']}" for s in conv["channel_switches"]
                )
                lines.append(f"  Channel switches: {switches}")
            if conv.get("sentiment_score") is not None:
                lines.append(
                    f"  Sentiment: {conv['sentiment_score']:.2f} ({conv.get('sentiment_trend', 'stable')})"
                )
            if conv.get("topics"):
                lines.append(f"  Topics: {', '.join(conv['topics'])}")

        if tickets:
            lines.append("")
            lines.append(f"Recent tickets ({len(tickets)}):")
            for t in tickets:
                esc = f" | escalation: {t['escalation_reason']}" if t.get("escalation_reason") else ""
                lines.append(
                    f"  [{t['ticket_id']}] {t['source_channel'].upper()} | "
                    f"{t['category'] or 'general'} | {t['priority']} | "
                    f"{t['status']}{esc} | {(t['subject'] or '')[:60]}"
                )
        else:
            lines.append("")
            lines.append("No previous tickets found.")

        logger.info(
            "get_customer_history | customer=%s | tickets=%d | repeat=%s",
            resolved_id[:8], len(tickets), ctx["is_repeat_contact"],
        )
        return "\n".join(lines)

    except Exception as exc:
        logger.error("get_customer_history | error: %s", exc, exc_info=True)
        return f"Error retrieving customer history: {exc}"


# ---------------------------------------------------------------------------
# Tool 4: escalate_to_human
# ---------------------------------------------------------------------------

@mcp.tool()
async def escalate_to_human(ticket_id: str, reason: str) -> str:
    """Escalate a conversation to the human support team.

    Use when any of these conditions are true (per escalation-rules.md):
    - Customer mentions: lawyer, legal action, sue, attorney, court, litigation
    - Security: data breach, unauthorized access, compromised account, API key exposure
    - Financial: refund request, chargeback threat, billing dispute
    - Sentiment: customer is very negative (score < 0.3) or uses aggressive language
    - Data loss: tasks disappeared, data gone, lost data
    - Explicit: customer says "human", "real person", "speak to someone"
    - Knowledge gap: question not answerable from product docs after 2 searches
    - Enterprise SLA: downtime > 15 min, P1 incident, SLA breach

    After escalating, do NOT attempt to resolve the issue — hand off completely.

    Args:
        ticket_id: The ticket to escalate (NF-XXXXXXXX format, from create_ticket).
        reason:    Specific escalation reason. Use one of these standardised values:
                   legal_threat | security_incident | data_breach |
                   chargeback_threat | data_loss_reported | refund_request |
                   explicit_human_request | billing_dispute |
                   compliance_legal_request | repeat_contact |
                   extreme_negative_sentiment | knowledge_gap |
                   pricing_negotiation | enterprise_inquiry
                   (or any descriptive string if none of the above fits)

    Returns:
        Escalation confirmation with:
        - escalation_id
        - urgency level (critical/high/normal/low)
        - routed_to team email
        - SLA (expected response time)
        Returns an error message string on failure.
    """
    logger.info("escalate_to_human | ticket=%r | reason=%r", ticket_id, reason)

    if not ticket_id or not ticket_id.strip():
        return "Error: ticket_id must not be empty."
    if not reason or not reason.strip():
        return "Error: reason must not be empty."

    try:
        ticket_norm = ticket_id.strip()
        reason_norm = reason.strip().lower().replace(" ", "_")

        # Determine urgency and route from reason
        urgency = _URGENCY_MAP.get(reason_norm, "normal")
        routed_to = _ROUTE_MAP.get(reason_norm, "support@nimbusflow.io")
        sla = _SLA_MAP[urgency]

        # Update ticket in memory store
        ticket = _store.get_ticket(ticket_norm)
        if ticket:
            _store.update_ticket(
                ticket_norm,
                status="escalated",
                escalation_reason=reason_norm,
                escalation_urgency=urgency,
                escalated_to=routed_to,
            )
            # Close the conversation as escalated
            if ticket.conversation_id:
                _store.close_conversation(
                    ticket.conversation_id,
                    status="escalated",
                    resolution_type="escalated",
                )

        escalation_id = f"ESC-{uuid.uuid4().hex[:8].upper()}"

        logger.warning(
            "escalate_to_human | ticket=%s | reason=%s | urgency=%s | route=%s",
            ticket_norm, reason_norm, urgency, routed_to,
        )

        return (
            f"Escalated. Escalation ID: {escalation_id}\n"
            f"Ticket: {ticket_norm}\n"
            f"Reason: {reason_norm}\n"
            f"Urgency: {urgency}\n"
            f"Routed to: {routed_to}\n"
            f"Expected response: within {sla}"
        )

    except Exception as exc:
        logger.error("escalate_to_human | error: %s", exc, exc_info=True)
        return f"Error escalating ticket: {exc}"


# ---------------------------------------------------------------------------
# Tool 5: send_response
# ---------------------------------------------------------------------------

@mcp.tool()
async def send_response(ticket_id: str, message: str, channel: str) -> str:
    """Send a response to the customer via the appropriate channel.

    ALWAYS call this last. Never output the response text directly — always
    route it through this tool so it is formatted correctly for the channel,
    stored in the conversation history, and the ticket status is updated.

    Channel formatting rules (from brand-voice.md):
    - email:     Semi-formal. Greeting "Hi [Name],", sign-off "— NimbusFlow Support",
                 ticket reference included. Up to 2000 chars.
    - whatsapp:  Conversational, concise. No greeting/sign-off formulas.
                 Plain text (markdown stripped). Under 300 chars preferred.
    - web_form:  Medium formality. Closing "Hope that helps!". Up to 1000 chars.

    Args:
        ticket_id: The ticket this response belongs to (NF-XXXXXXXX format).
        message:   The response content BEFORE channel formatting.
                   Write the answer clearly — this tool applies all formatting.
                   Do NOT include greetings, sign-offs, or ticket refs here;
                   the formatter adds them.
        channel:   Target channel — one of: email | whatsapp | web_form

    Returns:
        Delivery status confirmation with formatted preview (first 120 chars).
        Returns an error message string on failure.
    """
    logger.info(
        "send_response | ticket=%r | channel=%s | message_len=%d",
        ticket_id, channel, len(message),
    )

    if not ticket_id or not ticket_id.strip():
        return "Error: ticket_id must not be empty."
    if not message or not message.strip():
        return "Error: message must not be empty."

    try:
        channel_norm = _validate_channel(channel)
    except ValueError as exc:
        return f"Error: {exc}"

    try:
        ticket_norm = ticket_id.strip()
        ticket = _store.get_ticket(ticket_norm)

        # Resolve customer name for channel formatting
        customer_name = ""
        if ticket:
            profile = _store.get_customer(ticket.customer_id)
            if profile:
                customer_name = profile.name or ""

        # Apply channel formatting (brand-voice.md rules)
        ch = Channel(channel_norm)
        formatted = format_for_channel(
            text=message.strip(),
            channel=ch,
            customer_name=customer_name,
            ticket_id=ticket_norm,
        )

        # Store as outbound message in conversation history
        if ticket and ticket.conversation_id:
            _store.add_message(
                conversation_id=ticket.conversation_id,
                channel=channel_norm,
                direction="outbound",
                role="agent",
                content=formatted,
            )

        # Update ticket status
        if ticket and ticket.status not in ("escalated", "resolved", "closed"):
            _store.update_ticket(ticket_norm, status="responded")

        # Preview (first 120 chars for confirmation log)
        preview = formatted[:120].replace("\n", " ")
        if len(formatted) > 120:
            preview += "..."

        logger.info(
            "send_response | ticket=%s | channel=%s | formatted_len=%d",
            ticket_norm, channel_norm, len(formatted),
        )

        # In incubation phase, log instead of actually sending
        # Production: call Gmail API / Twilio WhatsApp API here
        print(f"\n[SEND via {channel_norm.upper()}]\n{formatted}\n", file=sys.stderr)

        return (
            f"Response delivered via {channel_norm}. "
            f"Ticket {ticket_norm} updated to 'responded'.\n"
            f"Preview: {preview}"
        )

    except Exception as exc:
        logger.error("send_response | error: %s", exc, exc_info=True)
        return f"Error sending response: {exc}"


# ---------------------------------------------------------------------------
# Entry point — matches hackathon template exactly
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="NimbusFlow Customer Success FTE — MCP Server"
    )
    parser.add_argument(
        "--sse",
        action="store_true",
        help="Run with SSE HTTP transport (default: stdio)",
    )
    parser.add_argument(
        "--host", default="127.0.0.1", help="SSE host (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port", type=int, default=8080, help="SSE port (default: 8080)"
    )
    args = parser.parse_args()

    logger.info("Starting NimbusFlow Customer Success FTE MCP server")

    if args.sse:
        logger.info("Transport: SSE on %s:%d", args.host, args.port)
        mcp.run(transport="sse")
    else:
        logger.info("Transport: stdio")
        mcp.run(transport="stdio")
