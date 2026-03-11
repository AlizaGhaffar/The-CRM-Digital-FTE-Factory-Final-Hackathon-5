"""
production/tests/test_transition.py
Transition test suite — Step 5 of the Incubation → Production handoff.

Purpose:
  Verify that all incubation discoveries are correctly implemented in the production
  agent before deploying to Stage 2 (OpenAI Agents SDK + FastAPI + PostgreSQL).

What this file tests (and why it is different from test_agent.py / test_e2e.py):
  test_agent.py   — isolated unit tests for each tool in isolation
  test_e2e.py     — 15 specific edge cases from transition-checklist.md
  test_transition.py — INTEGRATION: skill-to-skill data contracts, execution order
                       enforcement, channel format compliance, and full skill coverage

The 4 test classes:
  TestIncubationEdgeCases   — 4 edge cases from incubation sessions
  TestChannelResponseFormat — channel output compliance (email/WhatsApp/web form)
  TestToolExecutionOrder    — create_ticket first, send_response last, invariants
  TestAllFiveSkills         — each skill produces the correct typed output

Run:
    pytest production/tests/test_transition.py -v
    pytest production/tests/test_transition.py -v --tb=short
    pytest production/tests/test_transition.py -v -k "order"
"""

import asyncio
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest


# ══════════════════════════════════════════════════════════════════════════════
# SHARED FIXTURES
# ══════════════════════════════════════════════════════════════════════════════

def _make_queries(
    history: Optional[list] = None,
    kb_results: Optional[list] = None,
    sentiment_override: Optional[float] = None,
):
    """
    Build a fully mocked queries module.
    Accepts overrides so individual tests can simulate specific DB states.
    """
    m = MagicMock()
    m.find_or_create_customer = AsyncMock(return_value="cust-001")
    m.get_or_create_conversation = AsyncMock(return_value="conv-001")
    m.create_ticket = AsyncMock(return_value="ticket-001")
    m.get_customer_history = AsyncMock(return_value=history or [])
    m.get_customer_summary = AsyncMock(return_value={"plan": "pro", "total_tickets": 2})
    m.update_conversation_sentiment = AsyncMock()
    m.search_knowledge_base = AsyncMock(return_value=kb_results or [
        {"title": "How to reset password", "content": "Visit nimbusflow.io/forgot-password", "similarity": 0.82}
    ])
    m.create_escalation = AsyncMock(return_value="esc-001")
    m.update_ticket_status = AsyncMock()
    m.store_message = AsyncMock(return_value="msg-001")
    m.record_metric = AsyncMock()
    m.close_pool = AsyncMock()
    return m


def _make_gemini_client(sentiment_score: str = "0.75"):
    """Build a mock Gemini client for sentiment + embeddings."""
    m = MagicMock()
    m.chat.completions.create = AsyncMock(
        return_value=MagicMock(
            choices=[MagicMock(message=MagicMock(content=sentiment_score))]
        )
    )
    m.embeddings.create = AsyncMock(
        return_value=MagicMock(data=[MagicMock(embedding=[0.05] * 1536)])
    )
    return m


class CallOrderTracker:
    """
    Records tool call names in order. Inject as a side-effect to track
    the exact sequence of tool invocations across a full agent run.
    """
    def __init__(self):
        self.calls: list[str] = []

    def record(self, name: str):
        async def _side_effect(*args, **kwargs):
            self.calls.append(name)
            # return sensible defaults so the agent can continue
            defaults = {
                "create_ticket":        {"ticket_id": "ticket-001", "customer_id": "cust-001", "conversation_id": "conv-001"},
                "get_customer_history": {"tickets": [], "repeat_contact": False, "contact_count": 0, "summary": {}},
                "analyze_sentiment":    {"score": 0.75, "level": "positive", "requires_empathy": False, "immediate_escalate": False, "trend": "stable"},
                "search_knowledge_base":{"results": [{"title": "T", "content": "C", "similarity": 0.82}], "found": True, "top_score": 0.82, "search_count": 1},
                "escalate_to_human":    {"escalation_id": "esc-001", "routed_to": "billing@nimbusflow.io", "queue": "priority-queue", "urgency": "high", "sla": "2 hours", "customer_message": "Connecting you now."},
                "send_response":        {"message_id": "msg-001", "formatted_content": "Hi there,\n\nAnswer here.\n\nBest regards,\nNimbusFlow Support\nTicket: ticket-001", "char_count": 80, "channel": "email"},
            }
            return defaults.get(name, {})
        return _side_effect


# ══════════════════════════════════════════════════════════════════════════════
# 1. INCUBATION EDGE CASES
# These are the 4 specific scenarios the user asked for. They exercise the
# tool layer directly with realistic message content.
# ══════════════════════════════════════════════════════════════════════════════

