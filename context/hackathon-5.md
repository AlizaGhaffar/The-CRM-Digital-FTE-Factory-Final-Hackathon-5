# The CRM Digital FTE Factory Final Hackathon 5

## Build Your First 24/7 AI Employee: From Incubation to Production

**Duration:** 48-72 Development Hours | **Team Size:** 1 Student | **Difficulty:** Advanced

---

## Executive Summary

In this final and fifth hackathon, you will implement the complete **Agent Maturity Model** by building a real Digital FTE (Full-Time Equivalent) - an AI employee that works 24/7 without breaks, sick days, or vacations.

You'll experience the full evolutionary arc:

1. **Stage 1 - Incubation:** Use Claude Code to explore, prototype, and discover requirements

2. **Stage 2 - Specialization:** Transform your prototype into a production-grade Custom Agent using OpenAI Agents SDK, FastAPI, PostgreSQL, Kafka, and Kubernetes

By the end, you'll have a production-deployed AI employee handling a real business function autonomously across **multiple communication channels**.

Reference: Agent Maturity Model
https://agentfactory.panaversity.org/docs/General-Agents-Foundations/agent-factory-paradigm/the-2025-inflection-point#the-agent-maturity-model

---

## The Business Problem: Customer Success FTE

Your client is a growing SaaS company drowning in customer inquiries. They need a **Customer Success FTE** that can:

* Handle customer questions about their product 24/7
* **Accept inquiries from multiple channels:** Email (Gmail), WhatsApp, and Web Form
* Triage and escalate complex issues appropriately
* Track all interactions in a ticket management system (PostgreSQL-based - you will build this)
* Generate daily reports on customer sentiment
* Learn from resolved tickets to improve responses

**Note on CRM/Ticket System:** For this hackathon, you will build your own ticket management and customer tracking system using PostgreSQL. This serves as your CRM. You are NOT required to integrate with external CRMs like Salesforce or HubSpot. The database schema you create (customers, conversations, tickets, messages tables) IS your CRM system.

**Current cost of human FTE:** $75,000/year + benefits + training + management overhead

**Your target:** Build a Digital FTE that operates at <$1,000/year with 24/7 availability

---

## Multi-Channel Architecture Overview

Your FTE will receive support tickets from three channels:

```
+-----------------------------------------------------------------------------+
|                     MULTI-CHANNEL INTAKE ARCHITECTURE                        |
|                                                                              |
|   +--------------+    +--------------+    +--------------+                 |
|   |    Gmail     |    |   WhatsApp   |    |   Web Form   |                 |
|   |   (Email)    |    |  (Messaging) |    |  (Website)   |                 |
|   +------+-------+    +------+-------+    +------+-------+                 |
|          |                   |                   |                          |
|          v                   v                   v                          |
|   +--------------+    +--------------+    +--------------+                 |
|   | Gmail API /  |    |   Twilio     |    |   FastAPI    |                 |
|   |   Webhook    |    |   Webhook    |    |   Endpoint   |                 |
|   +------+-------+    +------+-------+    +------+-------+                 |
|          |                   |                   |                          |
|          +-------------------+-------------------+                          |
|                              v                                               |
|                    +-----------------+                                      |
|                    |  Unified Ticket |                                      |
|                    |    Ingestion    |                                      |
|                    |     (Kafka)     |                                      |
|                    +--------+--------+                                      |
|                             |                                                |
|                             v                                                |
|                    +-----------------+                                      |
|                    |   Customer      |                                      |
|                    |   Success FTE   |                                      |
|                    |    (Agent)      |                                      |
|                    +--------+--------+                                      |
|                             |                                                |
|              +--------------+--------------+                                |
|              v              v              v                                 |
|         Reply via      Reply via     Reply via                              |
|          Email         WhatsApp       Web/API                               |
+-----------------------------------------------------------------------------+
```

### Channel Requirements

| Channel | Integration Method | Student Builds | Response Method |
| :---- | :---- | :---- | :---- |
| **Gmail** | Gmail API + Pub/Sub or Polling | Webhook handler | Send via Gmail API |
| **WhatsApp** | Twilio WhatsApp API | Webhook handler | Reply via Twilio |
| **Web Form** | Next.js/HTML Form | **Complete form UI** | API response + Email |

**Important:** Students must build the complete **Web Support Form** (not the entire website). The form should be a standalone, embeddable component.

---

## Part 1: The Incubation Phase (Hours 1-16)

### Objective

Use Claude Code as your **Agent Factory** to explore the problem space, discover hidden requirements, and build a working prototype.

### Your Role: Director

You are NOT writing code line-by-line. You are directing an intelligent system toward a goal.

### Setup: The Development Dossier

Before starting, prepare your "dossier" - the context Claude Code needs:

```
project-root/
├── context/
│   ├── company-profile.md      # Fake SaaS company details
│   ├── product-docs.md         # Product documentation to answer from
│   ├── sample-tickets.json     # 50+ sample customer inquiries (multi-channel)
│   ├── escalation-rules.md     # When to involve humans
│   └── brand-voice.md          # How the company communicates
├── src/
│   ├── channels/               # Channel integrations
│   ├── agent/                  # Core agent logic
│   └── web-form/               # Support form frontend
├── tests/                      # Test cases discovered during incubation
└── specs/                      # Crystallized requirements (output)
```

### Exercise 1.1: Initial Exploration (2-3 hours)

**Prompt Claude Code with your initial intent:**

```
I need to build a Customer Success AI agent for a SaaS company.

The agent should:
- Answer customer questions from product documentation
- Accept tickets from THREE channels: Gmail, WhatsApp, and a Web Form
- Know when to escalate to humans
- Track all interactions with channel source metadata

I've provided company context in the /context folder.
Help me explore what this system should look like.
Start by analyzing the sample tickets and identifying patterns across channels.
```

**What to observe:**
- How does Claude Code plan the exploration?
- What patterns does it discover in the sample tickets?
- Are there channel-specific patterns (email tends to be longer, WhatsApp is more conversational)?
- What questions does it ask you for clarification?

**Document your discoveries in specs/discovery-log.md**

### Exercise 1.2: Prototype the Core Loop (4-5 hours)

**Direct Claude Code to build the basic interaction:**

```
Based on our analysis, let's prototype the core customer interaction loop.
Build a simple version that:
1. Takes a customer message as input (with channel metadata)
2. Normalizes the message regardless of source channel
3. Searches the product docs for relevant information
4. Generates a helpful response
5. Formats response appropriately for the channel (email vs chat style)
6. Decides if escalation is needed

Use Python. Start simple - we'll iterate.
```

**Iteration prompts to use:**

