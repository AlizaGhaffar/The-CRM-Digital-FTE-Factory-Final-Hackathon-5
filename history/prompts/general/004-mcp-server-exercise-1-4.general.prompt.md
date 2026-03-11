---
id: 004
title: MCP Server Exercise 1.4
stage: general
date: 2026-03-06
surface: agent
model: claude-sonnet-4-6
feature: none
branch: master
user: CDC
command: inline
labels: ["mcp","tools","fastmcp","exercise-1.4","customer-success-fte","incubation"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - src/mcp/__init__.py
  - src/mcp/server.py
  - tests/test_mcp_server.py
tests:
  - tests/test_mcp_server.py (69 tests — 69 passed)
---

## Prompt

Following Exercise 1.4 EXACTLY from hackathon document:

Create /src/mcp/server.py with these 5 tools:
1. search_knowledge_base(query) -> relevant docs
2. create_ticket(customer_id, issue, priority, channel) -> ticket_id
3. get_customer_history(customer_id) -> past interactions across ALL channels
4. escalate_to_human(ticket_id, reason) -> escalation_id
5. send_response(ticket_id, message, channel) -> delivery_status

Follow MCP specification exactly. Use the template provided in the document.
Each tool must have proper error handling and logging.

## Response snapshot

Discovered that the hackathon template's `@server.tool()` (from `mcp.server.Server`) does not exist in MCP 1.26.0 — the installed version. `FastMCP` from `mcp.server.fastmcp` is the correct high-level API and provides the identical `@mcp.tool()` decorator pattern the template intends.

Created `src/mcp/server.py` with:
- `FastMCP("customer-success-fte")` — matches template server name exactly
- All 5 tools as `@mcp.tool()` async functions
- Logging to stderr (keeps stdio MCP transport clean)
- Input validation + try/except error handling on every tool
- Wired to `src.agent.core.search_docs` / `format_for_channel` (Ex 1.2)
- Wired to `src.agent.memory.MemoryStore` (Ex 1.3) — shared module-level singleton

Tool details:
1. `search_knowledge_base(query)` — 2-pass search (broad then narrow), 600-char section cap, markdown output
2. `create_ticket(customer_id, issue, priority, channel)` — resolves/creates customer (email primary), creates conversation, returns NF-XXXXXXXX
3. `get_customer_history(customer_id)` — uses `resolve_customer_id` + `build_agent_context`; surfaces repeat contact, channel switches, sentiment, last 5 tickets
4. `escalate_to_human(ticket_id, reason)` — urgency/route resolved from reason keyword table; updates ticket+conversation in store; returns ESC-XXXXXXXX
5. `send_response(ticket_id, message, channel)` — applies brand-voice formatting via `format_for_channel`; stores outbound message; guards escalated tickets from re-update

Transport: stdio (default) or SSE via --sse flag.
`TestServerRegistration` verifies exactly 5 tools are registered with correct names, descriptions, and input schemas via `mcp.list_tools()`.

**69/69 tests pass.**

## Outcome

- Impact: Exercise 1.4 complete. MCP server is runnable and connectable to Claude Desktop or any MCP host via stdio transport.
- Tests: 69/69 PASS (2.19s)
- Files: src/mcp/__init__.py (new), src/mcp/server.py (new), tests/test_mcp_server.py (new)
- Next prompts: Exercise 1.5 (agent skills manifest), wire MCP server into Claude Desktop config
- Reflection: `@server.tool()` in hackathon template is pseudocode from older MCP SDK — documented the discrepancy and used FastMCP. All tool behaviours match spec exactly.

## Evaluation notes (flywheel)

- Failure modes observed: none — 69/69 first run
- Graders run and results (PASS/FAIL): pytest tests/test_mcp_server.py — 69 PASS
- Prompt variant (if applicable): none
- Next experiment: Connect to Claude Desktop via mcp config; test tool-calling flow end-to-end with a real Claude session