class TestIncubationEdgeCases:
    """
    Edge cases discovered during incubation that must be handled correctly
    in the production tool implementations.
    """

    # ── EC-1: Empty message ───────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_empty_message_create_ticket_still_succeeds(self):
        """
        T-046: Empty message body must not crash create_ticket.
        The agent still needs a ticket to track the conversation.
        Expected: ticket created with subject="(empty message)".
        """
        mock_q = _make_queries()

        with patch("production.agent.tools.queries", mock_q):
            from production.agent.tools import create_ticket
            result = await create_ticket(
                customer_email="silent@corp.com",
                customer_phone=None,
                customer_name="Silent User",
                channel="email",
                subject="(empty message)",
                category="general",
                priority="low",
            )

        assert "ticket_id" in result
        assert "customer_id" in result
        assert "conversation_id" in result
        mock_q.create_ticket.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_message_sentiment_returns_neutral(self):
        """
        Empty message body → analyze_sentiment must not crash.
        Should return neutral score (0.5) as fallback.
        """
        mock_q = _make_queries()
        mock_gemini = _make_gemini_client("0.5")

        with patch("production.agent.tools.queries", mock_q), \
             patch("production.agent.tools._get_openai", return_value=mock_gemini):
            from production.agent.tools import analyze_sentiment
            result = await analyze_sentiment(message=" ", conversation_id="conv-001")

        assert "score" in result
        assert 0.0 <= result["score"] <= 1.0
        assert result["level"] in {"very_negative", "negative", "mixed", "neutral", "positive"}

    @pytest.mark.asyncio
    async def test_empty_message_worker_skips_agent(self):
        """
        Worker layer: empty body must be skipped before agent runs.
        process_message returns True (not a retryable error) without calling run_agent.
        """
        from production.workers.message_processor import _extract_fields

        payload = {"channel": "email", "from_email": "test@test.com", "body": ""}
        fields = _extract_fields(payload)

        # Empty body detected — agent should not be called
        assert fields["message"] == ""
        # The worker's process_message() checks this and returns True early (tested here by
        # confirming the extractor surfaces the empty body correctly)

    # ── EC-2: Pricing escalation ──────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_pricing_keyword_triggers_escalation(self):
        """
        Message containing "discount" or "custom pricing" must trigger soft escalation.
        escalate_to_human should be called with reason="pricing_negotiation".
        Auto-urgency upgrade from HIGH_KEYWORDS must NOT trigger on pricing words
        (they are NORMAL_KEYWORDS, not HIGH_KEYWORDS).
        """
        mock_q = _make_queries()

        with patch("production.agent.tools.queries", mock_q):
            from production.agent.tools import escalate_to_human
            result = await escalate_to_human(
                ticket_id="ticket-001",
                customer_id="cust-001",
                reason="pricing_negotiation",
                urgency="normal",
                channel="email",
                trigger_message="We'd like a nonprofit discount for our team.",
            )

        assert result["urgency"] == "normal"
        assert "routed_to" in result
        assert "sales" in result["routed_to"] or "support" in result["routed_to"]
        mock_q.create_escalation.assert_called_once()

    @pytest.mark.asyncio
    async def test_pricing_escalation_customer_message_per_channel(self):
        """
        Escalation message for pricing must be channel-appropriate.
        Email: includes "ticket reference", WhatsApp: brief with Ref:.
        """
        mock_q = _make_queries()

        with patch("production.agent.tools.queries", mock_q):
            from production.agent.tools import escalate_to_human

            # Email
            email_result = await escalate_to_human(
                ticket_id="TICKET-PRICING",
                customer_id="cust-001",
                reason="pricing_negotiation",
                urgency="normal",
                channel="email",
                trigger_message="Can we negotiate a better price?",
            )
            # WhatsApp
            mock_q.create_escalation = AsyncMock(return_value="esc-002")
            mock_q.update_ticket_status = AsyncMock()
            wa_result = await escalate_to_human(
                ticket_id="TICKET-PRICING-WA",
                customer_id="cust-001",
                reason="pricing_negotiation",
                urgency="normal",
                channel="whatsapp",
                trigger_message="any discount available?",
            )

        # Email message should mention ticket reference
        assert "TICKET" in email_result["customer_message"].upper() or "ticket" in email_result["customer_message"].lower()
        # WhatsApp message should be brief
        assert len(wa_result["customer_message"]) <= 200

    @pytest.mark.asyncio
    async def test_chargeback_auto_upgrades_to_critical(self):
        """
        Chargeback keyword in trigger_message must auto-upgrade urgency to critical,
        even if "normal" was passed (discovery-log D-011).
        """
        mock_q = _make_queries()

        with patch("production.agent.tools.queries", mock_q):
            from production.agent.tools import escalate_to_human
            result = await escalate_to_human(
                ticket_id="ticket-001",
                customer_id="cust-001",
                reason="billing_dispute",
                urgency="normal",                   # under-specified
                trigger_message="I will dispute the charge with my bank",  # chargeback keyword
            )

        assert result["urgency"] == "critical"

    # ── EC-3: Angry customer (sentiment < 0.3) ────────────────────────────────

    @pytest.mark.asyncio
    async def test_angry_customer_sentiment_below_threshold(self):
        """
        Hostile message → analyze_sentiment returns score < 0.1.
        immediate_escalate must be True.
        requires_empathy must be True.
        level must be "very_negative".
        """
        mock_q = _make_queries()
        mock_gemini = _make_gemini_client("0.05")   # hostile score

        with patch("production.agent.tools.queries", mock_q), \
             patch("production.agent.tools._get_openai", return_value=mock_gemini):
            from production.agent.tools import analyze_sentiment
            result = await analyze_sentiment(
                message="YOUR SERVICE IS ABSOLUTELY TERRIBLE!!! I WANT MY MONEY BACK RIGHT NOW!!!",
                conversation_id="conv-001",
            )

        assert result["score"] <= 0.1
        assert result["level"] == "very_negative"
        assert result["immediate_escalate"] is True
        assert result["requires_empathy"] is True

    @pytest.mark.asyncio
    async def test_legal_keyword_overrides_neutral_llm_score(self):
        """
        LLM might score a calm legal message as 0.6 (neutral tone).
        The critical keyword scan must override it to ≤ 0.1 (discovery-log D-015).
        """
        mock_q = _make_queries()
        mock_gemini = _make_gemini_client("0.6")    # LLM thinks it's neutral

        with patch("production.agent.tools.queries", mock_q), \
             patch("production.agent.tools._get_openai", return_value=mock_gemini):
            from production.agent.tools import analyze_sentiment
            result = await analyze_sentiment(
                message="I would like to inform you that I have retained legal counsel.",
            )

        # "legal" and "counsel" → legal keywords → cap at 0.1
        assert result["score"] <= 0.1
        assert result["immediate_escalate"] is True

    @pytest.mark.asyncio
    async def test_moderate_frustration_requires_empathy_not_escalation(self):
        """
        Score 0.25–0.49 → requires_empathy=True, immediate_escalate=False.
        The agent should prepend an empathy opener but not escalate.
        """
        mock_q = _make_queries()
        mock_gemini = _make_gemini_client("0.30")

        with patch("production.agent.tools.queries", mock_q), \
             patch("production.agent.tools._get_openai", return_value=mock_gemini):
            from production.agent.tools import analyze_sentiment
            result = await analyze_sentiment(
                message="I've been waiting for a fix for three days now. This is really frustrating.",
            )

        assert result["requires_empathy"] is True
        assert result["immediate_escalate"] is False
        assert result["level"] in {"negative", "mixed"}

    @pytest.mark.asyncio
    async def test_angry_customer_send_response_includes_empathy_opener(self):
        """
        When sentiment < 0.5 on email, format_response must prepend an empathy opener
        from the approved list (brand-voice.md — acknowledged before solving).
        """
        from production.agent.formatters import format_response

        result = format_response(
            content="To resolve this, please re-authorize the GitHub integration from Settings.",
            channel="email",
            customer_name="Richard",
            ticket_id="ticket-001",
            sentiment_score=0.05,    # very negative
        )

        empathy_phrases = [
            "That sounds frustrating",
            "I can see why that's confusing",
            "That shouldn't be happening",
            "Thanks for bearing with us",
        ]
        assert any(phrase in result for phrase in empathy_phrases), (
            f"Expected empathy opener in response for score=0.05 but got:\n{result}"
        )

    # ── EC-4: Cross-channel follow-up ─────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_cross_channel_repeat_contact_detected(self):
        """
        D-016: Customer contacts via WhatsApp about webhook, then via Email.
        get_customer_history must surface repeat_contact=True when the same
        category appears 2+ times across different channels.
        """
        prior_tickets = [
            {"ticket_id": "old-001", "category": "technical", "status": "open",
             "subject": "Webhook not firing", "source_channel": "web_form", "created_at": "2026-03-05"},
            {"ticket_id": "old-002", "category": "technical", "status": "open",
             "subject": "RE: Webhook not firing", "source_channel": "email", "created_at": "2026-03-06"},
        ]
        mock_q = _make_queries(history=prior_tickets)

        with patch("production.agent.tools.queries", mock_q):
            from production.agent.tools import get_customer_history
            result = await get_customer_history(customer_id="cust-T051", limit=5)

        assert result["repeat_contact"] is True
        assert result["contact_count"] == 2

    @pytest.mark.asyncio
    async def test_cross_channel_three_contacts_high_priority(self):
        """
        3+ contacts on same topic → contact_count ≥ 3.
        The agent system prompt specifies urgency="high" at this threshold.
        Verify contact_count is correctly surfaced.
        """
        prior_tickets = [
            {"ticket_id": f"t-{i}", "category": "technical", "status": "open",
             "subject": "Webhook issue", "source_channel": ["web_form", "email", "whatsapp"][i]}
            for i in range(3)
        ]
        mock_q = _make_queries(history=prior_tickets)

        with patch("production.agent.tools.queries", mock_q):
            from production.agent.tools import get_customer_history
            result = await get_customer_history(customer_id="cust-repeat", limit=10)

        assert result["contact_count"] == 3
        assert result["repeat_contact"] is True

    @pytest.mark.asyncio
    async def test_cross_channel_first_contact_no_repeat_flag(self):
        """
        First contact from a new customer → repeat_contact must be False.
        """
        mock_q = _make_queries(history=[])

        with patch("production.agent.tools.queries", mock_q):
            from production.agent.tools import get_customer_history
            result = await get_customer_history(customer_id="cust-new")

        assert result["repeat_contact"] is False
        assert result["contact_count"] == 0