```
# After first version works:
"This crashes when the customer asks about pricing.
Add handling for pricing-related queries."

# Channel-specific iteration:
"WhatsApp messages are much shorter and more casual.
Adjust response style based on channel."

# Email-specific iteration:
"Email responses need proper greeting and signature.
Add channel-aware formatting."

# After testing with real scenarios:
"The responses are too long for WhatsApp. Customers want concise answers.
Optimize for brevity on chat channels while keeping detail on email."
```

### Exercise 1.3: Add Memory and State (3-4 hours)

**Extend the prototype:**

```
Our agent needs to remember context across a conversation.
If a customer asks follow-up questions, the agent should understand
they're continuing the same topic - even if they switch channels!

Add conversation memory. Also track:
- Customer sentiment (is this interaction going well?)
- Topics discussed (for reporting)
- Resolution status (solved/pending/escalated)
- Original channel and any channel switches
- Customer identifier (email address as primary key)
```

### Exercise 1.4: Build the MCP Server (3-4 hours)

Model Context Protocol (MCP) is how your agent will connect to external tools. Build an MCP server that exposes your prototype's capabilities:

```
Let's expose our customer success agent as an MCP server.
Create tools for:
- search_knowledge_base(query) -> relevant docs
- create_ticket(customer_id, issue, priority, channel) -> ticket_id
- get_customer_history(customer_id) -> past interactions across ALL channels
- escalate_to_human(ticket_id, reason) -> escalation_id
- send_response(ticket_id, message, channel) -> delivery_status

Follow the MCP specification for tool definitions.
```

**MCP Server Template to Start:**

```python
# mcp_server.py
from mcp.server import Server
from mcp.types import Tool, TextContent
from enum import Enum

class Channel(str, Enum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    WEB_FORM = "web_form"

server = Server("customer-success-fte")

@server.tool("search_knowledge_base")
async def search_kb(query: str) -> str:
    """Search product documentation for relevant information."""
    # Your implementation from incubation
    pass

@server.tool("create_ticket")
async def create_ticket(
    customer_id: str,
    issue: str,
    priority: str,
    channel: Channel
) -> str:
    """Create a support ticket in the system with channel tracking."""
    pass

@server.tool("get_customer_history")
async def get_customer_history(customer_id: str) -> str:
    """Get customer's interaction history across ALL channels."""
    pass

@server.tool("send_response")
async def send_response(
    ticket_id: str,
    message: str,
    channel: Channel
) -> str:
    """Send response via the appropriate channel."""
    pass

# Add more tools...

if __name__ == "__main__":
    server.run()
```

### Exercise 1.5: Define Agent Skills (2-3 hours)

Agent Skills are reusable capabilities your FTE can invoke. Create skill definitions:

```
Based on what we've built, let's formalize the agent's skills.
Create a skills manifest that defines:

1. Knowledge Retrieval Skill
   - When to use: Customer asks product questions
   - Inputs: query text
   - Outputs: relevant documentation snippets

2. Sentiment Analysis Skill
   - When to use: Every customer message
   - Inputs: message text
   - Outputs: sentiment score, confidence

3. Escalation Decision Skill
   - When to use: After generating response
   - Inputs: conversation context, sentiment trend
   - Outputs: should_escalate (bool), reason

4. Channel Adaptation Skill
   - When to use: Before sending any response
   - Inputs: response text, target channel
   - Outputs: formatted response appropriate for channel

5. Customer Identification Skill
   - When to use: On every incoming message
   - Inputs: message metadata (email, phone, etc.)
   - Outputs: unified customer_id, merged history

Create the skill definitions in a reusable format.
```

### Incubation Deliverables Checklist

Before moving to Stage 2, ensure you have:

* [ ] **Working prototype** that handles customer queries from any channel
* [ ] **Discovery log** documenting requirements found during exploration
* [ ] **MCP server** with 5+ tools exposed (including channel-aware tools)
* [ ] **Agent skills** defined and tested
* [ ] **Edge cases** documented with handling strategies
* [ ] **Escalation rules** crystallized from testing
* [ ] **Channel-specific response templates** discovered
* [ ] **Performance baseline** (response time, accuracy on test set)

### Crystallization Document

Create specs/customer-success-fte-spec.md:

```markdown
# Customer Success FTE Specification

## Purpose
Handle routine customer support queries with speed and consistency across multiple channels.

## Supported Channels
| Channel | Identifier | Response Style | Max Length |
|---------|------------|----------------|------------|
| Email (Gmail) | Email address | Formal, detailed | 500 words |
| WhatsApp | Phone number | Conversational, concise | 160 chars preferred |
| Web Form | Email address | Semi-formal | 300 words |

## Scope
### In Scope
- Product feature questions
- How-to guidance
- Bug report intake
- Feedback collection
- Cross-channel conversation continuity

### Out of Scope (Escalate)
- Pricing negotiations
- Refund requests
- Legal/compliance questions
- Angry customers (sentiment < 0.3)

## Tools
| Tool | Purpose | Constraints |
|------|---------|-------------|
| search_knowledge_base | Find relevant docs | Max 5 results |
| create_ticket | Log interactions | Required for all chats; include channel |
| escalate_to_human | Hand off complex issues | Include full context |
| send_response | Reply to customer | Channel-appropriate formatting |

## Performance Requirements
- Response time: <3 seconds (processing), <30 seconds (delivery)
- Accuracy: >85% on test set
- Escalation rate: <20%
- Cross-channel identification: >95% accuracy

## Guardrails
- NEVER discuss competitor products
- NEVER promise features not in docs
- ALWAYS create ticket before responding
- ALWAYS check sentiment before closing
- ALWAYS use channel-appropriate tone
```

---

## The Transition: From General Agent to Custom Agent (Hours 15-18)

This is the most critical phase of the hackathon. You're transforming exploratory code into production-ready systems.

**Important: Claude Code Remains Your Development Partner**

A common misconception is that you stop using Claude Code (the General Agent) once you transition to building the Custom Agent. **This is incorrect.** Claude Code remains your primary development tool throughout the entire hackathon. During the Specialization Phase, you will use Claude Code to:
- Write the OpenAI Agents SDK implementation code
- Generate the FastAPI endpoints and channel handlers
- Create the PostgreSQL schema and database queries
- Build Kubernetes manifests and Docker configurations
- Debug issues and iterate on your production code

Think of it this way: **Claude Code is the factory that builds the Custom Agent.**

### Understanding the Transition

