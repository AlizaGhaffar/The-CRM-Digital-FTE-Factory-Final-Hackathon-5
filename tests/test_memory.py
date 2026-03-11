"""
Tests for src/agent/memory.py — Exercise 1.3 Conversation Memory
Covers all six memory features.

Run: pytest tests/test_memory.py -v
"""

import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.agent.memory import (
    MemoryStore,
    CustomerProfile,
    ConversationContext,
    MessageRecord,
    TicketRecord,
    ACTIVE_CONVERSATION_WINDOW_HOURS,
    SENTIMENT_TREND_THRESHOLD,
    _compute_sentiment_trend,
    _normalize_email,
    _normalize_phone,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fresh() -> MemoryStore:
    """Return a clean MemoryStore for each test."""
    return MemoryStore()


def _customer(store: MemoryStore, email="user@example.com", name="Test User",
              channel="email") -> CustomerProfile:
    return store.find_or_create_customer(email=email, name=name, channel=channel)


def _conv(store: MemoryStore, customer_id: str, channel="email") -> ConversationContext:
    return store.get_or_create_conversation(customer_id, channel)


# ---------------------------------------------------------------------------
# Feature 1: Track conversation context across messages
# ---------------------------------------------------------------------------

class TestConversationContext:

    def test_new_conversation_created(self):
        s = fresh()
        p = _customer(s)
        conv = _conv(s, p.customer_id)
        assert conv.conversation_id is not None
        assert conv.customer_id == p.customer_id
        assert conv.status == "active"

    def test_same_active_conversation_returned(self):
        s = fresh()
        p = _customer(s)
        conv1 = _conv(s, p.customer_id)
        conv2 = _conv(s, p.customer_id)
        assert conv1.conversation_id == conv2.conversation_id

    def test_message_added_to_conversation(self):
        s = fresh()
        p = _customer(s)
        conv = _conv(s, p.customer_id)
        msg = s.add_message(conv.conversation_id, "email", "inbound", "customer", "Hello")
        assert msg.message_id is not None
        assert conv.message_count == 1
        assert len(conv.messages) == 1
        assert conv.messages[0].content == "Hello"

    def test_agent_turns_counted_separately(self):
        s = fresh()
        p = _customer(s)
        conv = _conv(s, p.customer_id)
        s.add_message(conv.conversation_id, "email", "inbound", "customer", "Q")
        s.add_message(conv.conversation_id, "email", "outbound", "agent", "A")
        s.add_message(conv.conversation_id, "email", "outbound", "agent", "More")
        assert conv.message_count == 3
        assert conv.agent_turns == 2

    def test_conversation_history_returns_role_content(self):
        s = fresh()
        p = _customer(s)
        conv = _conv(s, p.customer_id)
        s.add_message(conv.conversation_id, "email", "inbound", "customer", "Hi there")
        s.add_message(conv.conversation_id, "email", "outbound", "agent", "Hello!")
        history = s.get_conversation_history(conv.conversation_id)
        assert history == [
            {"role": "customer", "content": "Hi there"},
            {"role": "agent", "content": "Hello!"},
        ]

    def test_history_limit_respected(self):
        s = fresh()
        p = _customer(s)
        conv = _conv(s, p.customer_id)
        for i in range(15):
            s.add_message(conv.conversation_id, "email", "inbound", "customer", f"msg {i}")
        history = s.get_conversation_history(conv.conversation_id, limit=5)
        assert len(history) == 5
        assert history[-1]["content"] == "msg 14"  # most recent last

    def test_close_conversation_sets_status(self):
        s = fresh()
        p = _customer(s)
        conv = _conv(s, p.customer_id)
        s.close_conversation(conv.conversation_id, "resolved", "self_service")
        assert conv.status == "resolved"
        assert conv.resolution_type == "self_service"
        assert conv.ended_at is not None

    def test_new_conversation_created_after_close(self):
        s = fresh()
        p = _customer(s)
        conv1 = _conv(s, p.customer_id)
        s.close_conversation(conv1.conversation_id, "resolved")
        # Mark as closed so the active check fails
        conv1.status = "resolved"
        conv2 = _conv(s, p.customer_id)
        assert conv2.conversation_id != conv1.conversation_id


# ---------------------------------------------------------------------------
# Feature 2: Handle channel switches
# ---------------------------------------------------------------------------

class TestChannelSwitches:

    def test_same_channel_no_switch(self):
        s = fresh()
        p = _customer(s)
        conv = _conv(s, p.customer_id, "email")
        _ = _conv(s, p.customer_id, "email")  # same channel again
        assert conv.channel_switches == []

    def test_channel_switch_recorded(self):
        s = fresh()
        p = _customer(s)
        conv = _conv(s, p.customer_id, "email")
        # Customer contacts again from WhatsApp
        conv2 = _conv(s, p.customer_id, "whatsapp")
        assert conv2.conversation_id == conv.conversation_id
        assert len(conv.channel_switches) == 1
        switch = conv.channel_switches[0]
        assert switch["from"] == "email"
        assert switch["to"] == "whatsapp"
        assert "switched_at" in switch

    def test_current_channel_updated_on_switch(self):
        s = fresh()
        p = _customer(s)
        conv = _conv(s, p.customer_id, "email")
        assert conv.current_channel == "email"
        _conv(s, p.customer_id, "whatsapp")
        assert conv.current_channel == "whatsapp"

    def test_initial_channel_preserved_on_switch(self):
        s = fresh()
        p = _customer(s)
        conv = _conv(s, p.customer_id, "web_form")
        _conv(s, p.customer_id, "email")
        _conv(s, p.customer_id, "whatsapp")
        assert conv.initial_channel == "web_form"
        assert len(conv.channel_switches) == 2

    def test_multiple_switches_all_recorded(self):
        s = fresh()
        p = _customer(s)
        _conv(s, p.customer_id, "email")
        conv = s.get_or_create_conversation(p.customer_id, "whatsapp")
        conv2 = s.get_or_create_conversation(p.customer_id, "web_form")
        assert len(conv.channel_switches) == 2
        assert conv.channel_switches[0]["from"] == "email"
        assert conv.channel_switches[1]["from"] == "whatsapp"


# ---------------------------------------------------------------------------
# Feature 3: Track sentiment per interaction
# ---------------------------------------------------------------------------

class TestSentimentTracking:

    def test_sentiment_updated_on_message(self):
        s = fresh()
        p = _customer(s)
        conv = _conv(s, p.customer_id)
        s.add_message(conv.conversation_id, "email", "inbound", "customer",
                      "This is terrible", sentiment_score=0.1)
        assert conv.sentiment_score == 0.1

    def test_sentiment_trend_improving(self):
        s = fresh()
        p = _customer(s)
        conv = _conv(s, p.customer_id)
        # Feed declining scores first
        for score in [0.2, 0.25, 0.3]:
            s.update_sentiment(conv.conversation_id, score)
        # Then a much better one
        trend = s.update_sentiment(conv.conversation_id, 0.7)
        assert trend == "improving"

    def test_sentiment_trend_declining(self):
        s = fresh()
        p = _customer(s)
        conv = _conv(s, p.customer_id)
        for score in [0.8, 0.75, 0.7]:
            s.update_sentiment(conv.conversation_id, score)
        trend = s.update_sentiment(conv.conversation_id, 0.2)
        assert trend == "declining"

    def test_sentiment_trend_stable(self):
        s = fresh()
        p = _customer(s)
        conv = _conv(s, p.customer_id)
        for score in [0.5, 0.52, 0.48]:
            s.update_sentiment(conv.conversation_id, score)
        trend = s.update_sentiment(conv.conversation_id, 0.51)
        assert trend == "stable"

    def test_sentiment_history_builds_per_interaction(self):
        s = fresh()
        p = _customer(s)
        conv = _conv(s, p.customer_id)
        scores = [0.3, 0.4, 0.5, 0.6]
        for score in scores:
            s.add_message(conv.conversation_id, "email", "inbound", "customer",
                          "msg", sentiment_score=score)
        assert len(conv._sentiment_history) == 4
        assert conv.sentiment_score == 0.6  # last score wins

    def test_no_sentiment_is_none(self):
        s = fresh()
        p = _customer(s)
        conv = _conv(s, p.customer_id)
        s.add_message(conv.conversation_id, "email", "inbound", "customer", "hi")
        assert conv.sentiment_score is None
        assert conv.sentiment_trend is None

    def test_compute_sentiment_trend_empty_history(self):
        trend = _compute_sentiment_trend([], 0.8)
        assert trend == "stable"


# ---------------------------------------------------------------------------
# Feature 4: Track topics discussed
# ---------------------------------------------------------------------------

class TestTopicTracking:

    def test_topic_added(self):
        s = fresh()
        p = _customer(s)
        conv = _conv(s, p.customer_id)
        s.add_topic(conv.conversation_id, "password reset")
        assert "password reset" in conv.topics

    def test_duplicate_topic_not_added(self):
        s = fresh()
        p = _customer(s)
        conv = _conv(s, p.customer_id)
        s.add_topic(conv.conversation_id, "billing")
        s.add_topic(conv.conversation_id, "BILLING")  # case-insensitive dedup
        assert len(conv.topics) == 1

    def test_multiple_topics_tracked(self):
        s = fresh()
        p = _customer(s)
        conv = _conv(s, p.customer_id)
        for topic in ["github integration", "webhook", "api rate limits"]:
            s.add_topic(conv.conversation_id, topic)
        assert len(conv.topics) == 3

    def test_topics_appear_in_agent_context(self):
        s = fresh()
        p = _customer(s)
        conv = _conv(s, p.customer_id)
        s.add_topic(conv.conversation_id, "sso saml")
        ctx = s.build_agent_context(p.customer_id)
        assert "sso saml" in ctx["conversation"]["topics"]

    def test_empty_topic_not_added(self):
        s = fresh()
        p = _customer(s)
        conv = _conv(s, p.customer_id)
        s.add_topic(conv.conversation_id, "")
        s.add_topic(conv.conversation_id, "   ")
        assert conv.topics == []


# ---------------------------------------------------------------------------
# Feature 5: Track resolution status
# ---------------------------------------------------------------------------

class TestResolutionStatus:

    def test_ticket_created_with_open_status(self):
        s = fresh()
        p = _customer(s)
        conv = _conv(s, p.customer_id)
        t = s.create_ticket(p.customer_id, conv.conversation_id, "email",
                            subject="Can't log in", category="technical")
        assert t.status == "open"
        assert t.resolved_at is None

    def test_ticket_resolved_sets_resolved_at(self):
        s = fresh()
        p = _customer(s)
        conv = _conv(s, p.customer_id)
        t = s.create_ticket(p.customer_id, conv.conversation_id, "email")
        s.update_ticket(t.ticket_id, "resolved", resolution_notes="Fixed")
        assert t.status == "resolved"
        assert t.resolved_at is not None
        assert t.resolution_notes == "Fixed"

    def test_escalation_fields_stored(self):
        s = fresh()
        p = _customer(s)
        conv = _conv(s, p.customer_id)
        t = s.create_ticket(p.customer_id, conv.conversation_id, "email")
        s.update_ticket(
            t.ticket_id, "escalated",
            escalation_reason="legal_threat",
            escalation_urgency="critical",
            escalated_to="legal@nimbusflow.io",
        )
        assert t.escalation_reason == "legal_threat"
        assert t.escalation_urgency == "critical"
        assert t.escalated_to == "legal@nimbusflow.io"

    def test_open_ticket_count_decremented_on_resolve(self):
        s = fresh()
        p = _customer(s)
        conv = _conv(s, p.customer_id)
        t = s.create_ticket(p.customer_id, conv.conversation_id, "email")
        assert p.open_tickets == 1
        s.update_ticket(t.ticket_id, "resolved")
        assert p.open_tickets == 0

    def test_lifetime_tickets_incremented_per_ticket(self):
        s = fresh()
        p = _customer(s)
        conv = _conv(s, p.customer_id)
        s.create_ticket(p.customer_id, conv.conversation_id, "email")
        s.create_ticket(p.customer_id, conv.conversation_id, "email")
        assert p.lifetime_tickets == 2

    def test_ticket_linked_to_conversation(self):
        s = fresh()
        p = _customer(s)
        conv = _conv(s, p.customer_id)
        t = s.create_ticket(p.customer_id, conv.conversation_id, "email",
                            ticket_id="NF-TEST01")
        assert "NF-TEST01" in conv.ticket_ids

    def test_conversation_close_sets_resolution_type(self):
        s = fresh()
        p = _customer(s)
        conv = _conv(s, p.customer_id)
        s.close_conversation(conv.conversation_id, "escalated", "escalated")
        assert conv.resolution_type == "escalated"

    def test_get_customer_tickets_sorted_by_recency(self):
        s = fresh()
        p = _customer(s)
        conv = _conv(s, p.customer_id)
        t1 = s.create_ticket(p.customer_id, conv.conversation_id, "email", ticket_id="NF-A01")
        t2 = s.create_ticket(p.customer_id, conv.conversation_id, "whatsapp", ticket_id="NF-A02")
        tickets = s.get_customer_tickets(p.customer_id)
        assert tickets[0].ticket_id == "NF-A02"


# ---------------------------------------------------------------------------
# Feature 6: Email as primary identifier / cross-channel identity
# ---------------------------------------------------------------------------

class TestCustomerIdentity:

    def test_email_is_primary_identifier(self):
        s = fresh()
        p = s.find_or_create_customer(email="alice@example.com", name="Alice", channel="email")
        assert p.email == "alice@example.com"
        assert "alice@example.com" in p.identifiers

    def test_same_email_returns_same_customer(self):
        s = fresh()
        p1 = s.find_or_create_customer(email="bob@example.com", channel="email")
        p2 = s.find_or_create_customer(email="BOB@EXAMPLE.COM", channel="whatsapp")
        assert p1.customer_id == p2.customer_id

    def test_phone_only_creates_customer(self):
        s = fresh()
        p = s.find_or_create_customer(phone="+14155551234", name="WA User", channel="whatsapp")
        assert p.phone == "+14155551234"
        assert p.customer_id is not None

    def test_email_and_phone_merged_into_one_record(self):
        # First contact via WhatsApp (phone only)
        s = fresh()
        p_wa = s.find_or_create_customer(phone="+14155559876", name="Carol", channel="whatsapp")
        # Later provides email via web form
        p_web = s.find_or_create_customer(
            email="carol@example.com", phone="+14155559876", name="Carol", channel="web_form"
        )
        assert p_wa.customer_id == p_web.customer_id
        assert p_web.email == "carol@example.com"

    def test_resolve_customer_id_by_email(self):
        s = fresh()
        p = s.find_or_create_customer(email="dave@example.com", channel="email")
        resolved = s.resolve_customer_id("dave@example.com")
        assert resolved == p.customer_id

    def test_resolve_customer_id_by_phone(self):
        s = fresh()
        p = s.find_or_create_customer(phone="+447700900456", channel="whatsapp")
        resolved = s.resolve_customer_id("+447700900456")
        assert resolved == p.customer_id

    def test_resolve_unknown_identifier_returns_none(self):
        s = fresh()
        assert s.resolve_customer_id("nobody@nowhere.com") is None

    def test_email_merged_when_phone_known_first(self):
        s = fresh()
        p1 = s.find_or_create_customer(phone="+15550001111", channel="whatsapp")
        p2 = s.find_or_create_customer(email="eve@example.com", phone="+15550001111", channel="email")
        assert p1.customer_id == p2.customer_id
        assert p2.email == "eve@example.com"
        # Both identifiers should resolve to same customer
        assert s.resolve_customer_id("+15550001111") == p1.customer_id
        assert s.resolve_customer_id("eve@example.com") == p1.customer_id

    def test_email_normalised_to_lowercase(self):
        s = fresh()
        p = s.find_or_create_customer(email="Frank@EXAMPLE.COM", channel="email")
        assert p.email == "frank@example.com"
        assert s.resolve_customer_id("frank@example.com") == p.customer_id

    def test_different_emails_different_customers(self):
        s = fresh()
        p1 = s.find_or_create_customer(email="a@example.com", channel="email")
        p2 = s.find_or_create_customer(email="b@example.com", channel="email")
        assert p1.customer_id != p2.customer_id

    def test_preferred_channel_set_on_creation(self):
        s = fresh()
        p = s.find_or_create_customer(email="g@example.com", channel="whatsapp")
        assert p.preferred_channel == "whatsapp"

    def test_last_channel_updated_on_ticket_creation(self):
        s = fresh()
        p = _customer(s, email="h@example.com")
        conv = _conv(s, p.customer_id, "whatsapp")
        s.create_ticket(p.customer_id, conv.conversation_id, "whatsapp")
        assert p.last_channel == "whatsapp"


# ---------------------------------------------------------------------------
# build_agent_context integration
# ---------------------------------------------------------------------------

class TestAgentContext:

    def test_unknown_customer_returns_not_found(self):
        s = fresh()
        ctx = s.build_agent_context("non-existent-id")
        assert ctx["found"] is False

    def test_context_includes_customer_profile(self):
        s = fresh()
        p = s.find_or_create_customer(email="iris@example.com", name="Iris", channel="email")
        ctx = s.build_agent_context(p.customer_id)
        assert ctx["found"] is True
        assert ctx["customer"]["email"] == "iris@example.com"
        assert ctx["customer"]["name"] == "Iris"

    def test_context_includes_conversation(self):
        s = fresh()
        p = _customer(s, email="jay@example.com")
        conv = _conv(s, p.customer_id)
        s.add_topic(conv.conversation_id, "billing")
        ctx = s.build_agent_context(p.customer_id)
        assert ctx["conversation"]["conversation_id"] == conv.conversation_id
        assert "billing" in ctx["conversation"]["topics"]

    def test_context_includes_channel_switch_history(self):
        s = fresh()
        p = _customer(s, email="kim@example.com")
        _conv(s, p.customer_id, "email")
        _conv(s, p.customer_id, "whatsapp")
        ctx = s.build_agent_context(p.customer_id)
        assert len(ctx["conversation"]["channel_switches"]) == 1

    def test_context_includes_recent_tickets(self):
        s = fresh()
        p = _customer(s, email="lee@example.com")
        conv = _conv(s, p.customer_id)
        s.create_ticket(p.customer_id, conv.conversation_id, "email",
                        subject="Password", category="general", ticket_id="NF-CTX01")
        ctx = s.build_agent_context(p.customer_id)
        assert any(t["ticket_id"] == "NF-CTX01" for t in ctx["recent_tickets"])

    def test_context_marks_repeat_contact(self):
        s = fresh()
        p = _customer(s, email="mo@example.com")
        conv = _conv(s, p.customer_id)
        s.create_ticket(p.customer_id, conv.conversation_id, "email")
        s.create_ticket(p.customer_id, conv.conversation_id, "email")
        ctx = s.build_agent_context(p.customer_id)
        assert ctx["is_repeat_contact"] is True

    def test_context_message_history_included(self):
        s = fresh()
        p = _customer(s, email="nan@example.com")
        conv = _conv(s, p.customer_id)
        s.add_message(conv.conversation_id, "email", "inbound", "customer", "Hello")
        s.add_message(conv.conversation_id, "email", "outbound", "agent", "Hi there!")
        ctx = s.build_agent_context(p.customer_id)
        assert len(ctx["message_history"]) == 2

    def test_context_sentiment_score_present(self):
        s = fresh()
        p = _customer(s, email="oz@example.com")
        conv = _conv(s, p.customer_id)
        s.add_message(conv.conversation_id, "email", "inbound", "customer",
                      "I'm frustrated", sentiment_score=0.2)
        ctx = s.build_agent_context(p.customer_id)
        assert ctx["conversation"]["sentiment_score"] == 0.2


# ---------------------------------------------------------------------------
# process_inbound integration
# ---------------------------------------------------------------------------

class TestProcessInbound:

    def test_creates_all_three_objects(self):
        s = fresh()
        profile, conv, ticket = s.process_inbound(
            email="pat@example.com", phone=None, name="Pat",
            channel="email", message_body="I need help", sentiment_score=0.5
        )
        assert isinstance(profile, CustomerProfile)
        assert isinstance(conv, ConversationContext)
        assert isinstance(ticket, TicketRecord)

    def test_supplied_ticket_id_used(self):
        s = fresh()
        _, _, t = s.process_inbound(
            email="q@example.com", phone=None, name="Q",
            channel="email", message_body="test", ticket_id="NF-SUPPLIED"
        )
        assert t.ticket_id == "NF-SUPPLIED"

    def test_inbound_message_stored_in_conversation(self):
        s = fresh()
        p, conv, _ = s.process_inbound(
            email="ray@example.com", phone=None, name="Ray",
            channel="email", message_body="How do I reset my password?"
        )
        assert conv.message_count == 1
        assert conv.messages[0].role == "customer"
        assert conv.messages[0].direction == "inbound"

    def test_repeat_inbound_reuses_conversation(self):
        s = fresh()
        _, conv1, _ = s.process_inbound(
            email="sue@example.com", phone=None, name="Sue",
            channel="email", message_body="First question"
        )
        _, conv2, _ = s.process_inbound(
            email="sue@example.com", phone=None, name="Sue",
            channel="email", message_body="Follow-up question"
        )
        assert conv1.conversation_id == conv2.conversation_id
        assert conv1.message_count == 2

    def test_channel_switch_via_process_inbound(self):
        s = fresh()
        _, conv1, _ = s.process_inbound(
            email="tom@example.com", phone=None, name="Tom",
            channel="email", message_body="Email question"
        )
        # Same customer, different channel
        p, conv2, _ = s.process_inbound(
            email="tom@example.com", phone=None, name="Tom",
            channel="whatsapp", message_body="whatsapp follow-up"
        )
        assert conv1.conversation_id == conv2.conversation_id
        assert len(conv1.channel_switches) == 1
        assert conv1.current_channel == "whatsapp"