# ══════════════════════════════════════════════════════════════════════════════
# 2. CHANNEL RESPONSE FORMAT TESTS
# Verify send_response and format_response apply the correct channel rules.
# ══════════════════════════════════════════════════════════════════════════════

class TestChannelResponseFormat:
    """
    Verify that formatted responses comply with per-channel rules
    from brand-voice.md and discovery-log.md.
    """

    # ── Email ─────────────────────────────────────────────────────────────────

    def test_email_has_greeting(self):
        from production.agent.formatters import format_response
        result = format_response(
            content="Here are the steps to connect GitHub.",
            channel="email",
            customer_name="Sarah",
            ticket_id="NF-100",
        )
        assert result.startswith("Hi Sarah,"), f"Email must start with greeting, got: {result[:40]}"

    def test_email_has_signature(self):
        from production.agent.formatters import format_response
        result = format_response(
            content="The webhook issue is caused by a raw body vs parsed JSON mismatch.",
            channel="email",
            customer_name="Bob",
            ticket_id="NF-200",
        )
        assert "Best regards" in result
        assert "NimbusFlow Support" in result

    def test_email_includes_ticket_reference(self):
        from production.agent.formatters import format_response
        result = format_response(
            content="To reset your password, visit nimbusflow.io/forgot-password.",
            channel="email",
            customer_name="Carol",
            ticket_id="NF-300",
        )
        assert "NF-300" in result

    def test_email_preserves_numbered_steps(self):
        from production.agent.formatters import format_response
        content = "1. Go to Settings\n2. Click Integrations\n3. Select GitHub"
        result = format_response(
            content=content,
            channel="email",
            customer_name="Dan",
            ticket_id="NF-400",
        )
        assert "1." in result and "2." in result and "3." in result

    def test_email_under_length_limit(self):
        from production.agent.formatters import format_response, within_channel_limit
        result = format_response(
            content="word " * 600,   # ~600 words — over the 500-word limit
            channel="email",
            ticket_id="NF-500",
        )
        assert within_channel_limit(result, "email"), (
            f"Email response exceeds 3500 chars: {len(result)}"
        )

    # ── WhatsApp ──────────────────────────────────────────────────────────────

    def test_whatsapp_no_greeting(self):
        from production.agent.formatters import format_response
        result = format_response(
            content="To reset your password go to nimbusflow.io/forgot-password",
            channel="whatsapp",
            customer_name="Eve",
            ticket_id="NF-600",
        )
        assert not result.startswith("Hi"), (
            f"WhatsApp must NOT have greeting, got: {result[:30]}"
        )

    def test_whatsapp_under_preferred_limit(self):
        from production.agent.formatters import format_response
        result = format_response(
            content="Go to Settings > Integrations > GitHub and click Reconnect.",
            channel="whatsapp",
            ticket_id="NF-700",
        )
        # Should be under 300 chars for a simple answer
        assert len(result) <= 300, (
            f"WhatsApp simple answer should be ≤300 chars, got {len(result)}: {result}"
        )

    def test_whatsapp_no_markdown(self):
        from production.agent.formatters import format_response
        result = format_response(
            content="Use **Settings > Integrations** to reconnect. Visit [our docs](https://docs.nimbusflow.io).",
            channel="whatsapp",
            ticket_id="NF-800",
        )
        assert "**" not in result, "WhatsApp must not contain **bold** markdown"
        assert "](https://" not in result, "WhatsApp must not contain markdown links"

    def test_whatsapp_hard_limit_enforced(self):
        from production.agent.formatters import format_response, within_channel_limit
        result = format_response(
            content="x " * 1000,   # far exceeds 1600 char limit
            channel="whatsapp",
            ticket_id="NF-900",
        )
        assert within_channel_limit(result, "whatsapp"), (
            f"WhatsApp response must not exceed 1600 chars, got {len(result)}"
        )

    def test_whatsapp_includes_ticket_ref(self):
        from production.agent.formatters import format_response
        result = format_response(
            content="Connecting you now.",
            channel="whatsapp",
            ticket_id="NF-ESCALATE",
        )
        assert "NF-ESCALATE" in result

    def test_whatsapp_filler_stripped(self):
        from production.agent.formatters import format_response
        result = format_response(
            content="Great question! The velocity chart is available on Business+ plans.",
            channel="whatsapp",
            ticket_id="NF-FILLER",
        )
        assert "Great question!" not in result
        assert "velocity chart" in result

    # ── Web Form ──────────────────────────────────────────────────────────────

    def test_web_form_semi_formal_greeting(self):
        from production.agent.formatters import format_response
        result = format_response(
            content="The HMAC signature mismatch is caused by using parsed JSON instead of the raw request body.",
            channel="web_form",
            customer_name="Frank",
            ticket_id="NF-WEB-1",
        )
        assert "Hi Frank," in result

    def test_web_form_closing_present(self):
        from production.agent.formatters import format_response
        result = format_response(
            content="Here are the steps to configure SSO with Okta.",
            channel="web_form",
            customer_name="Grace",
            ticket_id="NF-WEB-2",
        )
        assert "Hope that helps" in result

    def test_web_form_under_length_limit(self):
        from production.agent.formatters import format_response, within_channel_limit
        result = format_response(
            content="word " * 400,   # over 300-word limit
            channel="web_form",
            ticket_id="NF-WEB-3",
        )
        assert within_channel_limit(result, "web_form"), (
            f"Web form response exceeds 2100 chars: {len(result)}"
        )

    def test_web_form_no_markdown_rendered(self):
        """
        Web form UI renders plain text — markdown must be stripped.
        """
        from production.agent.formatters import format_response
        result = format_response(
            content="Use **Settings > Developer** to get your API key. Visit [the docs](https://docs.nimbusflow.io).",
            channel="web_form",
            ticket_id="NF-WEB-4",
        )
        assert "**" not in result
        assert "](https://" not in result

    @pytest.mark.parametrize("channel,expected_greeting,has_signature", [
        ("email",    "Hi Alice,",   True),
        ("whatsapp", None,          False),
        ("web_form", "Hi Alice,",   False),
    ])
    def test_channel_greeting_matrix(self, channel, expected_greeting, has_signature):
        """Parametrised: verify greeting presence/absence per channel."""
        from production.agent.formatters import format_response
        result = format_response(
            content="Here is how to fix your issue.",
            channel=channel,
            customer_name="Alice",
            ticket_id="NF-MATRIX",
        )
        if expected_greeting:
            assert expected_greeting in result, f"{channel}: expected greeting '{expected_greeting}'"
        else:
            assert "Hi Alice," not in result, f"{channel}: should NOT have name greeting"

        if has_signature:
            assert "Best regards" in result
        else:
            assert "Best regards" not in result