```
+-----------------------------------------------------------------------------+
|                    THE EVOLUTION: WHAT CHANGES                               |
|                                                                              |
|   GENERAL AGENT (Claude Code)          CUSTOM AGENT (OpenAI SDK)            |
|   ---------------------------------    ---------------------------------     |
|                                                                              |
|   - Interactive exploration      ->    - Automated execution                 |
|   - Dynamic planning             ->    - Pre-defined workflows               |
|   - Human-in-the-loop            ->    - Autonomous operation                |
|   - Flexible responses           ->    - Constrained responses               |
|   - Single user (you)            ->    - Thousands of users                  |
|   - Local execution              ->    - Distributed infrastructure          |
|   - Ad-hoc tools                 ->    - Formal tool definitions             |
|   - Conversational memory        ->    - Persistent database state           |
|   - Trial and error              ->    - Tested and validated                |
+-----------------------------------------------------------------------------+
```

### Step 1: Extract Your Discoveries (1 hour)

**Create specs/transition-checklist.md:**

```markdown
# Transition Checklist: General -> Custom Agent

## 1. Discovered Requirements
List every requirement you discovered during incubation:
- [ ] Requirement 1: _______________
- [ ] Requirement 2: _______________
- [ ] (Add all requirements)

## 2. Working Prompts
Copy the exact prompts that worked well:

### System Prompt That Worked:
[Paste your working system prompt from Claude Code here]

### Tool Descriptions That Worked:
[Paste tool descriptions that gave good results]

## 3. Edge Cases Found
| Edge Case | How It Was Handled | Test Case Needed |
|-----------|-------------------|------------------|
| Example: Empty message | Return helpful prompt | Yes |

## 4. Response Patterns
What response styles worked best?
- Email: [describe]
- WhatsApp: [describe]
- Web: [describe]

## 5. Escalation Rules (Finalized)
When did escalation work correctly?
- Trigger 1: _______________
- Trigger 2: _______________

## 6. Performance Baseline
From your prototype testing:
- Average response time: ___ seconds
- Accuracy on test set: ___%
- Escalation rate: ___%
```

### Step 2: Map Prototype Code to Production Components (1 hour)

```
+-----------------------------------------------------------------------------+
|                         CODE MAPPING TABLE                                   |
|                                                                              |
|   INCUBATION (What you built)          PRODUCTION (Where it goes)           |
|   ---------------------------          -------------------------            |
|                                                                              |
|   Prototype Python script        ->    agent/customer_success_agent.py      |
|   MCP server tools               ->    @function_tool decorated functions   |
|   In-memory conversation         ->    PostgreSQL messages table            |
|   Print statements               ->    Structured logging + Kafka events    |
|   Manual testing                 ->    pytest test suite                    |
|   Local file storage             ->    PostgreSQL + S3/MinIO                |
|   Single-threaded                ->    Async workers on Kubernetes          |
|   Hardcoded config               ->    Environment variables + ConfigMaps   |
|   Direct API calls               ->    Channel handlers with retry logic    |
+-----------------------------------------------------------------------------+
```

**Production file structure:**

```
production/
├── agent/
│   ├── __init__.py
│   ├── customer_success_agent.py    # Your agent definition
│   ├── tools.py                      # All @function_tool definitions
│   ├── prompts.py                    # System prompts (extracted from prototype)
│   └── formatters.py                 # Channel-specific response formatting
├── channels/
│   ├── __init__.py
│   ├── gmail_handler.py              # Gmail integration
│   ├── whatsapp_handler.py           # Twilio/WhatsApp integration
│   └── web_form_handler.py           # Web form API
├── workers/
│   ├── __init__.py
│   ├── message_processor.py          # Kafka consumer + agent runner
│   └── metrics_collector.py          # Background metrics
├── api/
│   ├── __init__.py
│   └── main.py                       # FastAPI application
├── database/
│   ├── schema.sql                    # PostgreSQL schema
│   ├── migrations/                   # Database migrations
│   └── queries.py                    # Database access functions
├── tests/
│   ├── test_agent.py
│   ├── test_channels.py
│   └── test_e2e.py
├── k8s/                              # Kubernetes manifests
├── Dockerfile
├── docker-compose.yml                # Local development
└── requirements.txt
```

### Step 3: Transform Your MCP Tools to Production Tools (1 hour)

**Before (MCP Server - Incubation):**

```python
# What you built during incubation
from mcp.server import Server

server = Server("customer-success-fte")

@server.tool("search_knowledge_base")
async def search_kb(query: str) -> str:
    """Search product documentation."""
    # Your prototype implementation
    results = simple_search(query)  # Maybe just string matching
    return str(results)
```

**After (OpenAI Agents SDK - Production):**

```python
# production/agent/tools.py

from agents import function_tool
from pydantic import BaseModel
from typing import Optional
import asyncpg

# 1. Define strict input schemas
class KnowledgeSearchInput(BaseModel):
    """Input schema for knowledge base search."""
    query: str
    max_results: int = 5
    category: Optional[str] = None  # Optional filter

# 2. Create production tool with proper typing and error handling
@function_tool
async def search_knowledge_base(input: KnowledgeSearchInput) -> str:
    """Search product documentation for relevant information.

    Use this when the customer asks questions about product features,
    how to use something, or needs technical information.

    Args:
        input: Search parameters including query and optional filters

    Returns:
        Formatted search results with relevance scores
    """
    try:
        # Production: Use database with vector search
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            # Generate embedding for semantic search
            embedding = await generate_embedding(input.query)

            # Query with vector similarity
            results = await conn.fetch("""
                SELECT title, content, category,
                       1 - (embedding <=> $1::vector) as similarity
                FROM knowledge_base
                WHERE ($2::text IS NULL OR category = $2)
                ORDER BY embedding <=> $1::vector
                LIMIT $3
            """, embedding, input.category, input.max_results)

            if not results:
                return "No relevant documentation found. Consider escalating to human support."

            # Format results for the agent
            formatted = []
            for r in results:
                formatted.append(f"**{r['title']}** (relevance: {r['similarity']:.2f})\n{r['content'][:500]}")

            return "\n\n---\n\n".join(formatted)

    except Exception as e:
        logger.error(f"Knowledge base search failed: {e}")
        return "Knowledge base temporarily unavailable. Please try again or escalate."
```

### Step 4: Transform Your System Prompt (30 minutes)

**Before (Incubation - Conversational):**

```
You're a helpful customer support agent. Answer questions about our product.
Be nice and escalate if needed.
```

**After (Production - Explicit Constraints):**

