"""
production/agent/customer_success_agent.py
OpenAI Agents SDK — NimbusFlow Customer Success FTE definition.

Usage:
    from production.agent.customer_success_agent import run_agent

    result = await run_agent(
        message="How do I set up webhook notifications?",
        channel="email",
        customer_email="alice@acme.com",
        customer_name="Alice",
    )
"""

import logging
import os
import time
from typing import Optional

from agents import Agent, Runner, RunConfig, AsyncOpenAI, OpenAIChatCompletionsModel

from production.agent.tools import ALL_TOOLS
from production.database import queries

logger = logging.getLogger(__name__)

# ── System prompt ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are the NimbusFlow Customer Success FTE — an AI support agent for NimbusFlow,
a B2B project management SaaS platform. You handle support queries across Email,
WhatsApp, and Web Form with accuracy, empathy, and speed.

## MANDATORY WORKFLOW (never skip steps)

1. ALWAYS call `create_ticket` FIRST. No exceptions.
2. ALWAYS call `get_customer_history` to detect repeat contacts.
   - If same issue appeared 3+ times → call `escalate_to_human` with urgency="high"
3. ALWAYS call `analyze_sentiment` on the customer's message.
   - score < 0.1  → call `escalate_to_human` with urgency="critical" immediately
   - score < 0.3  → start response with empathy: "I understand this is frustrating..."
   - score < 0.5  → acknowledge before solving
4. If the query is a product question → call `search_knowledge_base`.
   - If found: use content to answer. Cite the article title.
   - If not found after 2 searches → call `escalate_to_human` with reason="knowledge_gap"
5. Draft response in plain text (channel-aware: no markdown on WhatsApp).
6. ALWAYS call `send_response` LAST. Never output raw text as final answer.

## HARD RULES (NEVER violate)

- NEVER discuss refunds — always escalate to billing team
- NEVER mention competitor products by name
- NEVER promise features not confirmed in knowledge base results
- NEVER share internal email addresses, Slack channels, or employee names
- NEVER exceed: Email=500 words, WhatsApp=300 chars preferred / 1600 max, Web Form=300 words
- NEVER skip `create_ticket` or `send_response`
- NEVER make legal or compliance claims without legal team confirmation

## IMMEDIATE ESCALATION TRIGGERS (call escalate_to_human before drafting any response)

- Legal keywords: "lawyer", "sue", "court", "attorney", "litigation"
- Security: "compromised", "unauthorized access", "hacked", "data breach"
- Financial dispute: "chargeback", "dispute the charge", "credit card dispute"
- Data loss: "tasks disappeared", "data gone", "lost my work"
- Refunds: any refund request
- Human request: "speak to a human", "real person", "agent"

## CONDITIONAL ESCALATION (try to help first, then escalate if unable)

- Pricing negotiation or discount requests
- GDPR, HIPAA, SOC 2, compliance audit requests
- Workspace ownership transfer
- Enterprise custom deployment

## CHANNEL FORMATTING

- Email: formal tone, structured paragraphs, markdown OK, sign off with "Best regards"
- WhatsApp: conversational, ≤300 chars preferred, NO markdown headers, plain text only
- Web Form: semi-formal, helpful, moderate length

## EMPATHY OPENERS (use when sentiment < 0.5)
- "I understand this is frustrating — let me help you resolve this right away."
- "I'm sorry you're experiencing this issue. Here's what we can do:"
- "That sounds difficult. Let me look into this for you."