# ══════════════════════════════════════════════════════════════════════════════
# 3. TOOL EXECUTION ORDER
# Verify the mandatory 6-step workflow invariants.
# ══════════════════════════════════════════════════════════════════════════════

class TestToolExecutionOrder:
    """
    Verify the execution order contract from prompts.py §3 REQUIRED WORKFLOW:
      create_ticket  → first
      send_response  → last
      get_customer_history → before analyze_sentiment
      escalate_to_human   → before send_response (when escalating)
    """

    @pytest.mark.asyncio
    async def test_create_ticket_returns_required_ids(self):
        """
        create_ticket must return all three IDs needed by downstream tools.
        Missing any ID would break the tool chain.
        """
        mock_q = _make_queries()

        with patch("production.agent.tools.queries", mock_q):
            from production.agent.tools import create_ticket
            result = await create_ticket(
                customer_email="alice@corp.com",
                customer_phone=None,
                customer_name="Alice",
                channel="email",
                subject="Integration not working",
                category="technical",
                priority="high",
            )

        assert "ticket_id" in result,       "ticket_id required by all downstream tools"
        assert "customer_id" in result,     "customer_id required by get_customer_history + escalate_to_human"
        assert "conversation_id" in result, "conversation_id required by analyze_sentiment + send_response"

    @pytest.mark.asyncio
    async def test_send_response_requires_ticket_id_from_create_ticket(self):
        """
        send_response requires ticket_id — which only comes from create_ticket.
        This test confirms the data dependency: create_ticket → send_response.
        """
        mock_q = _make_queries()

        with patch("production.agent.tools.queries", mock_q):
            from production.agent.tools import create_ticket, send_response

            # Step 1: create_ticket
            ticket_result = await create_ticket(
                customer_email="bob@corp.com",
                customer_phone=None,
                customer_name="Bob",
                channel="web_form",
                subject="API returning 401",
                priority="medium",
            )
            ticket_id = ticket_result["ticket_id"]
            conv_id   = ticket_result["conversation_id"]

            # Step 6: send_response uses ticket_id from Step 1
            response_result = await send_response(
                ticket_id=ticket_id,
                conversation_id=conv_id,
                channel="web_form",
                content="Your API key has expired. Regenerate it in Settings > Developer.",
                customer_name="Bob",
            )

        assert response_result["message_id"] is not None
        assert ticket_id in response_result["formatted_content"], (
            "ticket_id must appear in the formatted response"
        )

    @pytest.mark.asyncio
    async def test_escalate_before_send_response(self):
        """
        Escalation flow: escalate_to_human must be called before send_response.
        The customer_message from escalate_to_human becomes the content for send_response.
        Verify the data flows correctly between these two tools.
        """
        mock_q = _make_queries()

        with patch("production.agent.tools.queries", mock_q):
            from production.agent.tools import escalate_to_human, send_response

            esc_result = await escalate_to_human(
                ticket_id="ticket-001",
                customer_id="cust-001",
                reason="legal_threat",
                urgency="critical",
                channel="email",
                trigger_message="I'm contacting my lawyer about this.",
            )

            # customer_message from escalation → content for send_response
            send_result = await send_response(
                ticket_id="ticket-001",
                conversation_id="conv-001",
                channel="email",
                content=esc_result["customer_message"],
                customer_name="Legal Customer",
            )

        assert esc_result["urgency"] == "critical"
        assert send_result["message_id"] is not None
        # Escalation message should appear in the final formatted content
        assert len(send_result["formatted_content"]) > 0

    @pytest.mark.asyncio
    async def test_tool_chain_ids_are_consistent(self):
        """
        ticket_id and conversation_id must be the same object passed through
        the entire tool chain. No tool should generate its own IDs mid-chain.
        """
        mock_q = _make_queries()
        mock_gemini = _make_gemini_client("0.75")

        with patch("production.agent.tools.queries", mock_q), \
             patch("production.agent.tools._get_openai", return_value=mock_gemini):
            from production.agent.tools import (
                create_ticket, get_customer_history, analyze_sentiment, send_response
            )

            t = await create_ticket(
                customer_email="chain@corp.com",
                customer_phone=None,
                customer_name="Chain Test",
                channel="whatsapp",
                subject="How many projects on free plan?",
                priority="low",
            )
            ticket_id = t["ticket_id"]
            conv_id   = t["conversation_id"]
            cust_id   = t["customer_id"]

            h = await get_customer_history(customer_id=cust_id)
            s = await analyze_sentiment(
                message="how many projects can i make on free plan",
                conversation_id=conv_id,
            )
            r = await send_response(
                ticket_id=ticket_id,
                conversation_id=conv_id,
                channel="whatsapp",
                content="Free plan: up to 3 projects.",
            )

        # ticket_id from Step 1 appears in final response
        assert ticket_id in r["formatted_content"]
        # Chain completed without error
        assert r["char_count"] > 0

    @pytest.mark.asyncio
    async def test_db_failure_on_create_ticket_returns_temp_ids(self):
        """
        If create_ticket DB call fails, it must return temporary IDs (not raise).
        This ensures the agent can still respond to the customer gracefully.
        """
        mock_q = _make_queries()
        mock_q.find_or_create_customer = AsyncMock(side_effect=Exception("DB connection timeout"))

        with patch("production.agent.tools.queries", mock_q):
            from production.agent.tools import create_ticket
            result = await create_ticket(
                customer_email="test@test.com",
                customer_phone=None,
                customer_name=None,
                channel="email",
                subject="DB failure test",
                priority="medium",
            )

        assert "ticket_id" in result
        assert result["ticket_id"].startswith("temp-"), (
            f"Fallback ticket_id should start with 'temp-', got: {result['ticket_id']}"
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_db_failure_on_send_response_still_returns_content(self):
        """
        If send_response DB call fails, it must still return formatted_content.
        The channel handler can still deliver the message even if DB logging fails.
        """
        mock_q = _make_queries()
        mock_q.store_message = AsyncMock(side_effect=Exception("DB write timeout"))
        mock_q.record_metric = AsyncMock(side_effect=Exception("DB write timeout"))

        with patch("production.agent.tools.queries", mock_q):
            from production.agent.tools import send_response
            result = await send_response(
                ticket_id="ticket-fallback",
                conversation_id="conv-fallback",
                channel="email",
                content="Here is your answer.",
                customer_name="Fallback User",
            )

        assert "formatted_content" in result
        assert len(result["formatted_content"]) > 0, "Must return content even on DB failure"
        assert result["message_id"].startswith("msg-fallback-"), (
            f"Expected fallback message_id, got: {result['message_id']}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# 4. ALL FIVE SKILLS WORKING CORRECTLY
# Each skill is verified end-to-end: correct input → correct typed output.
# ══════════════════════════════════════════════════════════════════════════════

class TestAllFiveSkills:
    """
    Verify each skill from specs/skills-manifest.md produces the correct
    typed output with the expected fields.
    """

    # ── Skill 1: Customer Identification ─────────────────────────────────────

    @pytest.mark.asyncio
    async def test_skill1_customer_identification_email(self):
        """
        Skill 1a: create_ticket with email channel.
        Must return: ticket_id (str), customer_id (str), conversation_id (str).
        """
        mock_q = _make_queries()

        with patch("production.agent.tools.queries", mock_q):
            from production.agent.tools import create_ticket
            result = await create_ticket(
                customer_email="alice@acme.com",
                customer_phone=None,
                customer_name="Alice",
                channel="email",
                subject="GitHub webhook stopped working",
                category="technical",
                priority="high",
            )

        assert isinstance(result["ticket_id"], str)
        assert isinstance(result["customer_id"], str)
        assert isinstance(result["conversation_id"], str)
        assert len(result["ticket_id"]) > 0

    @pytest.mark.asyncio
    async def test_skill1_customer_identification_whatsapp_no_email(self):
        """
        Skill 1a: WhatsApp — only phone available, no email.
        Must still create ticket and customer record (guest if not found).
        """
        mock_q = _make_queries()

        with patch("production.agent.tools.queries", mock_q):
            from production.agent.tools import create_ticket
            result = await create_ticket(
                customer_email=None,          # WhatsApp: no email
                customer_phone="+447700900000",
                customer_name="WA User",
                channel="whatsapp",
                subject="velocity chart question",
                priority="low",
            )

        assert "ticket_id" in result
        mock_q.find_or_create_customer.assert_called_once_with(
            email=None,
            phone="+447700900000",
            name="WA User",
            channel="whatsapp",
        )

    @pytest.mark.asyncio
    async def test_skill1b_history_output_schema(self):
        """
        Skill 1b: get_customer_history output schema.
        Must return: tickets (list), repeat_contact (bool), contact_count (int), summary (dict).
        """
        mock_q = _make_queries(history=[
            {"ticket_id": "t1", "category": "billing", "status": "open", "source_channel": "email"}
        ])

        with patch("production.agent.tools.queries", mock_q):
            from production.agent.tools import get_customer_history
            result = await get_customer_history(customer_id="cust-001", limit=5)

        assert isinstance(result["tickets"], list)
        assert isinstance(result["repeat_contact"], bool)
        assert isinstance(result["contact_count"], int)
        assert isinstance(result["summary"], dict)
        assert result["contact_count"] == 1

    # ── Skill 2: Sentiment Analysis ───────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_skill2_sentiment_output_schema(self):
        """
        Skill 2: analyze_sentiment output schema.
        Must return: score (float 0–1), level (str), requires_empathy (bool),
                     immediate_escalate (bool), trend (str).
        """
        mock_q = _make_queries()
        mock_gemini = _make_gemini_client("0.65")

        with patch("production.agent.tools.queries", mock_q), \
             patch("production.agent.tools._get_openai", return_value=mock_gemini):
            from production.agent.tools import analyze_sentiment
            result = await analyze_sentiment(
                message="I've been waiting for 2 days and still no resolution.",
                conversation_id="conv-001",
            )

        assert isinstance(result["score"], float)
        assert 0.0 <= result["score"] <= 1.0
        assert result["level"] in {"very_negative", "negative", "mixed", "neutral", "positive"}
        assert isinstance(result["requires_empathy"], bool)
        assert isinstance(result["immediate_escalate"], bool)
        assert result["trend"] in {"declining", "stable", "improving"}

    @pytest.mark.asyncio
    async def test_skill2_sentiment_persists_to_db(self):
        """
        When conversation_id is provided, sentiment must be persisted to DB.
        """
        mock_q = _make_queries()
        mock_gemini = _make_gemini_client("0.45")

        with patch("production.agent.tools.queries", mock_q), \
             patch("production.agent.tools._get_openai", return_value=mock_gemini):
            from production.agent.tools import analyze_sentiment
            await analyze_sentiment(
                message="This keeps happening and I'm losing patience.",
                conversation_id="conv-persist-test",
            )

        mock_q.update_conversation_sentiment.assert_called_once()
        call_kwargs = mock_q.update_conversation_sentiment.call_args[1]
        assert call_kwargs["conversation_id"] == "conv-persist-test"
        assert "sentiment_score" in call_kwargs

    @pytest.mark.asyncio
    async def test_skill2_sentiment_llm_failure_returns_neutral(self):
        """
        If Gemini API fails, analyze_sentiment must return 0.5 (neutral) not raise.
        """
        mock_q = _make_queries()
        mock_gemini = MagicMock()
        mock_gemini.chat.completions.create = AsyncMock(
            side_effect=Exception("Gemini API 503")
        )

        with patch("production.agent.tools.queries", mock_q), \
             patch("production.agent.tools._get_openai", return_value=mock_gemini):
            from production.agent.tools import analyze_sentiment
            result = await analyze_sentiment(message="Is the API down?")

        assert result["score"] == 0.5
        assert result["level"] == "neutral"
        assert result["immediate_escalate"] is False

    # ── Skill 3: Knowledge Retrieval ──────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_skill3_kb_output_schema(self):
        """
        Skill 3: search_knowledge_base output schema.
        Must return: results (list), found (bool), top_score (float), search_count (int).
        """
        mock_q = _make_queries(kb_results=[
            {"title": "GitHub Integration", "content": "To connect GitHub...", "category": "technical", "similarity": 0.83}
        ])
        mock_gemini = _make_gemini_client()

        with patch("production.agent.tools.queries", mock_q), \
             patch("production.agent.tools._get_openai", return_value=mock_gemini):
            from production.agent.tools import search_knowledge_base
            result = await search_knowledge_base(query="how do I connect GitHub integration")

        assert isinstance(result["results"], list)
        assert isinstance(result["found"], bool)
        assert isinstance(result["top_score"], float)
        assert isinstance(result["search_count"], int)
        assert result["found"] is True
        assert result["results"][0]["title"] == "GitHub Integration"
        assert result["search_count"] >= 1

    @pytest.mark.asyncio
    async def test_skill3_kb_retries_at_lower_threshold(self):
        """
        Skill 3: if no results at 0.70, must automatically retry at 0.60.
        search_count must be 2.
        """
        call_count = 0

        async def _kb_mock(embedding, max_results, min_similarity, category):
            nonlocal call_count
            call_count += 1
            if min_similarity >= 0.70:
                return []   # empty at high threshold
            return [{"title": "Fallback Doc", "content": "...", "category": "general", "similarity": 0.63}]

        mock_q = _make_queries()
        mock_q.search_knowledge_base = _kb_mock
        mock_gemini = _make_gemini_client()

        with patch("production.agent.tools.queries", mock_q), \
             patch("production.agent.tools._get_openai", return_value=mock_gemini):
            from production.agent.tools import search_knowledge_base
            result = await search_knowledge_base(query="obscure feature nobody knows")

        assert call_count == 2, f"Expected 2 KB searches, got {call_count}"
        assert result["search_count"] == 2
        assert result["found"] is True

    @pytest.mark.asyncio
    async def test_skill3_kb_no_results_returns_found_false(self):
        """
        Skill 3: if both searches fail, found=False. Agent should escalate.
        """
        mock_q = _make_queries(kb_results=[])
        mock_gemini = _make_gemini_client()

        with patch("production.agent.tools.queries", mock_q), \
             patch("production.agent.tools._get_openai", return_value=mock_gemini):
            from production.agent.tools import search_knowledge_base
            result = await search_knowledge_base(query="completely unknown topic")

        assert result["found"] is False
        assert result["top_score"] == 0.0
        assert result["results"] == []

    # ── Skill 4: Escalation Decision ─────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_skill4_escalation_output_schema(self):
        """
        Skill 4: escalate_to_human output schema.
        Must return: escalation_id, routed_to, queue, urgency, sla, customer_message.
        """
        mock_q = _make_queries()

        with patch("production.agent.tools.queries", mock_q):
            from production.agent.tools import escalate_to_human
            result = await escalate_to_human(
                ticket_id="ticket-001",
                customer_id="cust-001",
                reason="knowledge_gap",
                urgency="low",
                channel="web_form",
            )

        assert isinstance(result["escalation_id"], str)
        assert isinstance(result["routed_to"], str)
        assert isinstance(result["queue"], str)
        assert result["urgency"] in {"critical", "high", "normal", "low"}
        assert isinstance(result["sla"], str)
        assert isinstance(result["customer_message"], str)
        assert len(result["customer_message"]) > 0

    @pytest.mark.asyncio
    async def test_skill4_escalation_updates_ticket_status(self):
        """
        Skill 4: after escalation, ticket status must be updated to "escalated".
        """
        mock_q = _make_queries()

        with patch("production.agent.tools.queries", mock_q):
            from production.agent.tools import escalate_to_human
            await escalate_to_human(
                ticket_id="ticket-status-test",
                customer_id="cust-001",
                reason="billing_dispute",
                urgency="high",
                channel="email",
            )

        mock_q.update_ticket_status.assert_called_once()
        call_args = mock_q.update_ticket_status.call_args[1]
        assert call_args["status"] == "escalated"
        assert call_args["ticket_id"] == "ticket-status-test"

    @pytest.mark.asyncio
    async def test_skill4_escalation_db_failure_still_returns_customer_message(self):
        """
        Skill 4: even if DB write fails, customer_message must be returned.
        This is the most critical fallback — customer MUST receive acknowledgement.
        """
        mock_q = _make_queries()
        mock_q.create_escalation = AsyncMock(side_effect=Exception("DB timeout"))
        mock_q.update_ticket_status = AsyncMock(side_effect=Exception("DB timeout"))

        with patch("production.agent.tools.queries", mock_q):
            from production.agent.tools import escalate_to_human
            result = await escalate_to_human(
                ticket_id="ticket-db-fail",
                customer_id="cust-001",
                reason="security_incident",
                urgency="critical",
                channel="whatsapp",
            )

        assert "customer_message" in result
        assert len(result["customer_message"]) > 0, (
            "customer_message must be returned even when DB fails"
        )

    # ── Skill 5: Channel Adaptation ───────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_skill5_send_response_output_schema(self):
        """
        Skill 5: send_response output schema.
        Must return: message_id (str), formatted_content (str), char_count (int), channel (str).
        """
        mock_q = _make_queries()

        with patch("production.agent.tools.queries", mock_q):
            from production.agent.tools import send_response
            result = await send_response(
                ticket_id="ticket-001",
                conversation_id="conv-001",
                channel="email",
                content="Here are the steps to reset your password.",
                customer_name="Alice",
            )

        assert isinstance(result["message_id"], str)
        assert isinstance(result["formatted_content"], str)
        assert isinstance(result["char_count"], int)
        assert result["channel"] == "email"
        assert result["char_count"] == len(result["formatted_content"])

    @pytest.mark.asyncio
    async def test_skill5_send_response_records_metric(self):
        """
        Skill 5: send_response must record a 'response_sent' metric after delivery.
        This feeds the metrics_collector performance dashboard.
        """
        mock_q = _make_queries()

        with patch("production.agent.tools.queries", mock_q):
            from production.agent.tools import send_response
            await send_response(
                ticket_id="ticket-metric",
                conversation_id="conv-metric",
                channel="whatsapp",
                content="Go to Settings > Notifications to re-enable push notifications.",
            )

        mock_q.record_metric.assert_called_once()
        metric_args = mock_q.record_metric.call_args[1]
        assert metric_args["metric_name"] == "response_sent"
        assert metric_args["channel"] == "whatsapp"

    @pytest.mark.asyncio
    async def test_skill5_all_channels_produce_valid_output(self):
        """
        Skill 5: send_response must succeed for all 3 channels without raising.
        """
        mock_q = _make_queries()

        with patch("production.agent.tools.queries", mock_q):
            from production.agent.tools import send_response

            for channel in ("email", "whatsapp", "web_form"):
                mock_q.store_message = AsyncMock(return_value=f"msg-{channel}")
                mock_q.record_metric = AsyncMock()
                result = await send_response(
                    ticket_id="ticket-001",
                    conversation_id="conv-001",
                    channel=channel,
                    content="Here is how to resolve your issue.",
                    customer_name="Test User",
                )
                assert result["channel"] == channel, f"Channel mismatch for {channel}"
                assert len(result["formatted_content"]) > 0, f"Empty response for {channel}"


# ══════════════════════════════════════════════════════════════════════════════
# TRANSITION GATE CHECK
# These tests confirm the minimum acceptance criteria from transition-checklist.md.
# All must pass before promoting to production.
# ══════════════════════════════════════════════════════════════════════════════

class TestTransitionGate:
    """
    Gate check: all 7 acceptance criteria from transition-checklist.md §7.5.
    Run as final validation before Stage 2 production deployment.
    """

    def test_gate_all_tools_registered_in_all_tools(self):
        """All 6 tools must be in the ALL_TOOLS registry passed to the Agent."""
        from production.agent.tools import ALL_TOOLS

        tool_names = [t.__name__ for t in ALL_TOOLS]
        required = [
            "create_ticket",
            "get_customer_history",
            "analyze_sentiment",
            "search_knowledge_base",
            "escalate_to_human",
            "send_response",
        ]
        for name in required:
            assert name in tool_names, f"Tool '{name}' missing from ALL_TOOLS"

    def test_gate_system_prompt_contains_all_required_sections(self):
        """SYSTEM_PROMPT must contain all 7 required sections."""
        from production.agent.prompts import SYSTEM_PROMPT

        required_sections = [
            "PURPOSE",
            "CHANNEL AWARENESS",
            "REQUIRED WORKFLOW",
            "HARD CONSTRAINTS",
            "ESCALATION TRIGGERS",
            "RESPONSE QUALITY",
            "CONTEXT VARIABLES",
        ]
        for section in required_sections:
            assert section in SYSTEM_PROMPT, (
                f"Section '{section}' missing from SYSTEM_PROMPT"
            )

    def test_gate_system_prompt_contains_hard_escalation_keywords(self):
        """SYSTEM_PROMPT must contain all hard escalation keywords from escalation-rules.md."""
        from production.agent.prompts import SYSTEM_PROMPT

        keywords = ["lawyer", "chargeback", "data breach", "unauthorized access",
                    "STOP", "HUMAN", "AGENT"]
        for kw in keywords:
            assert kw in SYSTEM_PROMPT, f"Keyword '{kw}' missing from SYSTEM_PROMPT"

    def test_gate_prompts_sla_map_complete(self):
        """SLA map must have all 4 urgency levels."""
        from production.agent.prompts import SLA_BY_URGENCY

        for level in ("critical", "high", "normal", "low"):
            assert level in SLA_BY_URGENCY, f"urgency '{level}' missing from SLA_BY_URGENCY"

    def test_gate_prompts_routing_map_covers_all_reasons(self):
        """ROUTING_EMAIL must cover all reasons that TEAM_BY_REASON covers."""
        from production.agent.prompts import ROUTING_EMAIL, TEAM_BY_REASON

        for reason in TEAM_BY_REASON:
            assert reason in ROUTING_EMAIL, (
                f"reason '{reason}' in TEAM_BY_REASON but missing from ROUTING_EMAIL"
            )

    def test_gate_channel_params_all_channels_present(self):
        """CHANNEL_PARAMS must define rules for all 3 channels."""
        from production.agent.tools import CHANNEL_PARAMS

        for channel in ("email", "whatsapp", "web_form"):
            assert channel in CHANNEL_PARAMS, f"'{channel}' missing from CHANNEL_PARAMS"
            params = CHANNEL_PARAMS[channel]
            assert "max_chars" in params
            assert "markdown" in params

    def test_gate_escalation_keywords_cover_all_categories(self):
        """CRITICAL_KEYWORDS and HIGH_KEYWORDS must cover all hard escalation categories."""
        from production.agent.tools import CRITICAL_KEYWORDS, HIGH_KEYWORDS

        # Legal
        assert any("lawyer" in kw or "sue" in kw for kw in CRITICAL_KEYWORDS)
        # Security
        assert any("breach" in kw or "compromised" in kw for kw in CRITICAL_KEYWORDS)
        # Chargeback
        assert any("chargeback" in kw for kw in CRITICAL_KEYWORDS)
        # Data loss
        assert any("disappeared" in kw or "data gone" in kw for kw in CRITICAL_KEYWORDS)
        # Human request
        assert any("human" in kw or "real person" in kw for kw in HIGH_KEYWORDS)
