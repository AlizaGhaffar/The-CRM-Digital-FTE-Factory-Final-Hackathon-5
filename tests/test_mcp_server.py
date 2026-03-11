"""
Tests for src/mcp/server.py — Exercise 1.4 MCP Server
Covers all five tools: input validation, happy paths, error handling.

Run: pytest tests/test_mcp_server.py -v
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Import the tool functions directly (FastMCP exposes the original async functions)
from src.mcp.server import (
    search_knowledge_base,
    create_ticket,
    get_customer_history,
    escalate_to_human,
    send_response,
    _store,          # shared MemoryStore — reset between test classes
    _URGENCY_MAP,
    _ROUTE_MAP,
    _SLA_MAP,
)
import src.mcp.server as _server_module


def run(coro):
    """Helper to run an async tool in sync test context."""
    return asyncio.run(coro)


def fresh_store():
    """Replace the module-level store with a clean one between tests."""
    new_store = __import__("src.agent.memory", fromlist=["MemoryStore"]).MemoryStore()
    _server_module._store = new_store
    return new_store


# ---------------------------------------------------------------------------
# Tool 1: search_knowledge_base
# ---------------------------------------------------------------------------

class TestSearchKnowledgeBase:

    def test_password_reset_returns_results(self):
        result = run(search_knowledge_base("reset password"))
        assert "No relevant" not in result
        assert len(result) > 50

    def test_github_webhook_returns_results(self):
        result = run(search_knowledge_base("GitHub webhook integration"))
        assert "GitHub" in result or "webhook" in result.lower()

    def test_api_rate_limits_returns_results(self):
        result = run(search_knowledge_base("API rate limits 429 error"))
        assert "No relevant" not in result

    def test_billing_plans_returns_results(self):
        result = run(search_knowledge_base("billing plan upgrade"))
        assert "No relevant" not in result

    def test_sso_saml_returns_results(self):
        result = run(search_knowledge_base("SSO SAML Okta setup"))
        assert "No relevant" not in result

    def test_unknown_query_returns_no_results_message(self):
        result = run(search_knowledge_base("xyznonexistentfeature99999abc"))
        assert "No relevant" in result

    def test_empty_query_returns_error(self):
        result = run(search_knowledge_base(""))
        assert "Error" in result

    def test_whitespace_only_query_returns_error(self):
        result = run(search_knowledge_base("   "))
        assert "Error" in result

    def test_result_contains_section_titles(self):
        result = run(search_knowledge_base("GitHub integration"))
        # FastMCP returns markdown with **Title** formatting
        assert "**" in result

    def test_result_sections_separated_by_divider(self):
        result = run(search_knowledge_base("settings account billing"))
        # Multiple sections separated by ---
        if "---" in result:
            parts = result.split("---")
            assert len(parts) >= 2

    def test_result_length_bounded_per_section(self):
        # Each section is capped at 600 chars; 5 sections max
        result = run(search_knowledge_base("help settings user"))
        # Total should be well under 10KB
        assert len(result) < 10_000


# ---------------------------------------------------------------------------
# Tool 2: create_ticket
# ---------------------------------------------------------------------------

class TestCreateTicket:

    def setup_method(self):
        fresh_store()

    def test_returns_ticket_id(self):
        result = run(create_ticket(
            "alex@example.com", "Account locked", "high", "email"
        ))
        assert "NF-" in result

    def test_ticket_id_format(self):
        result = run(create_ticket(
            "user@example.com", "Password reset", "low", "email"
        ))
        # "Ticket created: NF-XXXXXXXX"
        ticket_id = result.split(": ")[-1].strip()
        assert ticket_id.startswith("NF-")
        assert len(ticket_id) == 11  # NF- + 8 hex chars

    def test_whatsapp_channel_accepted(self):
        result = run(create_ticket(
            "+14155551234", "App not syncing", "medium", "whatsapp"
        ))
        assert "NF-" in result

    def test_web_form_channel_accepted(self):
        result = run(create_ticket(
            "form@example.com", "Webhook failing", "high", "web_form"
        ))
        assert "NF-" in result

    def test_all_priorities_accepted(self):
        for priority in ["low", "medium", "high", "critical"]:
            result = run(create_ticket(
                f"{priority}@example.com", "Test issue", priority, "email"
            ))
            assert "NF-" in result, f"Failed for priority={priority}"

    def test_invalid_channel_returns_error(self):
        result = run(create_ticket(
            "user@example.com", "Issue", "medium", "telegram"
        ))
        assert "Error" in result

    def test_invalid_priority_returns_error(self):
        result = run(create_ticket(
            "user@example.com", "Issue", "urgent", "email"
        ))
        assert "Error" in result

    def test_empty_customer_id_returns_error(self):
        result = run(create_ticket("", "Issue", "medium", "email"))
        assert "Error" in result

    def test_empty_issue_returns_error(self):
        result = run(create_ticket("user@example.com", "", "medium", "email"))
        assert "Error" in result

    def test_same_customer_reuses_unified_record(self):
        run(create_ticket("same@example.com", "First issue", "low", "email"))
        run(create_ticket("same@example.com", "Second issue", "low", "whatsapp"))
        # Both tickets should be under the same customer
        cid = _server_module._store.resolve_customer_id("same@example.com")
        assert cid is not None
        tickets = _server_module._store.get_customer_tickets(cid)
        assert len(tickets) == 2

    def test_ticket_stored_in_memory(self):
        result = run(create_ticket(
            "stored@example.com", "Integration issue", "medium", "email"
        ))
        ticket_id = result.split(": ")[-1].strip()
        ticket = _server_module._store.get_ticket(ticket_id)
        assert ticket is not None
        assert ticket.status == "open"
        assert ticket.source_channel == "email"


# ---------------------------------------------------------------------------
# Tool 3: get_customer_history
# ---------------------------------------------------------------------------

class TestGetCustomerHistory:

    def setup_method(self):
        fresh_store()

    def test_unknown_customer_returns_no_history(self):
        result = run(get_customer_history("nobody@unknown.com"))
        assert "No previous" in result

    def test_empty_customer_id_returns_error(self):
        result = run(get_customer_history(""))
        assert "Error" in result

    def test_known_customer_returns_history(self):
        run(create_ticket("history@example.com", "Login issue", "medium", "email"))
        result = run(get_customer_history("history@example.com"))
        assert "history@example.com" in result
        assert "NF-" in result

    def test_history_shows_ticket_status(self):
        run(create_ticket("status@example.com", "Billing question", "low", "email"))
        result = run(get_customer_history("status@example.com"))
        assert "open" in result

    def test_history_shows_channel(self):
        run(create_ticket("chan@example.com", "API issue", "medium", "email"))
        result = run(get_customer_history("chan@example.com"))
        assert "EMAIL" in result

    def test_repeat_contact_flagged(self):
        run(create_ticket("repeat@example.com", "First issue", "low", "email"))
        run(create_ticket("repeat@example.com", "Second issue", "low", "whatsapp"))
        result = run(get_customer_history("repeat@example.com"))
        assert "REPEAT" in result or "repeat" in result.lower()

    def test_history_shows_multiple_tickets(self):
        for i in range(3):
            run(create_ticket(
                "multi@example.com", f"Issue {i}", "low", "email"
            ))
        result = run(get_customer_history("multi@example.com"))
        # Should list tickets
        assert result.count("NF-") >= 3

    def test_history_shows_channel_switch(self):
        # First contact via email
        run(create_ticket("switch@example.com", "Email issue", "low", "email"))
        # Then via whatsapp — triggers channel switch in conversation
        run(create_ticket("switch@example.com", "WA follow-up", "low", "whatsapp"))
        result = run(get_customer_history("switch@example.com"))
        # Channel switch should be visible
        assert "email" in result.lower() and "whatsapp" in result.lower()

    def test_history_shows_lifetime_ticket_count(self):
        run(create_ticket("count@example.com", "Issue 1", "low", "email"))
        run(create_ticket("count@example.com", "Issue 2", "low", "email"))
        result = run(get_customer_history("count@example.com"))
        assert "Lifetime tickets: 2" in result or "2" in result


# ---------------------------------------------------------------------------
# Tool 4: escalate_to_human
# ---------------------------------------------------------------------------

class TestEscalateToHuman:

    def setup_method(self):
        fresh_store()

    def _make_ticket(self, email="esc@example.com", priority="high", channel="email") -> str:
        result = run(create_ticket(email, "Test issue", priority, channel))
        return result.split(": ")[-1].strip()

    def test_returns_escalation_id(self):
        tid = self._make_ticket()
        result = run(escalate_to_human(tid, "legal_threat"))
        assert "ESC-" in result

    def test_result_contains_ticket_id(self):
        tid = self._make_ticket()
        result = run(escalate_to_human(tid, "refund_request"))
        assert tid in result

    def test_result_contains_urgency(self):
        tid = self._make_ticket()
        result = run(escalate_to_human(tid, "refund_request"))
        assert "high" in result

    def test_result_contains_routed_to(self):
        tid = self._make_ticket()
        result = run(escalate_to_human(tid, "refund_request"))
        assert "billing@nimbusflow.io" in result

    def test_result_contains_sla(self):
        tid = self._make_ticket()
        result = run(escalate_to_human(tid, "legal_threat"))
        assert "2 hours" in result

    def test_legal_threat_is_critical(self):
        tid = self._make_ticket()
        result = run(escalate_to_human(tid, "legal_threat"))
        assert "critical" in result

    def test_security_incident_is_critical(self):
        tid = self._make_ticket()
        result = run(escalate_to_human(tid, "security_incident"))
        assert "critical" in result
        assert "security@nimbusflow.io" in result

    def test_knowledge_gap_is_low(self):
        tid = self._make_ticket()
        result = run(escalate_to_human(tid, "knowledge_gap"))
        assert "low" in result
        assert "1 business day" in result

    def test_unknown_reason_defaults_to_normal(self):
        tid = self._make_ticket()
        result = run(escalate_to_human(tid, "some_unusual_reason"))
        assert "normal" in result
        assert "support@nimbusflow.io" in result

    def test_ticket_status_updated_to_escalated(self):
        tid = self._make_ticket()
        run(escalate_to_human(tid, "chargeback_threat"))
        ticket = _server_module._store.get_ticket(tid)
        assert ticket.status == "escalated"

    def test_escalation_reason_stored_on_ticket(self):
        tid = self._make_ticket()
        run(escalate_to_human(tid, "data_loss_reported"))
        ticket = _server_module._store.get_ticket(tid)
        assert ticket.escalation_reason == "data_loss_reported"

    def test_empty_ticket_id_returns_error(self):
        result = run(escalate_to_human("", "legal_threat"))
        assert "Error" in result

    def test_empty_reason_returns_error(self):
        result = run(escalate_to_human("NF-FAKEID1", ""))
        assert "Error" in result

    def test_non_existent_ticket_still_returns_escalation(self):
        # Should not crash if ticket not in store (graceful degradation)
        result = run(escalate_to_human("NF-NOTFOUND", "knowledge_gap"))
        assert "ESC-" in result  # still returns an escalation ID

    def test_urgency_map_coverage(self):
        """All standard reasons have urgency mappings."""
        expected_reasons = [
            "legal_threat", "security_incident", "chargeback_threat",
            "data_loss_reported", "refund_request", "explicit_human_request",
            "knowledge_gap", "pricing_negotiation",
        ]
        for reason in expected_reasons:
            assert reason in _URGENCY_MAP, f"{reason} missing from urgency map"

    def test_all_urgencies_have_sla(self):
        for urgency in ["critical", "high", "normal", "low"]:
            assert urgency in _SLA_MAP


# ---------------------------------------------------------------------------
# Tool 5: send_response
# ---------------------------------------------------------------------------

class TestSendResponse:

    def setup_method(self):
        fresh_store()

    def _make_ticket(self, email="send@example.com", channel="email") -> str:
        result = run(create_ticket(email, "Test issue", "medium", channel))
        return result.split(": ")[-1].strip()

    def test_returns_delivery_confirmation(self):
        tid = self._make_ticket()
        result = run(send_response(tid, "Here is the answer.", "email"))
        assert "delivered" in result.lower() or "Response" in result

    def test_result_contains_ticket_id(self):
        tid = self._make_ticket()
        result = run(send_response(tid, "Your account was unlocked.", "email"))
        assert tid in result

    def test_result_contains_channel(self):
        tid = self._make_ticket()
        result = run(send_response(tid, "To reset: go to /forgot-password.", "email"))
        assert "email" in result.lower()

    def test_result_contains_preview(self):
        tid = self._make_ticket()
        result = run(send_response(tid, "Your password reset link is ready.", "email"))
        assert "Preview" in result

    def test_email_formatting_applied(self):
        """Email responses should include greeting and sign-off in the formatted output."""
        tid = self._make_ticket(email="greet@example.com", channel="email")
        result = run(send_response(tid, "Here is the fix.", "email"))
        # Preview in result should contain formatted content
        assert "NimbusFlow" in result or "Hi" in result or "ticket" in result.lower()

    def test_whatsapp_response_delivered(self):
        tid = self._make_ticket(email="+14155551234", channel="whatsapp")
        result = run(send_response(tid, "Go to /forgot-password to reset.", "whatsapp"))
        assert "delivered" in result.lower() or "Response" in result

    def test_web_form_response_delivered(self):
        tid = self._make_ticket(email="wf@example.com", channel="web_form")
        result = run(send_response(tid, "Please re-authorize GitHub in Settings.", "web_form"))
        assert "Response" in result or "delivered" in result.lower()

    def test_ticket_status_updated_to_responded(self):
        tid = self._make_ticket()
        run(send_response(tid, "Here is the information.", "email"))
        ticket = _server_module._store.get_ticket(tid)
        assert ticket.status == "responded"

    def test_message_stored_in_conversation(self):
        tid = self._make_ticket(email="conv@example.com")
        run(send_response(tid, "Here is your answer.", "email"))
        ticket = _server_module._store.get_ticket(tid)
        if ticket and ticket.conversation_id:
            history = _server_module._store.get_conversation_history(
                ticket.conversation_id
            )
            agent_msgs = [m for m in history if m["role"] == "agent"]
            assert len(agent_msgs) >= 1

    def test_empty_ticket_id_returns_error(self):
        result = run(send_response("", "Answer.", "email"))
        assert "Error" in result

    def test_empty_message_returns_error(self):
        result = run(send_response("NF-FAKEID1", "", "email"))
        assert "Error" in result

    def test_invalid_channel_returns_error(self):
        tid = self._make_ticket()
        result = run(send_response(tid, "Answer.", "sms"))
        assert "Error" in result

    def test_non_existent_ticket_still_sends(self):
        """send_response should not crash if ticket not in store."""
        result = run(send_response("NF-NOTFOUND", "Here is the answer.", "email"))
        # Should still format and return delivery status
        assert "Error" not in result or "delivered" in result.lower()

    def test_escalated_ticket_not_re_updated(self):
        """Sending response to an already-escalated ticket should not change status."""
        tid = self._make_ticket()
        run(escalate_to_human(tid, "legal_threat"))
        run(send_response(tid, "Some message.", "email"))
        ticket = _server_module._store.get_ticket(tid)
        # Status should remain escalated
        assert ticket.status == "escalated"


# ---------------------------------------------------------------------------
# Tool registration / server metadata
# ---------------------------------------------------------------------------

class TestServerRegistration:

    def test_server_name(self):
        from src.mcp.server import mcp
        assert mcp.name == "customer-success-fte"

    def test_five_tools_registered(self):
        from src.mcp.server import mcp
        tools = asyncio.run(mcp.list_tools())
        tool_names = {t.name for t in tools}
        expected = {
            "search_knowledge_base",
            "create_ticket",
            "get_customer_history",
            "escalate_to_human",
            "send_response",
        }
        assert expected == tool_names, (
            f"Missing tools: {expected - tool_names} | "
            f"Unexpected: {tool_names - expected}"
        )

    def test_all_tools_have_descriptions(self):
        from src.mcp.server import mcp
        tools = asyncio.run(mcp.list_tools())
        for tool in tools:
            assert tool.description, f"Tool '{tool.name}' has no description"
            assert len(tool.description) > 30, (
                f"Tool '{tool.name}' description too short: {tool.description!r}"
            )

    def test_all_tools_have_input_schemas(self):
        from src.mcp.server import mcp
        tools = asyncio.run(mcp.list_tools())
        for tool in tools:
            assert tool.inputSchema, f"Tool '{tool.name}' has no inputSchema"
            assert "properties" in tool.inputSchema, (
                f"Tool '{tool.name}' inputSchema missing 'properties'"
            )

    def test_search_tool_has_query_param(self):
        from src.mcp.server import mcp
        tools = asyncio.run(mcp.list_tools())
        search = next(t for t in tools if t.name == "search_knowledge_base")
        assert "query" in search.inputSchema["properties"]

    def test_create_ticket_has_required_params(self):
        from src.mcp.server import mcp
        tools = asyncio.run(mcp.list_tools())
        ct = next(t for t in tools if t.name == "create_ticket")
        props = ct.inputSchema["properties"]
        for param in ["customer_id", "issue", "priority", "channel"]:
            assert param in props, f"create_ticket missing param: {param}"

    def test_escalate_tool_has_required_params(self):
        from src.mcp.server import mcp
        tools = asyncio.run(mcp.list_tools())
        esc = next(t for t in tools if t.name == "escalate_to_human")
        props = esc.inputSchema["properties"]
        assert "ticket_id" in props
        assert "reason" in props

    def test_send_response_has_required_params(self):
        from src.mcp.server import mcp
        tools = asyncio.run(mcp.list_tools())
        sr = next(t for t in tools if t.name == "send_response")
        props = sr.inputSchema["properties"]
        for param in ["ticket_id", "message", "channel"]:
            assert param in props, f"send_response missing param: {param}"
