"""
Tests for src/agent/core.py — Exercise 1.2 Core Agent Loop
Covers all six pipeline steps using sample-tickets.json.

Run: pytest tests/test_core.py -v
"""

import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.agent.core import (
    normalize_message,
    search_docs,
    check_escalation,
    score_sentiment,
    format_for_channel,
    generate_response,
    run_core_loop,
    Channel,
    Urgency,
    InboundMessage,
    AgentResponse,
    EscalationDecision,
    SAMPLE_TICKETS_PATH,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _email_payload(content: str, name: str = "Test User", subject: str = "") -> dict:
    return {"customer_email": "user@example.com", "customer_name": name,
            "subject": subject, "content": content}


def _whatsapp_payload(content: str, name: str = "WA User") -> dict:
    return {"customer_phone": "+15551234567", "customer_name": name, "content": content}


def _webform_payload(message: str, name: str = "WF User", subject: str = "") -> dict:
    return {"customer_email": "wf@example.com", "customer_name": name,
            "subject": subject, "message": message}


def _load_sample_tickets() -> list[dict]:
    return json.loads(SAMPLE_TICKETS_PATH.read_text(encoding="utf-8"))["tickets"]


# ---------------------------------------------------------------------------
# Step 1+2: normalize_message
# ---------------------------------------------------------------------------

class TestNormalizeMessage:

    def test_email_fields_extracted(self):
        payload = {"customer_email": "a@b.com", "customer_name": "Alice",
                   "subject": "Help", "content": "I need help"}
        msg = normalize_message(payload, Channel.EMAIL)
        assert msg.customer_id == "a@b.com"
        assert msg.customer_name == "Alice"
        assert msg.body == "I need help"
        assert msg.subject == "Help"
        assert msg.channel == Channel.EMAIL

    def test_whatsapp_fields_extracted(self):
        payload = {"customer_phone": "+15550001111", "customer_name": "Bob",
                   "content": "hi how do i reset password"}
        msg = normalize_message(payload, "whatsapp")
        assert msg.customer_id == "+15550001111"
        assert msg.channel == Channel.WHATSAPP
        assert "reset" in msg.body

    def test_web_form_uses_message_key(self):
        payload = {"customer_email": "c@d.com", "customer_name": "Carol",
                   "subject": "Webhook", "message": "Webhook not firing"}
        msg = normalize_message(payload, Channel.WEB_FORM)
        assert msg.body == "Webhook not firing"
        assert msg.subject == "Webhook"

    def test_body_whitespace_normalized(self):
        payload = {"customer_email": "x@y.com", "customer_name": "X",
                   "content": "  too   many    spaces  "}
        msg = normalize_message(payload, Channel.EMAIL)
        assert msg.body == "too many spaces"

    def test_ticket_id_generated(self):
        msg = normalize_message(_email_payload("hi"), Channel.EMAIL)
        assert msg.ticket_id.startswith("NF-")
        assert len(msg.ticket_id) == 11  # NF- + 8 hex chars

    def test_empty_body_results_in_empty_string(self):
        payload = {"customer_email": "e@f.com", "customer_name": "Eve",
                   "content": ""}
        msg = normalize_message(payload, Channel.EMAIL)
        assert msg.body == ""

    def test_missing_name_defaults_to_empty(self):
        payload = {"customer_email": "anon@x.com", "content": "hello"}
        msg = normalize_message(payload, Channel.EMAIL)
        assert msg.customer_name == ""

    def test_string_channel_accepted(self):
        msg = normalize_message(_whatsapp_payload("test"), "whatsapp")
        assert msg.channel == Channel.WHATSAPP


# ---------------------------------------------------------------------------
# Step 3: search_docs
# ---------------------------------------------------------------------------

class TestSearchDocs:

    def test_password_reset_returns_results(self):
        results = search_docs("reset password")
        assert len(results) > 0

    def test_github_integration_returns_results(self):
        results = search_docs("GitHub integration webhook")
        assert len(results) > 0

    def test_api_rate_limits_returns_results(self):
        results = search_docs("API rate limits 429")
        assert len(results) > 0

    def test_billing_plans_returns_results(self):
        results = search_docs("billing plan upgrade")
        assert len(results) > 0

    def test_sso_saml_returns_results(self):
        results = search_docs("SSO SAML Okta")
        assert len(results) > 0

    def test_nonexistent_query_returns_empty(self):
        results = search_docs("xyznonexistentfeature99999")
        assert results == []

    def test_max_results_respected(self):
        results = search_docs("settings", max_results=2)
        assert len(results) <= 2

    def test_results_sorted_by_relevance(self):
        results = search_docs("mobile app sync")
        if len(results) >= 2:
            assert results[0].relevance_score >= results[1].relevance_score

    def test_title_match_scores_higher_than_body(self):
        """A query matching a section title should rank highly."""
        results = search_docs("Integrations")
        assert len(results) > 0
        # The "Integrations" section should appear near the top
        titles = [r.title for r in results]
        assert any("Integrations" in t or "Integration" in t for t in titles[:3])


# ---------------------------------------------------------------------------
# Sentiment scoring
# ---------------------------------------------------------------------------

class TestScoreSentiment:

    def test_neutral_baseline(self):
        score = score_sentiment("how do i reset my password")
        assert 0.3 <= score <= 0.7

    def test_positive_message(self):
        score = score_sentiment("Love NimbusFlow, quick question about dark mode")
        assert score > 0.6

    def test_negative_message(self):
        score = score_sentiment("this is terrible and broken")
        assert score < 0.45

    def test_very_negative_caps(self):
        score = score_sentiment("THIS IS ABSOLUTELY UNACCEPTABLE YOUR SERVICE IS TERRIBLE")
        assert score < 0.25

    def test_legal_threat_very_negative(self):
        score = score_sentiment("I will sue you if this isn't fixed")
        assert score < 0.3

    def test_score_bounded(self):
        score = score_sentiment("hate awful terrible disgusting lawsuit chargeback !!!")
        assert 0.0 <= score <= 1.0

    def test_all_caps_penalized(self):
        normal = score_sentiment("i need help with login")
        caps = score_sentiment("I NEED HELP WITH LOGIN")
        assert caps < normal


# ---------------------------------------------------------------------------
# Step 6: check_escalation
# ---------------------------------------------------------------------------

class TestCheckEscalation:

    def _msg(self, body: str, subject: str = "", channel: Channel = Channel.EMAIL) -> InboundMessage:
        payload = {"customer_email": "t@t.com", "customer_name": "T",
                   "subject": subject, "content": body}
        return normalize_message(payload, channel)

    def test_legal_threat_triggers_critical(self):
        decision = check_escalation(self._msg("I will sue your company"), 0.2)
        assert decision is not None
        assert decision.reason == "legal_threat"
        assert decision.urgency == Urgency.CRITICAL

    def test_security_incident_triggers_critical(self):
        decision = check_escalation(
            self._msg("We believe there has been unauthorized access to our data"), 0.3
        )
        assert decision is not None
        assert decision.reason == "security_incident"
        assert decision.urgency == Urgency.CRITICAL

    def test_chargeback_triggers_critical(self):
        decision = check_escalation(
            self._msg("I'll dispute the charge with my bank"), 0.4
        )
        assert decision is not None
        assert decision.reason == "chargeback_threat"

    def test_data_loss_triggers_critical(self):
        decision = check_escalation(self._msg("my tasks disappeared from the sprint"), 0.3)
        assert decision is not None
        assert decision.reason == "data_loss_reported"

    def test_refund_request_triggers_high(self):
        decision = check_escalation(self._msg("I want a full refund please"), 0.5)
        assert decision is not None
        assert decision.reason == "refund_request"
        assert decision.urgency == Urgency.HIGH

    def test_human_request_triggers(self):
        decision = check_escalation(self._msg("I want to speak to a real person"), 0.5)
        assert decision is not None
        assert decision.reason == "explicit_human_request"

    def test_very_low_sentiment_triggers(self):
        decision = check_escalation(self._msg("I need help"), 0.1)
        assert decision is not None
        assert decision.reason == "extreme_negative_sentiment"

    def test_normal_question_no_escalation(self):
        decision = check_escalation(self._msg("how do I reset my password"), 0.7)
        assert decision is None

    def test_subject_line_triggers_escalation(self):
        """Escalation keywords in subject should be detected."""
        msg = self._msg("Please respond urgently", subject="LEGAL NOTICE — Data breach")
        decision = check_escalation(msg, 0.5)
        assert decision is not None


# ---------------------------------------------------------------------------
# Step 5: format_for_channel
# ---------------------------------------------------------------------------

class TestFormatForChannel:

    def test_email_includes_greeting(self):
        out = format_for_channel("Here is the answer.", Channel.EMAIL, "Alice", "NF-TEST01")
        assert "Hi Alice," in out

    def test_email_includes_sign_off(self):
        out = format_for_channel("Answer.", Channel.EMAIL, "Bob", "NF-TEST02")
        assert "NimbusFlow Support" in out

    def test_email_includes_ticket_reference(self):
        out = format_for_channel("Answer.", Channel.EMAIL, "Carol", "NF-TEST03")
        assert "NF-TEST03" in out

    def test_whatsapp_strips_markdown(self):
        out = format_for_channel("**Bold** and _italic_.", Channel.WHATSAPP, "", "NF-TEST04")
        assert "*" not in out
        assert "_" not in out

    def test_whatsapp_under_300_chars(self):
        long_text = "word " * 100
        out = format_for_channel(long_text, Channel.WHATSAPP, "", "NF-TEST05")
        # Response text portion should be truncated
        assert len(out) < 400

    def test_whatsapp_includes_ref(self):
        out = format_for_channel("Go here.", Channel.WHATSAPP, "", "NF-TEST06")
        assert "NF-TEST06" in out

    def test_web_form_includes_closing(self):
        out = format_for_channel("Answer.", Channel.WEB_FORM, "Dave", "NF-TEST07")
        assert "Hope that helps" in out or "Ticket" in out

    def test_escalation_email_includes_sla(self):
        esc = EscalationDecision("legal_threat", Urgency.CRITICAL, "legal@nimbusflow.io")
        out = format_for_channel("", Channel.EMAIL, "Eve", "NF-TEST08", escalation=esc)
        assert "2 hours" in out
        assert "NF-TEST08" in out

    def test_escalation_whatsapp_is_short(self):
        esc = EscalationDecision("refund_request", Urgency.HIGH, "billing@nimbusflow.io")
        out = format_for_channel("", Channel.WHATSAPP, "", "NF-TEST09", escalation=esc)
        assert len(out) < 300

    def test_email_max_length_enforced(self):
        long_text = "x" * 3000
        out = format_for_channel(long_text, Channel.EMAIL, "Long", "NF-LONG")
        # The text portion is capped; total will be longer due to greeting etc.
        assert "..." in out


# ---------------------------------------------------------------------------
# Core loop integration tests
# ---------------------------------------------------------------------------

class TestRunCoreLoop:

    def test_ticket_id_always_present(self):
        result = run_core_loop(_email_payload("help"), Channel.EMAIL)
        assert result.ticket_id.startswith("NF-")

    def test_empty_body_returns_clarification(self):
        result = run_core_loop(_email_payload(""), Channel.EMAIL)
        assert result.escalation is None
        assert "empty" in result.formatted_response.lower() or \
               "tell me" in result.formatted_response.lower() or \
               "what" in result.formatted_response.lower()

    def test_legal_threat_escalates(self):
        result = run_core_loop(
            _email_payload("I will sue your company for this"), Channel.EMAIL
        )
        assert result.escalation is not None
        assert result.escalation.reason == "legal_threat"

    def test_refund_request_escalates(self):
        result = run_core_loop(
            _email_payload("I want a full refund for my annual plan"), Channel.EMAIL
        )
        assert result.escalation is not None
        assert result.escalation.reason == "refund_request"

    def test_human_request_escalates(self):
        result = run_core_loop(
            _email_payload("I want to talk to a real person right now"), Channel.EMAIL
        )
        assert result.escalation is not None
        assert result.escalation.reason == "explicit_human_request"

    def test_data_loss_escalates(self):
        result = run_core_loop(
            _email_payload("Tasks disappeared from our sprint"), Channel.EMAIL
        )
        assert result.escalation is not None
        assert "data_loss" in result.escalation.reason

    def test_password_reset_resolves(self):
        result = run_core_loop(
            _email_payload("how do I reset my password"), Channel.EMAIL
        )
        assert result.escalation is None
        assert len(result.formatted_response) > 0

    def test_api_rate_limit_resolves(self):
        result = run_core_loop(
            _whatsapp_payload("getting 429 errors, what are growth plan rate limits"),
            Channel.WHATSAPP,
        )
        assert result.escalation is None
        assert result.formatted_response

    def test_sentiment_score_in_result(self):
        result = run_core_loop(_email_payload("I'm frustrated"), Channel.EMAIL)
        assert 0.0 <= result.sentiment_score <= 1.0

    def test_kb_sections_populated_on_resolve(self):
        result = run_core_loop(
            _email_payload("how do I set up GitHub integration"), Channel.EMAIL
        )
        if not result.escalation:
            assert len(result.kb_sections_used) > 0

    def test_whatsapp_response_shorter_than_email(self):
        wa = run_core_loop(_whatsapp_payload("how do I add team members"), Channel.WHATSAPP)
        em = run_core_loop(_email_payload("how do I add team members"), Channel.EMAIL)
        if not wa.escalation and not em.escalation:
            assert len(wa.formatted_response) < len(em.formatted_response)

    def test_processing_steps_recorded(self):
        result = run_core_loop(_email_payload("how do I reset my password"), Channel.EMAIL)
        assert len(result.processing_steps) >= 2

    def test_web_form_payload_works(self):
        result = run_core_loop(_webform_payload("GitHub webhook not firing"), Channel.WEB_FORM)
        assert result.ticket_id
        assert result.formatted_response


# ---------------------------------------------------------------------------
# Sample tickets end-to-end (subset, key edge cases)
# ---------------------------------------------------------------------------

class TestSampleTickets:
    """
    Runs a representative subset of sample-tickets.json through run_core_loop
    and verifies the expected_action matches actual behaviour.
    """

    CRITICAL_IDS = {
        # These must escalate per expected_action in sample-tickets.json
        "T-004",  # refund > $500
        "T-007",  # explicit human + chargeback
        "T-011",  # legal + security
        "T-019",  # data loss
        "T-029",  # security incident
        "T-041",  # extreme negative + data loss
        "T-051",  # repeat contact extreme negative
    }

    MUST_RESOLVE_IDS = {
        # These must NOT escalate
        "T-002",  # password reset (whatsapp)
        "T-005",  # API rate limits (whatsapp)
        "T-008",  # add team members (whatsapp)
        "T-020",  # download iOS app (whatsapp)
        "T-032",  # subtasks design (email)
    }

    def _get_ticket(self, ticket_id: str) -> dict:
        tickets = _load_sample_tickets()
        for t in tickets:
            if t["id"] == ticket_id:
                return t
        raise KeyError(f"Ticket {ticket_id} not found")

    def test_critical_tickets_escalate(self):
        """All tickets marked as must-escalate should trigger escalation."""
        failed = []
        for tid in self.CRITICAL_IDS:
            ticket = self._get_ticket(tid)
            result = run_core_loop(ticket, Channel(ticket["channel"]))
            if result.escalation is None:
                failed.append(tid)
        assert failed == [], f"Expected escalation but got resolve for: {failed}"

    def test_simple_tickets_resolve(self):
        """Simple FAQ tickets should resolve without escalation."""
        failed = []
        for tid in self.MUST_RESOLVE_IDS:
            ticket = self._get_ticket(tid)
            result = run_core_loop(ticket, Channel(ticket["channel"]))
            if result.escalation is not None:
                failed.append(f"{tid} ({result.escalation.reason})")
        assert failed == [], f"Unexpected escalation for: {failed}"

    def test_t001_account_locked(self):
        """T-001: account locked — should resolve with unlock info."""
        ticket = self._get_ticket("T-001")
        result = run_core_loop(ticket, Channel.EMAIL)
        # Account locked is resolvable from docs; should not hard-escalate
        # (sentiment is 0.25, just above very_negative threshold of 0.2)
        assert result.formatted_response

    def test_t003_github_webhook_resolves(self):
        ticket = self._get_ticket("T-003")
        result = run_core_loop(ticket, Channel.WEB_FORM)
        assert result.escalation is None or result.escalation.reason == "knowledge_gap"

    def test_t015_pricing_question_resolves(self):
        """T-015: pricing comparison WhatsApp — should resolve."""
        ticket = self._get_ticket("T-015")
        result = run_core_loop(ticket, Channel.WHATSAPP)
        assert result.escalation is None

    def test_t046_empty_ticket_handled(self):
        """T-046: empty content edge case."""
        ticket = self._get_ticket("T-046")
        result = run_core_loop(ticket, Channel.EMAIL)
        assert result.formatted_response
        assert result.escalation is None

    def test_all_tickets_produce_response(self):
        """Every ticket should produce a non-empty formatted_response."""
        tickets = _load_sample_tickets()
        for ticket in tickets:
            result = run_core_loop(ticket, Channel(ticket["channel"]))
            assert result.formatted_response, f"Empty response for {ticket['id']}"
            assert result.ticket_id.startswith("NF-")