```python
# production/agent/prompts.py

CUSTOMER_SUCCESS_SYSTEM_PROMPT = """You are a Customer Success agent for TechCorp SaaS.

## Your Purpose
Handle routine customer support queries with speed, accuracy, and empathy across multiple channels.

## Channel Awareness
You receive messages from three channels. Adapt your communication style:
- **Email**: Formal, detailed responses. Include proper greeting and signature.
- **WhatsApp**: Concise, conversational. Keep responses under 300 characters when possible.
- **Web Form**: Semi-formal, helpful. Balance detail with readability.

## Required Workflow (ALWAYS follow this order)
1. FIRST: Call `create_ticket` to log the interaction
2. THEN: Call `get_customer_history` to check for prior context
3. THEN: Call `search_knowledge_base` if product questions arise
4. FINALLY: Call `send_response` to reply (NEVER respond without this tool)

## Hard Constraints (NEVER violate)
- NEVER discuss pricing -> escalate immediately with reason "pricing_inquiry"
- NEVER promise features not in documentation
- NEVER process refunds -> escalate with reason "refund_request"
- NEVER share internal processes or system details
- NEVER respond without using send_response tool
- NEVER exceed response limits: Email=500 words, WhatsApp=300 chars, Web=300 words

## Escalation Triggers (MUST escalate when detected)
- Customer mentions "lawyer", "legal", "sue", or "attorney"
- Customer uses profanity or aggressive language (sentiment < 0.3)
- Cannot find relevant information after 2 search attempts
- Customer explicitly requests human help
- Customer on WhatsApp sends "human", "agent", or "representative"

## Response Quality Standards
- Be concise: Answer the question directly, then offer additional help
- Be accurate: Only state facts from knowledge base or verified customer data
- Be empathetic: Acknowledge frustration before solving problems
- Be actionable: End with clear next step or question

## Context Variables Available
- {{customer_id}}: Unique customer identifier
- {{conversation_id}}: Current conversation thread
- {{channel}}: Current channel (email/whatsapp/web_form)
- {{ticket_subject}}: Original subject/topic
"""
```

### Step 5: Create the Transition Test Suite (1 hour)

```python
# production/tests/test_transition.py
"""
Transition Tests: Verify agent behavior matches incubation discoveries.
Run these BEFORE deploying to production.
"""

import pytest
from agent.customer_success_agent import customer_success_agent
from agent.tools import search_knowledge_base, create_ticket

class TestTransitionFromIncubation:
    """Tests based on edge cases discovered during incubation."""

    @pytest.mark.asyncio
    async def test_edge_case_empty_message(self):
        """Edge case #1 from incubation: Empty messages."""
        result = await customer_success_agent.run(
            messages=[{"role": "user", "content": ""}],
            context={"channel": "web_form", "customer_id": "test-1"}
        )
        assert "help" in result.output.lower() or "question" in result.output.lower()

    @pytest.mark.asyncio
    async def test_edge_case_pricing_escalation(self):
        """Edge case #2 from incubation: Pricing questions must escalate."""
        result = await customer_success_agent.run(
            messages=[{"role": "user", "content": "How much does the enterprise plan cost?"}],
            context={"channel": "email", "customer_id": "test-2"}
        )
        assert result.escalated == True
        assert "pricing" in result.escalation_reason.lower()

    @pytest.mark.asyncio
    async def test_edge_case_angry_customer(self):
        """Edge case #3 from incubation: Angry customers need care."""
        result = await customer_success_agent.run(
            messages=[{"role": "user", "content": "This is RIDICULOUS! Your product is BROKEN!"}],
            context={"channel": "whatsapp", "customer_id": "test-3"}
        )
        assert result.escalated == True or "understand" in result.output.lower()

    @pytest.mark.asyncio
    async def test_channel_response_length_email(self):
        """Verify email responses are appropriately detailed."""
        result = await customer_success_agent.run(
            messages=[{"role": "user", "content": "How do I reset my password?"}],
            context={"channel": "email", "customer_id": "test-4"}
        )
        assert "dear" in result.output.lower() or "hello" in result.output.lower()

    @pytest.mark.asyncio
    async def test_channel_response_length_whatsapp(self):
        """Verify WhatsApp responses are concise."""
        result = await customer_success_agent.run(
            messages=[{"role": "user", "content": "How do I reset my password?"}],
            context={"channel": "whatsapp", "customer_id": "test-5"}
        )
        assert len(result.output) < 500

    @pytest.mark.asyncio
    async def test_tool_execution_order(self):
        """Verify tools are called in correct order."""
        result = await customer_success_agent.run(
            messages=[{"role": "user", "content": "I need help with the API"}],
            context={"channel": "web_form", "customer_id": "test-6"}
        )
        tool_names = [tc.tool_name for tc in result.tool_calls]
        assert tool_names[0] == "create_ticket"
        assert tool_names[-1] == "send_response"
```

### Step 6: The Transition Checklist

```markdown
## Pre-Transition Checklist

### From Incubation (Must Have Before Proceeding)
- [ ] Working prototype that handles basic queries
- [ ] Documented edge cases (minimum 10)
- [ ] Working system prompt
- [ ] MCP tools defined and tested
- [ ] Channel-specific response patterns identified
- [ ] Escalation rules finalized
- [ ] Performance baseline measured

### Transition Steps
- [ ] Created production folder structure
- [ ] Extracted prompts to prompts.py
- [ ] Converted MCP tools to @function_tool
- [ ] Added Pydantic input validation to all tools
- [ ] Added error handling to all tools
- [ ] Created transition test suite
- [ ] All transition tests passing

### Ready for Production Build
- [ ] Database schema designed
- [ ] Kafka topics defined
- [ ] Channel handlers outlined
- [ ] Kubernetes resource requirements estimated
- [ ] API endpoints listed
```

### Common Transition Mistakes (Avoid These!)

| Mistake | Why It Happens | How to Avoid |
| :---- | :---- | :---- |
| Skipping documentation | "I remember what worked" | Write it down immediately |
| Copying code directly | "It worked in prototype" | Refactor for production patterns |
| Ignoring edge cases | "We'll fix those later" | Test edge cases first |
| Hardcoding values | "Just for now" | Use config from day 1 |
| No error handling | "It didn't crash before" | Everything can fail at scale |
| Forgetting channel differences | "One response fits all" | Test each channel separately |

### Transition Complete Criteria

1. All transition tests pass
2. Prompts are extracted and documented
3. Tools have proper input validation
4. Error handling exists for all tools
5. Edge cases are documented with test cases
6. Production folder structure is created

---

## Part 2: The Specialization Phase (Hours 17-40)

### Objective

Transform your incubated prototype into a production-grade Custom Agent that runs 24/7 on Kubernetes with Kafka for event streaming and **multi-channel intake**.

### Architecture Overview

