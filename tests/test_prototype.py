"""
Prototype Tests — NimbusFlow Customer Success FTE
Tests for incubation phase prototype (src/agent/prototype.py)

Run: pytest tests/test_prototype.py -v
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.agent.prototype import (
    run_agent,
    analyze_sentiment,
    search_knowledge_base,
    check_escalation_triggers,
    Channel,
    SentimentLevel
)


# ── Sentiment Tests ────────────────────────────────────────────────────────
class TestSentimentAnalysis:

    def test_very_negative_angry_message(self):
        score, level = analyze_sentiment("This is RIDICULOUS! Your product is BROKEN!")
        assert score < 0.3
        assert level == SentimentLevel.VERY_NEGATIVE

    def test_legal_threat_very_negative(self):
        score, level = analyze_sentiment("I will sue you if this isn't resolved")
        assert score < 0.3

    def test_neutral_simple_question(self):
        score, level = analyze_sentiment("how do i reset my password")
        assert 0.3 <= score <= 0.7

    def test_positive_message(self):
        score, level = analyze_sentiment("Love NimbusFlow! Quick question about dark mode")
        assert score > 0.6
        assert level in [SentimentLevel.POSITIVE, SentimentLevel.VERY_POSITIVE]

    def test_all_caps_penalized(self):
        normal_score, _ = analyze_sentiment("i need help with login")
        caps_score, _ = analyze_sentiment("I NEED HELP WITH LOGIN")
        assert caps_score < normal_score

    def test_score_bounds(self):
        score, _ = analyze_sentiment("I hate this terrible awful disgusting scam lawsuit sue lawyer!!!")
        assert 0.0 <= score <= 1.0


# ── Escalation Tests ───────────────────────────────────────────────────────
class TestEscalationTriggers:

    def test_legal_threat_escalates(self):
        result = check_escalation_triggers("I'm going to sue you", 0.1)
        assert result is not None
        reason, urgency = result
        assert reason == "legal_threat"
        assert urgency == "critical"

    def test_refund_request_escalates(self):
        result = check_escalation_triggers("I want a refund", 0.5)
        assert result is not None
        reason, urgency = result
        assert reason == "refund_request"
        assert urgency == "high"

    def test_explicit_human_request_escalates(self):
        result = check_escalation_triggers("I want to speak to a human", 0.5)
        assert result is not None
        reason, urgency = result
        assert reason == "explicit_human_request"

    def test_chargeback_threat_escalates(self):
        result = check_escalation_triggers("I'll dispute the charge with my bank", 0.3)
        assert result is not None
        reason, urgency = result
        assert reason == "chargeback_threat"
        assert urgency == "critical"

    def test_very_low_sentiment_escalates(self):
        result = check_escalation_triggers("I need some help", 0.05)
        assert result is not None
        reason, urgency = result
        assert reason == "extreme_negative_sentiment"

    def test_normal_question_no_escalation(self):
        result = check_escalation_triggers("how do I reset my password", 0.7)
        assert result is None

    def test_data_loss_escalates(self):
        result = check_escalation_triggers("my tasks disappeared", 0.3)
        assert result is not None
        assert "data_loss" in result[0]


# ── Knowledge Base Tests ───────────────────────────────────────────────────
class TestKnowledgeSearch:

    def test_password_reset_returns_results(self):
        results = search_knowledge_base("reset password")
        assert len(results) > 0

    def test_api_rate_limits_returns_results(self):
        results = search_knowledge_base("API rate limits")
        assert len(results) > 0

    def test_nonexistent_query_returns_empty(self):
        results = search_knowledge_base("xyznonexistentfeature12345")
        assert len(results) == 0

    def test_max_results_respected(self):
        results = search_knowledge_base("settings", max_results=3)
        assert len(results) <= 3

    def test_github_integration_returns_results(self):
        results = search_knowledge_base("GitHub integration webhook")
        assert len(results) > 0


# ── Agent Core Loop Tests ──────────────────────────────────────────────────
class TestAgentCoreLoop:

    def test_empty_message_handled(self):
        result = run_agent(
            message="",
            channel=Channel.EMAIL,
            customer_id="test@example.com"
        )
        assert result["response"] is not None
        assert result["escalated"] is False
        assert "empty" in result["response"].lower() or "describe" in result["response"].lower()

    def test_legal_threat_escalates(self):
        result = run_agent(
            message="I will sue your company for data loss",
            channel=Channel.EMAIL,
            customer_id="legal@example.com"
        )
        assert result["escalated"] is True
        assert result["escalation_reason"] == "legal_threat"

    def test_refund_request_escalates(self):
        result = run_agent(
            message="I want a full refund for my annual subscription",
            channel=Channel.EMAIL,
            customer_id="refund@example.com"
        )
        assert result["escalated"] is True
        assert result["escalation_reason"] == "refund_request"

    def test_password_question_resolved(self):
        result = run_agent(
            message="how do I reset my password",
            channel=Channel.EMAIL,
            customer_id="user@example.com"
        )
        assert result["escalated"] is False
        assert result["response"] is not None
        assert len(result["response"]) > 0

    def test_ticket_always_created(self):
        result = run_agent(
            message="quick question about billing",
            channel=Channel.WEB_FORM,
            customer_id="user@example.com"
        )
        assert result["ticket_id"] is not None
        assert result["ticket_id"].startswith("NF-")

    def test_email_response_has_greeting(self):
        result = run_agent(
            message="how do I add team members",
            channel=Channel.EMAIL,
            customer_id="user@example.com",
            customer_name="Alice"
        )
        assert result["escalated"] is False
        assert "Alice" in result["response"] or "Hi" in result["response"]

    def test_whatsapp_response_is_shorter(self):
        email_result = run_agent(
            message="how do I set up GitHub integration",
            channel=Channel.EMAIL,
            customer_id="user_email@example.com"
        )
        whatsapp_result = run_agent(
            message="how do I set up GitHub integration",
            channel=Channel.WHATSAPP,
            customer_id="user_wa@example.com"
        )
        # WhatsApp should be shorter
        if not whatsapp_result["escalated"] and not email_result["escalated"]:
            assert len(whatsapp_result["response"]) < len(email_result["response"])

    def test_sentiment_score_returned(self):
        result = run_agent(
            message="I'm frustrated with this product",
            channel=Channel.EMAIL,
            customer_id="frustrated@example.com"
        )
        assert result["sentiment_score"] is not None
        assert 0.0 <= result["sentiment_score"] <= 1.0


# ── Channel Format Tests ───────────────────────────────────────────────────
class TestChannelFormatting:

    def test_whatsapp_response_within_limit(self):
        result = run_agent(
            message="explain all the features of the API",
            channel=Channel.WHATSAPP,
            customer_id="wa_test@example.com"
        )
        # WhatsApp limit: 1600 chars
        assert len(result["response"]) <= 1600

    def test_email_includes_ticket_reference(self):
        result = run_agent(
            message="password reset help",
            channel=Channel.EMAIL,
            customer_id="email_test@example.com"
        )
        if not result["escalated"]:
            assert result["ticket_id"] in result["response"]