Remember: You represent NimbusFlow. Be professional, accurate, and always resolve
the customer's issue or get them to the right person who can.
"""


# ── Groq (GroqCloud) external client (OpenAI-compatible endpoint) ─────────────
# Uses OpenAI Agents SDK external provider support.
# Docs: https://console.groq.com/docs

def _get_grok_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=os.getenv("GROQ_API_KEY", os.getenv("GROK_API_KEY", os.getenv("GEMINI_API_KEY", ""))),
        base_url="https://api.groq.com/openai/v1",
    )


# ── Agent singleton ──────────────────────────────────────────────────────────

_agent: Optional[Agent] = None


def get_agent() -> Agent:
    """Get or create the Customer Success FTE agent backed by Grok (xAI)."""
    global _agent
    if _agent is None:
        _agent = Agent(
            name="NimbusFlow Customer Success FTE",
            instructions=SYSTEM_PROMPT,
            tools=ALL_TOOLS,
            model=OpenAIChatCompletionsModel(
                model=os.getenv("GROQ_MODEL", os.getenv("GROK_MODEL", os.getenv("GEMINI_MODEL", "llama-3.3-70b-versatile"))),
                openai_client=_get_grok_client(),
            ),
        )
    return _agent


# ── Runner ───────────────────────────────────────────────────────────────────

async def run_agent(
    message: str,
    channel: str,
    customer_email: Optional[str] = None,
    customer_phone: Optional[str] = None,
    customer_name: Optional[str] = None,
    conversation_id: Optional[str] = None,
    ticket_id: Optional[str] = None,
) -> dict:
    """
    Process a single customer message end-to-end.

    Returns a result dict with:
        - ticket_id: str
        - customer_id: str
        - conversation_id: str
        - response: str (formatted, channel-appropriate)
        - escalated: bool
        - escalation_id: str | None
        - sentiment_score: float
        - latency_ms: int
        - tool_calls: list[str]
    """
    start = time.monotonic()
    agent = get_agent()

    # Build context message for the agent
    context_lines = [f"[Channel: {channel}]"]
    if customer_email:
        context_lines.append(f"[Customer Email: {customer_email}]")
    if customer_phone:
        context_lines.append(f"[Customer Phone: {customer_phone}]")
    if customer_name:
        context_lines.append(f"[Customer Name: {customer_name}]")
    if conversation_id:
        context_lines.append(f"[Existing Conversation ID: {conversation_id}]")
    if ticket_id:
        context_lines.append(f"[Existing Ticket ID: {ticket_id}]")

    full_input = "\n".join(context_lines) + "\n\nCustomer message:\n" + message

    # Load prior conversation messages if continuing
    prior_messages = []
    if conversation_id:
        history = await queries.load_conversation_history(conversation_id)
        prior_messages = history  # [{role, content}, ...]

    # Store inbound message
    if conversation_id:
        await queries.store_message(
            conversation_id=conversation_id,
            channel=channel,
            direction="inbound",
            role="customer",
            content=message,
            delivery_status="delivered",
        )

    run_config = RunConfig(
        tracing_disabled=True,  # Grok (xAI) endpoint — no OpenAI tracing needed
    )

    result = await Runner.run(
        agent,
        input=full_input,
        context=prior_messages if prior_messages else None,
        run_config=run_config,
    )

    latency_ms = int((time.monotonic() - start) * 1000)

    # Extract tool calls made during the run
    tool_calls_made: list[str] = []
    ticket_id_out: Optional[str] = ticket_id
    customer_id_out: Optional[str] = None
    conversation_id_out: Optional[str] = conversation_id
    escalated = False
    escalation_id: Optional[str] = None
    sentiment_score: Optional[float] = None
    response_text: Optional[str] = None

    for step in result.new_items:
        tool_name = getattr(getattr(step, "raw_item", None), "name", None)
        if tool_name:
            tool_calls_made.append(tool_name)

        # Extract key outputs from tool results
        if hasattr(step, "output") and isinstance(step.output, dict):
            out = step.output
            if "ticket_id" in out and not ticket_id_out:
                ticket_id_out = out["ticket_id"]
            if "customer_id" in out:
                customer_id_out = out["customer_id"]
            if "conversation_id" in out and not conversation_id_out:
                conversation_id_out = out["conversation_id"]
            if "escalation_id" in out:
                escalated = True
                escalation_id = out["escalation_id"]
            if "score" in out:
                sentiment_score = out["score"]
            if "formatted_content" in out:
                response_text = out["formatted_content"]

    # Record agent latency metric
    if ticket_id_out and conversation_id_out:
        await queries.record_metric(
            metric_name="agent_latency_ms",
            metric_value=float(latency_ms),
            channel=channel,
            ticket_id=ticket_id_out,
            conversation_id=conversation_id_out,
            dimensions={
                "tool_calls": tool_calls_made,
                "escalated": escalated,
            },
        )

    logger.info(
        "Agent run complete",
        extra={
            "ticket_id": ticket_id_out,
            "channel": channel,
            "latency_ms": latency_ms,
            "escalated": escalated,
            "tools": tool_calls_made,
        },
    )

    return {
        "ticket_id": ticket_id_out,
        "customer_id": customer_id_out,
        "conversation_id": conversation_id_out,
        "response": response_text or result.final_output,
        "escalated": escalated,
        "escalation_id": escalation_id,
        "sentiment_score": sentiment_score,
        "latency_ms": latency_ms,
        "tool_calls": tool_calls_made,
    }