```
+-----------------------------------------------------------------------------+
|                       PRODUCTION ARCHITECTURE                                |
|                                                                              |
|  CHANNEL INTAKE LAYER                                                        |
|  +-------------+  +-------------+  +-------------+                          |
|  |Gmail Webhook|  |Twilio Webook|  | Web Form    |                          |
|  |  Handler    |  |  Handler    |  |  Handler    |                          |
|  +------+------+  +------+------+  +------+------+                          |
|         |                |                |                                  |
|         +--------------++-+--------------+                                  |
|                          v                                                   |
|  EVENT STREAMING    +----------+                                            |
|                     |  Kafka   |                                            |
|                     | (Events) |                                            |
|                     +----+-----+                                            |
|                          |                                                   |
|  PROCESSING LAYER        v                                                  |
|                    +-----------+     +----------+                           |
|                    |  Agent    |---->| Postgres |                           |
|                    |  Worker   |     |  (State) |                           |
|                    +-----+-----+     +----------+                           |
|                          |                                                   |
|  RESPONSE LAYER          v                                                  |
|         +----------------+----------------+                                 |
|         v                v                v                                  |
|  +-------------+  +-------------+  +-------------+                          |
|  | Gmail API   |  | Twilio API  |  |  API/Email  |                          |
|  |  (Reply)    |  |  (Reply)    |  |  (Reply)    |                          |
|  +-------------+  +-------------+  +-------------+                          |
|                                                                              |
|  INFRASTRUCTURE                                                              |
|  +--------------------------------------------------------------+           |
|  |                    Kubernetes Cluster                         |           |
|  |  +--------+ +--------+ +--------+ +--------+                 |           |
|  |  |API Pod | |Worker 1| |Worker 2| |Worker N|  (Auto-Scale)   |           |
|  |  +--------+ +--------+ +--------+ +--------+                 |           |
|  +--------------------------------------------------------------+           |
+-----------------------------------------------------------------------------+
```

### Exercise 2.1: Database Schema - Your CRM System (2-3 hours)

```sql
-- schema.sql
-- =============================================================================
-- CUSTOMER SUCCESS FTE - CRM/TICKET MANAGEMENT SYSTEM
-- =============================================================================

-- Customers table (unified across channels) - YOUR CUSTOMER DATABASE
CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE,
    phone VARCHAR(50),
    name VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

-- Customer identifiers (for cross-channel matching)
CREATE TABLE customer_identifiers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID REFERENCES customers(id),
    identifier_type VARCHAR(50) NOT NULL, -- 'email', 'phone', 'whatsapp'
    identifier_value VARCHAR(255) NOT NULL,
    verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(identifier_type, identifier_value)
);

-- Conversations table
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID REFERENCES customers(id),
    initial_channel VARCHAR(50) NOT NULL, -- 'email', 'whatsapp', 'web_form'
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ended_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(50) DEFAULT 'active',
    sentiment_score DECIMAL(3,2),
    resolution_type VARCHAR(50),
    escalated_to VARCHAR(255),
    metadata JSONB DEFAULT '{}'
);

-- Messages table (with channel tracking)
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id),
    channel VARCHAR(50) NOT NULL, -- 'email', 'whatsapp', 'web_form'
    direction VARCHAR(20) NOT NULL, -- 'inbound', 'outbound'
    role VARCHAR(20) NOT NULL, -- 'customer', 'agent', 'system'
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    tokens_used INTEGER,
    latency_ms INTEGER,
    tool_calls JSONB DEFAULT '[]',
    channel_message_id VARCHAR(255), -- External ID (Gmail message ID, Twilio SID)
    delivery_status VARCHAR(50) DEFAULT 'pending'
);

-- Tickets table
CREATE TABLE tickets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id),
    customer_id UUID REFERENCES customers(id),
    source_channel VARCHAR(50) NOT NULL,
    category VARCHAR(100),
    priority VARCHAR(20) DEFAULT 'medium',
    status VARCHAR(50) DEFAULT 'open',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolution_notes TEXT
);

-- Knowledge base entries
CREATE TABLE knowledge_base (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    category VARCHAR(100),
    embedding VECTOR(1536), -- For semantic search
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Channel configurations
CREATE TABLE channel_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel VARCHAR(50) UNIQUE NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    config JSONB NOT NULL,
    response_template TEXT,
    max_response_length INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Agent performance metrics
CREATE TABLE agent_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_name VARCHAR(100) NOT NULL,
    metric_value DECIMAL(10,4) NOT NULL,
    channel VARCHAR(50),
    dimensions JSONB DEFAULT '{}',
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_customers_email ON customers(email);
CREATE INDEX idx_customer_identifiers_value ON customer_identifiers(identifier_value);
CREATE INDEX idx_conversations_customer ON conversations(customer_id);
CREATE INDEX idx_conversations_status ON conversations(status);
CREATE INDEX idx_conversations_channel ON conversations(initial_channel);
CREATE INDEX idx_messages_conversation ON messages(conversation_id);
CREATE INDEX idx_messages_channel ON messages(channel);
CREATE INDEX idx_tickets_status ON tickets(status);
CREATE INDEX idx_tickets_channel ON tickets(source_channel);
CREATE INDEX idx_knowledge_embedding ON knowledge_base USING ivfflat (embedding vector_cosine_ops);
```

### Exercise 2.2: Channel Integrations (4-5 hours)

#### Gmail Integration

```python
# channels/gmail_handler.py

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.cloud import pubsub_v1
import base64
import email
from email.mime.text import MIMEText
from datetime import datetime
import json

class GmailHandler:
    def __init__(self, credentials_path: str):
        self.credentials = Credentials.from_authorized_user_file(credentials_path)
        self.service = build('gmail', 'v1', credentials=self.credentials)

    async def setup_push_notifications(self, topic_name: str):
        """Set up Gmail push notifications via Pub/Sub."""
        request = {
            'labelIds': ['INBOX'],
            'topicName': topic_name,
            'labelFilterAction': 'include'
        }
        return self.service.users().watch(userId='me', body=request).execute()

    async def process_notification(self, pubsub_message: dict) -> dict:
        """Process incoming Pub/Sub notification from Gmail."""
        history_id = pubsub_message.get('historyId')

        history = self.service.users().history().list(
            userId='me',
            startHistoryId=history_id,
            historyTypes=['messageAdded']
        ).execute()

        messages = []
        for record in history.get('history', []):
            for msg_added in record.get('messagesAdded', []):
                msg_id = msg_added['message']['id']
                message = await self.get_message(msg_id)
                messages.append(message)

        return messages

    async def get_message(self, message_id: str) -> dict:
        """Fetch and parse a Gmail message."""
        msg = self.service.users().messages().get(
            userId='me',
            id=message_id,
            format='full'
        ).execute()

        headers = {h['name']: h['value'] for h in msg['payload']['headers']}
        body = self._extract_body(msg['payload'])

        return {
            'channel': 'email',
            'channel_message_id': message_id,
            'customer_email': self._extract_email(headers.get('From', '')),
            'subject': headers.get('Subject', ''),
            'content': body,
            'received_at': datetime.utcnow().isoformat(),
            'thread_id': msg.get('threadId'),
            'metadata': {
                'headers': headers,
                'labels': msg.get('labelIds', [])
            }
        }

    async def send_reply(self, to_email: str, subject: str, body: str, thread_id: str = None) -> dict:
        """Send email reply."""
        message = MIMEText(body)
        message['to'] = to_email
        message['subject'] = f"Re: {subject}" if not subject.startswith('Re:') else subject

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')

        send_request = {'raw': raw}
        if thread_id:
            send_request['threadId'] = thread_id

        result = self.service.users().messages().send(
            userId='me',
            body=send_request
        ).execute()

        return {
            'channel_message_id': result['id'],
            'delivery_status': 'sent'
        }
```

