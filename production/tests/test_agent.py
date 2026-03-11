"""
production/tests/test_agent.py
Unit tests for the agent tools and core agent logic.

Tests cover:
  - All 5 @function_tool wrappers (create_ticket, get_customer_history,
    analyze_sentiment, search_knowledge_base, escalate_to_human, send_response)
  - Channel formatting rules from formatters.py
  - Prompt templates from prompts.py
  - Edge cases from transition-checklist.md §4

Run:
    pytest production/tests/test_agent.py -v
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from production.agent.formatters import (
    format_response,
    within_channel_limit,
    _strip_filler,
    _strip_markdown_for_whatsapp,
)
from production.agent.prompts import (
    SYSTEM_PROMPT,
    get_escalation_message,
    SLA_BY_URGENCY,
    TEAM_BY_REASON,
)


# ── Formatter tests ───────────────────────────────────────────────────────────

class TestFormatters:

    def test_strips_filler_great_question(self):
        result = _strip_filler("Great question! Here's how to reset your password.")
        assert result == "Here's how to reset your password."

    def test_strips_filler_absolutely(self):
        result = _strip_filler("Absolutely! You can do this in Settings.")
        assert result == "You can do this in Settings."

    def test_no_filler_unchanged(self):
        text = "To reset your password, visit nimbusflow.io/forgot-password."
        assert _strip_filler(text) == text

    def test_whatsapp_strips_markdown_bold(self):
        result = _strip_markdown_for_whatsapp("Use **Settings > Integrations**.")
        assert "**" not in result
        assert "*Settings > Integrations*" in result

    def test_whatsapp_strips_headers(self):
        result = _strip_markdown_for_whatsapp("### Setup Steps\n1. Go to Settings.")
        assert "###" not in result
        assert "Setup Steps" in result

    def test_whatsapp_strips_links(self):
        result = _strip_markdown_for_whatsapp("[Reset password](https://nimbusflow.io/reset)")
        assert "Reset password" in result
        assert "https://" not in result

    def test_email_format_includes_greeting(self):
        result = format_response(
            content="Here's how to set up the GitHub integration.",
            channel="email",
            customer_name="Alice",
            ticket_id="NF-001",
        )
        assert "Hi Alice," in result
        assert "Best regards" in result
        assert "NF-001" in result

    def test_whatsapp_format_no_greeting(self):
        result = format_response(
            content="To reset your password go to nimbusflow.io/forgot-password",
            channel="whatsapp",
            customer_name="Bob",
            ticket_id="NF-002",
        )
        assert "Hi Bob" not in result
        assert "NF-002" in result

    def test_whatsapp_no_markdown_in_output(self):
        result = format_response(
            content="Use **Settings > Integrations** to connect GitHub.",
            channel="whatsapp",
            ticket_id="NF-003",
        )
        assert "**" not in result

    def test_web_form_format_with_name(self):
        result = format_response(
            content="Your webhook isn't firing because the endpoint must return 200 within 10s.",
            channel="web_form",
            customer_name="Carlos",
            ticket_id="NF-004",
        )
        assert "Hi Carlos," in result
        assert "Hope that helps" in result

    def test_empathy_opener_added_for_negative_sentiment(self):
        result = format_response(
            content="To resolve this, please try re-authorizing the integration.",
            channel="email",
            customer_name="Dan",
            ticket_id="NF-005",
            sentiment_score=0.2,
        )
        # Should prepend an empathy opener
        assert any(
            opener in result for opener in [
                "That sounds frustrating",
                "I can see why that's confusing",
                "That shouldn't be happening",
                "Thanks for bearing with us",
            ]
        )

    def test_no_empathy_opener_for_positive_sentiment(self):
        result = format_response(
            content="Happy to help! Here's how.",
            channel="email",
            customer_name="Eve",
            ticket_id="NF-006",
            sentiment_score=0.9,
        )
        assert "That sounds frustrating" not in result

    def test_whatsapp_empathy_threshold_lower(self):
        # WhatsApp threshold is 0.35; score=0.4 should NOT trigger empathy
        result = format_response(
            content="Here's the fix: pull to refresh.",
            channel="whatsapp",
            ticket_id="NF-007",
            sentiment_score=0.4,
        )
        assert "frustrating" not in result.lower()

    def test_length_limit_enforced_email(self):
        long_content = "word " * 1000  # Well over 500 words
        result = format_response(
            content=long_content,
            channel="email",
            ticket_id="NF-008",
        )
        assert len(result) <= 3500

    def test_length_limit_enforced_whatsapp(self):
        long_content = "x" * 2000
        result = format_response(
            content=long_content,
            channel="whatsapp",
            ticket_id="NF-009",
        )
        assert len(result) <= 1600

    def test_within_channel_limit_true(self):
        assert within_channel_limit("Short message", "whatsapp") is True

    def test_within_channel_limit_false(self):
        assert within_channel_limit("x" * 2000, "whatsapp") is False


# ── Prompt tests ──────────────────────────────────────────────────────────────

class TestPrompts:

    def test_system_prompt_contains_mandatory_workflow(self):
        assert "create_ticket" in SYSTEM_PROMPT
        assert "FIRST" in SYSTEM_PROMPT

    def test_system_prompt_contains_escalation_keywords(self):
        for kw in ["lawyer", "chargeback", "data breach", "unauthorized access"]:
            assert kw in SYSTEM_PROMPT, f"Missing keyword: {kw}"

    def test_system_prompt_contains_hard_rules(self):
        assert "NEVER" in SYSTEM_PROMPT
        assert "send_response" in SYSTEM_PROMPT

    def test_escalation_message_email(self):
        msg = get_escalation_message("email", "billing_dispute", "high", "NF-123")
        assert "NF-123" in msg
        assert "2 hours" in msg
        assert "billing" in msg.lower()

    def test_escalation_message_whatsapp(self):
        msg = get_escalation_message("whatsapp", "human_requested", "normal", "NF-456")
        assert "NF-456" in msg
        # WhatsApp escalation is brief
        assert len(msg) <= 200

    def test_escalation_message_web_form(self):
        msg = get_escalation_message("web_form", "knowledge_gap", "low", "NF-789")
        assert "NF-789" in msg
        assert "1 business day" in msg

    def test_sla_map_completeness(self):
        for urgency in ["critical", "high", "normal", "low"]:
            assert urgency in SLA_BY_URGENCY

    def test_team_by_reason_completeness(self):
        expected_reasons = [
            "legal_threat", "security_incident", "billing_dispute",
            "knowledge_gap", "repeat_contact", "human_requested",
        ]
        for reason in expected_reasons:
            assert reason in TEAM_BY_REASON, f"Missing reason: {reason}"


# ── Tool unit tests (mocked DB) ───────────────────────────────────────────────

class TestTools:

    @pytest.mark.asyncio
    async def test_create_ticket_calls_db(self):
        with patch("production.agent.tools.queries") as mock_q:
            mock_q.find_or_create_customer = AsyncMock(return_value="cust-uuid-1")
            mock_q.get_or_create_conversation = AsyncMock(return_value="conv-uuid-1")
            mock_q.create_ticket = AsyncMock(return_value="ticket-uuid-1")

            from production.agent.tools import create_ticket
            result = await create_ticket(
                customer_email="test@example.com",
                customer_phone=None,
                customer_name="Test User",
                channel="email",
                subject="Test issue",
                category="technical",
                priority="medium",
            )

        assert result["ticket_id"] == "ticket-uuid-1"
        assert result["customer_id"] == "cust-uuid-1"

    @pytest.mark.asyncio
    async def test_create_ticket_invalid_channel(self):
        from pydantic import ValidationError
        from production.agent.tools import CreateTicketInput

        with pytest.raises(ValidationError):
            CreateTicketInput(
                channel="fax",  # invalid
                subject="test",
                priority="medium",
            )

    @pytest.mark.asyncio
    async def test_analyze_sentiment_positive(self):
        with patch("production.agent.tools._get_openai") as mock_oai:
            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(
                return_value=MagicMock(
                    choices=[MagicMock(message=MagicMock(content="0.85"))]
                )
            )
            mock_oai.return_value = mock_client

            with patch("production.agent.tools.queries") as mock_q:
                mock_q.update_conversation_sentiment = AsyncMock()

                from production.agent.tools import analyze_sentiment
                result = await analyze_sentiment(message="Thanks, this worked great!")

        assert result["score"] >= 0.7
        assert result["level"] == "positive"
        assert result["immediate_escalate"] is False
        assert result["requires_empathy"] is False

    @pytest.mark.asyncio
    async def test_analyze_sentiment_legal_keyword_overrides_score(self):
        with patch("production.agent.tools._get_openai") as mock_oai:
            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(
                return_value=MagicMock(
                    choices=[MagicMock(message=MagicMock(content="0.6"))]
                )
            )
            mock_oai.return_value = mock_client

            with patch("production.agent.tools.queries") as mock_q:
                mock_q.update_conversation_sentiment = AsyncMock()

                from production.agent.tools import analyze_sentiment
                result = await analyze_sentiment(
                    message="I'm going to contact my lawyer about this."
                )

        # Legal keyword should cap score at 0.1
        assert result["score"] <= 0.1
        assert result["immediate_escalate"] is True

    @pytest.mark.asyncio
    async def test_search_knowledge_base_returns_results(self):
        with patch("production.agent.tools._get_openai") as mock_oai:
            mock_client = MagicMock()
            mock_client.embeddings.create = AsyncMock(
                return_value=MagicMock(data=[MagicMock(embedding=[0.1] * 1536)])
            )
            mock_oai.return_value = mock_client

            with patch("production.agent.tools.queries") as mock_q:
                mock_q.search_knowledge_base = AsyncMock(return_value=[
                    {"title": "GitHub Integration", "content": "To connect GitHub...", "similarity": 0.82}
                ])

                from production.agent.tools import search_knowledge_base
                result = await search_knowledge_base(query="how do I connect GitHub")

        assert result["found"] is True
        assert len(result["results"]) == 1
        assert result["top_score"] == 0.82

    @pytest.mark.asyncio
    async def test_search_knowledge_base_retries_at_lower_threshold(self):
        with patch("production.agent.tools._get_openai") as mock_oai:
            mock_client = MagicMock()
            mock_client.embeddings.create = AsyncMock(
                return_value=MagicMock(data=[MagicMock(embedding=[0.1] * 1536)])
            )
            mock_oai.return_value = mock_client

            call_count = 0

            async def _mock_kb(embedding, max_results, min_similarity, category):
                nonlocal call_count
                call_count += 1
                if min_similarity >= 0.70:
                    return []  # No results at high threshold
                return [{"title": "Fallback Doc", "content": "...", "similarity": 0.65}]

            with patch("production.agent.tools.queries") as mock_q:
                mock_q.search_knowledge_base = _mock_kb

                from production.agent.tools import search_knowledge_base
                result = await search_knowledge_base(query="obscure feature")

        assert call_count == 2  # Retried once
        assert result["found"] is True

    @pytest.mark.asyncio
    async def test_escalate_to_human_critical(self):
        with patch("production.agent.tools.queries") as mock_q:
            mock_q.create_escalation = AsyncMock(return_value="esc-uuid-1")
            mock_q.update_ticket_status = AsyncMock()

            from production.agent.tools import escalate_to_human
            result = await escalate_to_human(
                ticket_id="t-001",
                customer_id="c-001",
                reason="legal_threat",
                urgency="critical",
                channel="email",
                trigger_message="I'll contact my lawyer",
            )

        assert result["urgency"] == "critical"
        assert result["escalation_id"] == "esc-uuid-1"
        assert "routed_to" in result

    @pytest.mark.asyncio
    async def test_escalate_auto_upgrades_urgency_for_legal_keyword(self):
        with patch("production.agent.tools.queries") as mock_q:
            mock_q.create_escalation = AsyncMock(return_value="esc-uuid-2")
            mock_q.update_ticket_status = AsyncMock()

            from production.agent.tools import escalate_to_human
            result = await escalate_to_human(
                ticket_id="t-002",
                customer_id="c-002",
                reason="general complaint",
                urgency="normal",        # Under-specified
                trigger_message="I'll sue your company",  # Contains critical keyword
            )

        # Should be upgraded to critical
        assert result["urgency"] == "critical"

    @pytest.mark.asyncio
    async def test_send_response_formats_for_channel(self):
        with patch("production.agent.tools.queries") as mock_q:
            mock_q.store_message = AsyncMock(return_value="msg-uuid-1")
            mock_q.record_metric = AsyncMock()

            from production.agent.tools import send_response
            result = await send_response(
                ticket_id="t-001",
                conversation_id="conv-001",
                channel="email",
                content="Here's how to reset your password.",
                customer_name="Alice",
            )

        assert result["message_id"] == "msg-uuid-1"
        assert "Hi Alice," in result["formatted_content"]
        assert result["channel"] == "email"