#### WhatsApp Integration (via Twilio)

```python
# channels/whatsapp_handler.py

from twilio.rest import Client
from twilio.request_validator import RequestValidator
from fastapi import Request, HTTPException
import os
from datetime import datetime

class WhatsAppHandler:
    def __init__(self):
        self.account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        self.auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        self.whatsapp_number = os.getenv('TWILIO_WHATSAPP_NUMBER')
        self.client = Client(self.account_sid, self.auth_token)
        self.validator = RequestValidator(self.auth_token)

    async def validate_webhook(self, request: Request) -> bool:
        """Validate incoming Twilio webhook signature."""
        signature = request.headers.get('X-Twilio-Signature', '')
        url = str(request.url)
        form_data = await request.form()
        params = dict(form_data)
        return self.validator.validate(url, params, signature)

    async def process_webhook(self, form_data: dict) -> dict:
        """Process incoming WhatsApp message from Twilio webhook."""
        return {
            'channel': 'whatsapp',
            'channel_message_id': form_data.get('MessageSid'),
            'customer_phone': form_data.get('From', '').replace('whatsapp:', ''),
            'content': form_data.get('Body', ''),
            'received_at': datetime.utcnow().isoformat(),
            'metadata': {
                'num_media': form_data.get('NumMedia', '0'),
                'profile_name': form_data.get('ProfileName'),
                'wa_id': form_data.get('WaId'),
                'status': form_data.get('SmsStatus')
            }
        }

    async def send_message(self, to_phone: str, body: str) -> dict:
        """Send WhatsApp message via Twilio."""
        if not to_phone.startswith('whatsapp:'):
            to_phone = f'whatsapp:{to_phone}'

        message = self.client.messages.create(
            body=body,
            from_=self.whatsapp_number,
            to=to_phone
        )

        return {
            'channel_message_id': message.sid,
            'delivery_status': message.status
        }
```

#### Web Support Form (Required Build)

```python
# channels/web_form_handler.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, validator
from datetime import datetime
from typing import Optional
import uuid

router = APIRouter(prefix="/support", tags=["support-form"])

class SupportFormSubmission(BaseModel):
    name: str
    email: EmailStr
    subject: str
    category: str  # 'general', 'technical', 'billing', 'feedback'
    message: str
    priority: Optional[str] = 'medium'
    attachments: Optional[list[str]] = []

    @validator('name')
    def name_must_not_be_empty(cls, v):
        if not v or len(v.strip()) < 2:
            raise ValueError('Name must be at least 2 characters')
        return v.strip()

    @validator('message')
    def message_must_have_content(cls, v):
        if not v or len(v.strip()) < 10:
            raise ValueError('Message must be at least 10 characters')
        return v.strip()

    @validator('category')
    def category_must_be_valid(cls, v):
        valid_categories = ['general', 'technical', 'billing', 'feedback', 'bug_report']
        if v not in valid_categories:
            raise ValueError(f'Category must be one of: {valid_categories}')
        return v

class SupportFormResponse(BaseModel):
    ticket_id: str
    message: str
    estimated_response_time: str

@router.post("/submit", response_model=SupportFormResponse)
async def submit_support_form(submission: SupportFormSubmission):
    ticket_id = str(uuid.uuid4())

    message_data = {
        'channel': 'web_form',
        'channel_message_id': ticket_id,
        'customer_email': submission.email,
        'customer_name': submission.name,
        'subject': submission.subject,
        'content': submission.message,
        'category': submission.category,
        'priority': submission.priority,
        'received_at': datetime.utcnow().isoformat(),
        'metadata': {
            'form_version': '1.0',
            'attachments': submission.attachments
        }
    }

    await publish_to_kafka('fte.tickets.incoming', message_data)
    await create_ticket_record(ticket_id, message_data)

    return SupportFormResponse(
        ticket_id=ticket_id,
        message="Thank you for contacting us! Our AI assistant will respond shortly.",
        estimated_response_time="Usually within 5 minutes"
    )
```

**React/Next.js Web Support Form Component (Required):**

```jsx
// web-form/SupportForm.jsx

import React, { useState } from 'react';

const CATEGORIES = [
  { value: 'general', label: 'General Question' },
  { value: 'technical', label: 'Technical Support' },
  { value: 'billing', label: 'Billing Inquiry' },
  { value: 'bug_report', label: 'Bug Report' },
  { value: 'feedback', label: 'Feedback' }
];

const PRIORITIES = [
  { value: 'low', label: 'Low - Not urgent' },
  { value: 'medium', label: 'Medium - Need help soon' },
  { value: 'high', label: 'High - Urgent issue' }
];

export default function SupportForm({ apiEndpoint = '/api/support/submit' }) {
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    subject: '',
    category: 'general',
    priority: 'medium',
    message: ''
  });

  const [status, setStatus] = useState('idle');
  const [ticketId, setTicketId] = useState(null);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setStatus('submitting');

    try {
      const response = await fetch(apiEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
      });

      const data = await response.json();
      setTicketId(data.ticket_id);
      setStatus('success');
    } catch (err) {
      setError(err.message);
      setStatus('error');
    }
  };

  // ... render form with fields: name, email, subject, category, priority, message
}
```

### Exercise 2.3: OpenAI Agents SDK Implementation (4-5 hours)

```python
# agent/customer_success_agent.py

from openai import OpenAI
from agents import Agent, Runner, function_tool
from pydantic import BaseModel
from typing import Optional
from enum import Enum
import asyncpg
from datetime import datetime

class Channel(str, Enum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    WEB_FORM = "web_form"

class KnowledgeSearchInput(BaseModel):
    query: str
    max_results: int = 5

class TicketInput(BaseModel):
    customer_id: str
    issue: str
    priority: str = "medium"
    category: Optional[str] = None
    channel: Channel

class EscalationInput(BaseModel):
    ticket_id: str
    reason: str
    urgency: str = "normal"

class ResponseInput(BaseModel):
    ticket_id: str
    message: str
    channel: Channel

@function_tool
async def search_knowledge_base(input: KnowledgeSearchInput) -> str:
    """Search product documentation for relevant information."""
    # ... implementation

@function_tool
async def create_ticket(input: TicketInput) -> str:
    """Create a support ticket for tracking. ALWAYS create at conversation start."""
    # ... implementation

@function_tool
async def get_customer_history(customer_id: str) -> str:
    """Get customer's complete interaction history across ALL channels."""
    # ... implementation

@function_tool
async def escalate_to_human(input: EscalationInput) -> str:
    """Escalate conversation to human support."""
    # ... implementation

@function_tool
async def send_response(input: ResponseInput) -> str:
    """Send response to customer via their preferred channel."""
    # ... implementation

customer_success_agent = Agent(
    name="Customer Success FTE",
    model="gpt-4o",
    instructions="""You are a Customer Success agent for TechCorp SaaS.

## Channel Awareness
- **Email**: Formal, detailed responses. Include proper greeting and signature.
- **WhatsApp**: Concise, conversational. Keep responses under 300 characters when possible.
- **Web Form**: Semi-formal, helpful. Balance detail with readability.

## Core Behaviors
1. ALWAYS create a ticket at conversation start (include channel!)
2. Check customer history ACROSS ALL CHANNELS before responding
3. Search knowledge base before answering product questions
4. Be concise on WhatsApp, detailed on email
5. Monitor sentiment - escalate if customer becomes frustrated

## Hard Constraints
- NEVER discuss pricing - escalate immediately
- NEVER promise features not in documentation
- NEVER process refunds - escalate to billing
- ALWAYS use send_response tool to reply (ensures proper channel formatting)

## Escalation Triggers
- Customer mentions "lawyer", "legal", or "sue"
- Customer uses profanity or aggressive language
- Cannot find relevant information after 2 searches
- Customer explicitly requests human help
- WhatsApp customer sends 'human' or 'agent'
""",
    tools=[
        search_knowledge_base,
        create_ticket,
        get_customer_history,
        escalate_to_human,
        send_response
    ],
)
```

### Exercise 2.4: Unified Message Processor (3-4 hours)

```python
# workers/message_processor.py

import asyncio
from kafka_client import FTEKafkaConsumer, FTEKafkaProducer, TOPICS
from agent.customer_success_agent import customer_success_agent, Channel
from channels.gmail_handler import GmailHandler
from channels.whatsapp_handler import WhatsAppHandler
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class UnifiedMessageProcessor:
    """Process incoming messages from all channels through the FTE agent."""

    def __init__(self):
        self.gmail = GmailHandler()
        self.whatsapp = WhatsAppHandler()
        self.producer = FTEKafkaProducer()

    async def start(self):
        await self.producer.start()
        consumer = FTEKafkaConsumer(
            topics=[TOPICS['tickets_incoming']],
            group_id='fte-message-processor'
        )
        await consumer.start()
        await consumer.consume(self.process_message)

    async def process_message(self, topic: str, message: dict):
        """Process a single incoming message from any channel."""
        try:
            start_time = datetime.utcnow()
            channel = Channel(message['channel'])
            customer_id = await self.resolve_customer(message)
            conversation_id = await self.get_or_create_conversation(
                customer_id=customer_id,
                channel=channel,
                message=message
            )

            history = await self.load_conversation_history(conversation_id)

            result = await customer_success_agent.run(
                messages=history,
                context={
                    'customer_id': customer_id,
                    'conversation_id': conversation_id,
                    'channel': channel.value,
                    'ticket_subject': message.get('subject', 'Support Request'),
                    'metadata': message.get('metadata', {})
                }
            )

            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.info(f"Processed {channel.value} message in {latency_ms:.0f}ms")

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            await self.handle_error(message, e)

async def main():
    processor = UnifiedMessageProcessor()
    await processor.start()

if __name__ == "__main__":
    asyncio.run(main())
```

### Exercise 2.5: Kafka Event Streaming (2-3 hours)

```python
# kafka_client.py

from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
import json
from datetime import datetime
import os

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")

TOPICS = {
    'tickets_incoming': 'fte.tickets.incoming',
    'email_inbound': 'fte.channels.email.inbound',
    'whatsapp_inbound': 'fte.channels.whatsapp.inbound',
    'webform_inbound': 'fte.channels.webform.inbound',
    'email_outbound': 'fte.channels.email.outbound',
    'whatsapp_outbound': 'fte.channels.whatsapp.outbound',
    'escalations': 'fte.escalations',
    'metrics': 'fte.metrics',
    'dlq': 'fte.dlq'
}
```

### Exercise 2.6: FastAPI Service with Channel Endpoints (3-4 hours)

```python
# api/main.py

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Customer Success FTE API",
    description="24/7 AI-powered customer support across Email, WhatsApp, and Web",
    version="2.0.0"
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)

# Endpoints:
# GET  /health                        - Health check with channel status
# POST /webhooks/gmail                - Gmail push notification handler
# POST /webhooks/whatsapp             - Twilio WhatsApp webhook
# POST /webhooks/whatsapp/status      - WhatsApp delivery status
# POST /support/submit                - Web form submission
# GET  /support/ticket/{ticket_id}    - Ticket status
# GET  /conversations/{id}            - Conversation history
# GET  /customers/lookup              - Customer lookup by email/phone
# GET  /metrics/channels              - Channel-specific metrics
```

### Exercise 2.7: Kubernetes Deployment (4-5 hours)

Key manifests to create:
- `k8s/namespace.yaml` - Namespace: `customer-success-fte`
- `k8s/configmap.yaml` - Environment config (Kafka, Postgres, channel settings)
- `k8s/secrets.yaml` - API keys (OpenAI, Twilio, Gmail credentials)
- `k8s/deployment-api.yaml` - API pods (3 replicas, auto-scale to 20)
- `k8s/deployment-worker.yaml` - Message processor pods (3 replicas, auto-scale to 30)
- `k8s/service.yaml` - ClusterIP service
- `k8s/ingress.yaml` - Nginx ingress with TLS
- `k8s/hpa.yaml` - HPA targeting 70% CPU utilization

---

## Part 3: Integration & Testing (Hours 41-48)

### Exercise 3.1: Multi-Channel E2E Testing (3-4 hours)

```python
# tests/test_multichannel_e2e.py

class TestWebFormChannel:
    """Test the web support form (required build)."""
    async def test_form_submission(self, client): ...
    async def test_form_validation(self, client): ...
    async def test_ticket_status_retrieval(self, client): ...

class TestEmailChannel:
    """Test Gmail integration."""
    async def test_gmail_webhook_processing(self, client): ...

class TestWhatsAppChannel:
    """Test WhatsApp/Twilio integration."""
    async def test_whatsapp_webhook_processing(self, client): ...

class TestCrossChannelContinuity:
    """Test that conversations persist across channels."""
    async def test_customer_history_across_channels(self, client): ...

class TestChannelMetrics:
    """Test channel-specific metrics."""
    async def test_metrics_by_channel(self, client): ...
```

### Exercise 3.2: Load Testing (2-3 hours)

```python
# tests/load_test.py

from locust import HttpUser, task, between

class WebFormUser(HttpUser):
    wait_time = between(2, 10)
    weight = 3  # Web form is most common

    @task
    def submit_support_form(self):
        self.client.post("/support/submit", json={...})

class HealthCheckUser(HttpUser):
    wait_time = between(5, 15)
    weight = 1

    @task
    def check_health(self): self.client.get("/health")

    @task
    def check_metrics(self): self.client.get("/metrics/channels")
```

---

## Deliverables Checklist

### Stage 1: Incubation Deliverables
* [ ] Working prototype handling customer queries from any channel
* [ ] specs/discovery-log.md - Requirements discovered during exploration
* [ ] specs/customer-success-fte-spec.md - Crystallized specification
* [ ] MCP server with 5+ tools (including channel-aware tools)
* [ ] Agent skills manifest defining capabilities
* [ ] Channel-specific response templates
* [ ] Test dataset of 20+ edge cases per channel

### Stage 2: Specialization Deliverables
* [ ] PostgreSQL schema with multi-channel support
* [ ] OpenAI Agents SDK implementation with channel-aware tools
* [ ] FastAPI service with all channel endpoints
* [ ] Gmail integration (webhook handler + send)
* [ ] WhatsApp/Twilio integration (webhook handler + send)
* [ ] **Web Support Form (REQUIRED)** - Complete React component in Next.js
* [ ] Kafka event streaming with channel-specific topics
* [ ] Kubernetes manifests for deployment
* [ ] Monitoring configuration

### Stage 3: Integration Deliverables
* [ ] Multi-channel E2E test suite passing
* [ ] Load test results showing 24/7 readiness
* [ ] Documentation for deployment and operations
* [ ] Runbook for incident response

---

## Scoring Rubric

### Technical Implementation (50 points)

| Criteria | Points | Requirements |
| :---- | :---- | :---- |
| Incubation Quality | 10 | Discovery log shows iterative exploration; multi-channel patterns found |
| Agent Implementation | 10 | All tools work; channel-aware responses; proper error handling |
| **Web Support Form** | 10 | **Complete React/Next.js form with validation, submission, and status checking** |
| Channel Integrations | 10 | Gmail + WhatsApp handlers work; proper webhook validation |
| Database & Kafka | 5 | Normalized schema; channel tracking; event streaming works |
| Kubernetes Deployment | 5 | All manifests work; multi-pod scaling; health checks passing |

### Operational Excellence (25 points)

| Criteria | Points | Requirements |
| :---- | :---- | :---- |
| 24/7 Readiness | 10 | Survives pod restarts; handles scaling; no single points of failure |
| Cross-Channel Continuity | 10 | Customer identified across channels; history preserved |
| Monitoring | 5 | Channel-specific metrics; alerts configured |

### Business Value (15 points)

| Criteria | Points | Requirements |
| :---- | :---- | :---- |
| Customer Experience | 10 | Channel-appropriate responses; proper escalation; sentiment handling |
| Documentation | 5 | Clear deployment guide; API documentation; form integration guide |

### Innovation (10 points)

| Criteria | Points | Requirements |
| :---- | :---- | :---- |
| Creative Solutions | 5 | Novel approaches; enhanced UX on web form |
| Evolution Demonstration | 5 | Clear progression from incubation to specialization |

---

## Resources

### Required Reading
* Agent Maturity Model - Core framework
* OpenAI Agents SDK Documentation: https://platform.openai.com/docs/agents
* Model Context Protocol Specification: https://modelcontextprotocol.io/
* Gmail API Documentation: https://developers.google.com/gmail/api
* Twilio WhatsApp API: https://www.twilio.com/docs/whatsapp

### Recommended Tools
* **Development:** Claude Code, VS Code, Docker Desktop
* **Database/CRM:** PostgreSQL 16 with pgvector extension (this IS your CRM)
* **Streaming:** Apache Kafka (use Confluent Cloud for simplicity)
* **Kubernetes:** minikube (local) or any cloud provider
* **Email:** Gmail API with Pub/Sub
* **WhatsApp:** Twilio WhatsApp Sandbox (for development)

### What You Don't Need
* External CRM (Salesforce, HubSpot, etc.) - PostgreSQL is your CRM
* Full website - Only the support form component
* Production WhatsApp Business account - Twilio Sandbox is sufficient

---

## FAQ

**Q: Do I need to integrate with Salesforce, HubSpot, or another CRM?**
A: No. The PostgreSQL database you build IS your CRM system.

**Q: Do I need real Gmail and WhatsApp accounts?**
A: For development, use Gmail API sandbox and Twilio WhatsApp Sandbox.

**Q: Is the entire website required?**
A: No. Only the Web Support Form component is required.

**Q: How do I test WhatsApp without Twilio costs?**
A: Twilio provides a free WhatsApp Sandbox.

**Q: Can I skip a channel?**
A: The Web Support Form is **required**. Gmail and WhatsApp integrations are expected but partial implementations are acceptable with documented limitations.

---

## Final Challenge: The 24-Hour Multi-Channel Test

After deployment, your FTE must survive a **24-hour continuous operation test** across all channels:

1. **Web Form Traffic:** 100+ submissions over 24 hours
2. **Email Simulation:** 50+ Gmail messages processed
3. **WhatsApp Simulation:** 50+ WhatsApp messages processed
4. **Cross-Channel:** 10+ customers contact via multiple channels
5. **Chaos Testing:** Random pod kills every 2 hours

**Metrics Validation:**
- Uptime > 99.9%
- P95 latency < 3 seconds (all channels)
- Escalation rate < 25%
- Cross-channel customer identification > 95%
- No message loss

Teams that pass the 24-hour multi-channel test have built a **true omnichannel Digital FTE**.

---

**Welcome to the future of customer support. Now build it.**
