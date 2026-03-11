"""
Exercise 1.3 — Conversation Memory
src/agent/memory.py

In-memory state store for the incubation phase prototype.
Field names and types mirror the production PostgreSQL schema exactly
(production/database/schema.sql) so this swaps for asyncpg calls in Stage 2.

Key design decisions:
  - Email is the primary customer identifier (matches customers.email UNIQUE)
  - Phone is secondary; a customer with both gets one unified record
  - customer_identifiers table logic is reproduced via _identifier_index dict
  - channel_switches mirrors conversations.channel_switches JSONB []
  - sentiment_trend is computed from the rolling per-message history
  - All public functions match the interface of production/database/queries.py

Run demo:
    python src/agent/memory.py
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ACTIVE_CONVERSATION_WINDOW_HOURS = 24  # reuse conversation within this window
SENTIMENT_TREND_THRESHOLD = 0.08       # delta required to call a trend improving/declining
SENTIMENT_HISTORY_WINDOW = 3           # messages to average for trend calculation


# ---------------------------------------------------------------------------
# Dataclasses — mirror production schema column-for-column
# ---------------------------------------------------------------------------

@dataclass
class CustomerProfile:
    """
    Mirrors: customers + customer_identifiers tables.
    email is the primary cross-channel identifier.
    phone is the E.164 secondary identifier (used for WhatsApp).
    """
    customer_id: str                     # UUID
    email: Optional[str]                 # PRIMARY identifier
    phone: Optional[str]                 # E.164, e.g. +14155551234
    name: str
    preferred_channel: str = "web_form"  # most-used channel
    lifetime_tickets: int = 0
    open_tickets: int = 0
    last_contact_at: Optional[str] = None
    last_channel: Optional[str] = None
    plan: Optional[str] = None           # starter/growth/business/enterprise
    company: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: _now())
    # Mirrors customer_identifiers rows: identifier_value -> identifier_type
    identifiers: dict[str, str] = field(default_factory=dict)


@dataclass
class MessageRecord:
    """
    Mirrors: messages table.
    One row per inbound or outbound message.
    """
    message_id: str
    conversation_id: str
    channel: str           # email | whatsapp | web_form
    direction: str         # inbound | outbound
    role: str              # customer | agent | system | human_agent
    content: str
    sentiment_score: Optional[float] = None
    tokens_used: Optional[int] = None
    latency_ms: Optional[int] = None
    tool_calls: list[dict] = field(default_factory=list)
    kb_results_used: int = 0
    channel_message_id: Optional[str] = None
    thread_id: Optional[str] = None
    delivery_status: str = "pending"
    created_at: str = field(default_factory=lambda: _now())


@dataclass
class TicketRecord:
    """
    Mirrors: tickets table.
    One row per support issue.
    """
    ticket_id: str
    customer_id: str
    conversation_id: Optional[str]
    source_channel: str
    subject: Optional[str] = None
    category: Optional[str] = None       # general|technical|billing|bug_report|feedback|security
    priority: str = "medium"             # low|medium|high|critical
    status: str = "open"                 # open|in_progress|responded|escalated|resolved|closed
    escalation_reason: Optional[str] = None
    escalation_urgency: Optional[str] = None
    escalated_to: Optional[str] = None
    resolution_notes: Optional[str] = None
    created_at: str = field(default_factory=lambda: _now())
    resolved_at: Optional[str] = None


@dataclass
class ConversationContext:
    """
    Mirrors: conversations table + embedded MessageRecord list.
    A ConversationContext is the agent's working memory for one support session.
    topics is prototype-only (production equivalent lives in ticket.subject).
    """
    conversation_id: str
    customer_id: str

    # Channel tracking — mirrors conversations.initial_channel / current_channel / channel_switches
    initial_channel: str
    current_channel: str
    channel_switches: list[dict] = field(default_factory=list)  # [{from, to, switched_at}]

    # Lifecycle — mirrors conversations.status
    status: str = "active"              # active|waiting|responded|resolved|escalated|closed
    started_at: str = field(default_factory=lambda: _now())
    ended_at: Optional[str] = None

    # Quality signals — mirrors conversations.sentiment_score / sentiment_trend
    sentiment_score: Optional[float] = None
    sentiment_trend: Optional[str] = None   # improving|stable|declining
    _sentiment_history: list[float] = field(default_factory=list)  # rolling per-message scores

    # Counters — mirrors conversations.message_count / agent_turns
    message_count: int = 0
    agent_turns: int = 0

    # Resolution — mirrors conversations.resolution_type
    resolution_type: Optional[str] = None  # self_service|escalated|abandoned|timeout

    # Topics discussed (prototype; production: summarised in ticket.subject)
    topics: list[str] = field(default_factory=list)

    # Embedded records (not in conversations table — joined from messages + tickets)
    messages: list[MessageRecord] = field(default_factory=list)
    ticket_ids: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


def _hours_ago(iso_ts: str) -> float:
    """Return how many hours ago an ISO timestamp was."""
    try:
        dt = datetime.fromisoformat(iso_ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt
        return delta.total_seconds() / 3600
    except Exception:
        return float("inf")


def _compute_sentiment_trend(history: list[float], new_score: float) -> str:
    """
    Compare new_score to rolling average of last SENTIMENT_HISTORY_WINDOW scores.
    Returns 'improving', 'declining', or 'stable'.
    """
    if not history:
        return "stable"
    window = history[-SENTIMENT_HISTORY_WINDOW:]
    avg = sum(window) / len(window)
    delta = new_score - avg
    if delta >= SENTIMENT_TREND_THRESHOLD:
        return "improving"
    if delta <= -SENTIMENT_TREND_THRESHOLD:
        return "declining"
    return "stable"


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _normalize_phone(phone: str) -> str:
    """Strip spaces and normalise E.164. Leaves + prefix."""
    return "".join(c for c in phone if c.isdigit() or c == "+")


# ---------------------------------------------------------------------------
# MemoryStore — the single in-memory state container
# ---------------------------------------------------------------------------

class MemoryStore:
    """
    In-memory CRM state store. Interface mirrors production/database/queries.py.

    Internals:
      _customers        : customer_id  -> CustomerProfile
      _identifier_index : identifier_value (normalised) -> customer_id
                          Reproduces the customer_identifiers table lookup.
      _conversations    : conversation_id -> ConversationContext
      _active_convs     : customer_id -> conversation_id  (most recent active)
      _tickets          : ticket_id -> TicketRecord
    """

    def __init__(self) -> None:
        self._customers: dict[str, CustomerProfile] = {}
        self._identifier_index: dict[str, str] = {}   # value -> customer_id
        self._conversations: dict[str, ConversationContext] = {}
        self._active_convs: dict[str, str] = {}        # customer_id -> conv_id
        self._tickets: dict[str, TicketRecord] = {}

    # ------------------------------------------------------------------
    # Identity resolution
    # ------------------------------------------------------------------

    def _register_identifier(
        self, customer_id: str, value: str, id_type: str
    ) -> None:
        """
        Register an identifier in the index. Mirrors INSERT INTO customer_identifiers.
        Does not overwrite an existing mapping to a different customer.
        """
        norm = value.strip().lower()
        if norm and norm not in self._identifier_index:
            self._identifier_index[norm] = customer_id
            profile = self._customers[customer_id]
            profile.identifiers[norm] = id_type

    def resolve_customer_id(self, identifier_value: str) -> Optional[str]:
        """
        Look up customer_id by any known identifier (email or phone).
        Mirrors: SELECT customer_id FROM customer_identifiers WHERE identifier_value = $1
        """
        return self._identifier_index.get(identifier_value.strip().lower())

    # ------------------------------------------------------------------
    # Customers — mirrors find_or_create_customer() in queries.py
    # ------------------------------------------------------------------

    def find_or_create_customer(
        self,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        name: str = "",
        channel: str = "web_form",
    ) -> CustomerProfile:
        """
        Find existing customer by email (primary) or phone (secondary).
        Creates a new unified record if neither is found.
        Merges identifiers if a match is found via only one of them.

        Email is always the primary identifier per schema design.
        """
        norm_email = _normalize_email(email) if email else None
        norm_phone = _normalize_phone(phone) if phone else None

        # 1. Try email first (primary identifier)
        customer_id = None
        if norm_email:
            customer_id = self._identifier_index.get(norm_email)

        # 2. Fall back to phone if email didn't match
        if not customer_id and norm_phone:
            customer_id = self._identifier_index.get(norm_phone)

        if customer_id and customer_id in self._customers:
            profile = self._customers[customer_id]
            # Merge any new identifiers we just learned about
            if norm_email and norm_email not in profile.identifiers:
                self._register_identifier(customer_id, norm_email, "email")
                profile.email = profile.email or norm_email
            if norm_phone and norm_phone not in profile.identifiers:
                self._register_identifier(customer_id, norm_phone, "phone")
                profile.phone = profile.phone or norm_phone
            # Update name if we now know it
            if name and not profile.name:
                profile.name = name
            return profile

        # 3. Create new customer
        customer_id = _new_id()
        profile = CustomerProfile(
            customer_id=customer_id,
            email=norm_email,
            phone=norm_phone,
            name=name or "",
            preferred_channel=channel,
        )
        self._customers[customer_id] = profile

        if norm_email:
            self._register_identifier(customer_id, norm_email, "email")
        if norm_phone:
            self._register_identifier(customer_id, norm_phone, "phone")

        return profile

    def get_customer(self, customer_id: str) -> Optional[CustomerProfile]:
        return self._customers.get(customer_id)

    # ------------------------------------------------------------------
    # Conversations — mirrors get_or_create_conversation() in queries.py
    # ------------------------------------------------------------------

    def get_or_create_conversation(
        self,
        customer_id: str,
        channel: str,
    ) -> ConversationContext:
        """
        Return the active conversation if one exists within ACTIVE_CONVERSATION_WINDOW_HOURS,
        otherwise create a new one.
        If the customer contacts on a different channel, record a channel switch
        and update current_channel — the conversation_id stays the same.

        Mirrors: SELECT fn_get_active_conversation($1, $2) then INSERT INTO conversations.
        """
        existing_id = self._active_convs.get(customer_id)
        if existing_id and existing_id in self._conversations:
            conv = self._conversations[existing_id]
            if (
                conv.status in ("active", "waiting", "responded")
                and _hours_ago(conv.started_at) < ACTIVE_CONVERSATION_WINDOW_HOURS
            ):
                # Channel switch?
                if conv.current_channel != channel:
                    self._record_channel_switch(conv, conv.current_channel, channel)
                return conv

        # Create new conversation
        conv_id = _new_id()
        conv = ConversationContext(
            conversation_id=conv_id,
            customer_id=customer_id,
            initial_channel=channel,
            current_channel=channel,
        )
        self._conversations[conv_id] = conv
        self._active_convs[customer_id] = conv_id
        return conv

    def get_conversation(self, conversation_id: str) -> Optional[ConversationContext]:
        return self._conversations.get(conversation_id)

    def _record_channel_switch(
        self, conv: ConversationContext, from_channel: str, to_channel: str
    ) -> None:
        """
        Record a channel switch event.
        Mirrors: conversations.channel_switches JSONB append.
        """
        switch = {"from": from_channel, "to": to_channel, "switched_at": _now()}
        conv.channel_switches.append(switch)
        conv.current_channel = to_channel
        print(
            f"  [memory] channel switch: {from_channel} -> {to_channel} "
            f"(conv={conv.conversation_id[:8]})"
        )

    def close_conversation(
        self,
        conversation_id: str,
        status: str = "resolved",
        resolution_type: Optional[str] = None,
    ) -> None:
        """
        Mirrors: UPDATE conversations SET status=$1, resolution_type=$2, ended_at=NOW().
        """
        conv = self._conversations.get(conversation_id)
        if conv:
            conv.status = status
            conv.resolution_type = resolution_type
            conv.ended_at = _now()

    # ------------------------------------------------------------------
    # Sentiment — mirrors update_conversation_sentiment() in queries.py
    # ------------------------------------------------------------------

    def update_sentiment(
        self, conversation_id: str, score: float
    ) -> Optional[str]:
        """
        Update per-conversation sentiment score and compute trend.
        Returns the new trend string, or None if conversation not found.

        Mirrors: UPDATE conversations SET sentiment_score=$1, sentiment_trend=$2.
        """
        conv = self._conversations.get(conversation_id)
        if not conv:
            return None

        trend = _compute_sentiment_trend(conv._sentiment_history, score)
        conv._sentiment_history.append(score)
        conv.sentiment_score = score
        conv.sentiment_trend = trend
        return trend

    # ------------------------------------------------------------------
    # Topics — prototype only (production: ticket.subject)
    # ------------------------------------------------------------------

    def add_topic(self, conversation_id: str, topic: str) -> None:
        """
        Record a topic discussed in this conversation.
        De-duplicates by checking if a similar topic is already tracked.
        """
        conv = self._conversations.get(conversation_id)
        if not conv:
            return
        topic = topic.strip()
        if topic and topic.lower() not in [t.lower() for t in conv.topics]:
            conv.topics.append(topic)

    # ------------------------------------------------------------------
    # Messages — mirrors store_message() in queries.py
    # ------------------------------------------------------------------

    def add_message(
        self,
        conversation_id: str,
        channel: str,
        direction: str,   # inbound | outbound
        role: str,        # customer | agent | system | human_agent
        content: str,
        sentiment_score: Optional[float] = None,
        tokens_used: Optional[int] = None,
        latency_ms: Optional[int] = None,
        tool_calls: Optional[list] = None,
        kb_results_used: int = 0,
        channel_message_id: Optional[str] = None,
        thread_id: Optional[str] = None,
    ) -> MessageRecord:
        """
        Store one message and update conversation counters + sentiment.
        Mirrors: INSERT INTO messages (...) RETURNING id.
        """
        conv = self._conversations.get(conversation_id)
        record = MessageRecord(
            message_id=_new_id(),
            conversation_id=conversation_id,
            channel=channel,
            direction=direction,
            role=role,
            content=content,
            sentiment_score=sentiment_score,
            tokens_used=tokens_used,
            latency_ms=latency_ms,
            tool_calls=tool_calls or [],
            kb_results_used=kb_results_used,
            channel_message_id=channel_message_id,
            thread_id=thread_id,
        )
        if conv:
            conv.messages.append(record)
            conv.message_count += 1
            if role == "agent":
                conv.agent_turns += 1
            if sentiment_score is not None:
                self.update_sentiment(conversation_id, sentiment_score)

        return record

    def get_conversation_history(
        self, conversation_id: str, limit: int = 20
    ) -> list[dict]:
        """
        Return messages as [{role, content}] list for agent context window.
        Mirrors: SELECT role, content FROM messages WHERE conversation_id=$1 ORDER BY created_at ASC.
        """
        conv = self._conversations.get(conversation_id)
        if not conv:
            return []
        msgs = conv.messages[-limit:]
        return [{"role": m.role, "content": m.content} for m in msgs]

    # ------------------------------------------------------------------
    # Tickets — mirrors create_ticket() / update_ticket_status() in queries.py
    # ------------------------------------------------------------------

    def create_ticket(
        self,
        customer_id: str,
        conversation_id: Optional[str],
        source_channel: str,
        subject: Optional[str] = None,
        category: Optional[str] = None,
        priority: str = "medium",
        ticket_id: Optional[str] = None,
    ) -> TicketRecord:
        """
        Create a support ticket and link it to the conversation.
        Mirrors: INSERT INTO tickets (...) RETURNING id.
        ticket_id may be supplied externally (e.g. from core.py's NF-XXXX).
        """
        tid = ticket_id or f"NF-{uuid.uuid4().hex[:8].upper()}"
        record = TicketRecord(
            ticket_id=tid,
            customer_id=customer_id,
            conversation_id=conversation_id,
            source_channel=source_channel,
            subject=subject,
            category=category,
            priority=priority,
        )
        self._tickets[tid] = record

        # Update conversation
        if conversation_id:
            conv = self._conversations.get(conversation_id)
            if conv and tid not in conv.ticket_ids:
                conv.ticket_ids.append(tid)

        # Update customer counters
        profile = self._customers.get(customer_id)
        if profile:
            profile.lifetime_tickets += 1
            profile.open_tickets += 1
            profile.last_contact_at = record.created_at
            profile.last_channel = source_channel

        return record

    def update_ticket(
        self,
        ticket_id: str,
        status: str,
        escalation_reason: Optional[str] = None,
        escalation_urgency: Optional[str] = None,
        escalated_to: Optional[str] = None,
        resolution_notes: Optional[str] = None,
    ) -> None:
        """
        Mirrors: UPDATE tickets SET status=$1 ... WHERE id=$6.
        """
        record = self._tickets.get(ticket_id)
        if not record:
            return
        prev_status = record.status
        record.status = status
        if escalation_reason:
            record.escalation_reason = escalation_reason
        if escalation_urgency:
            record.escalation_urgency = escalation_urgency
        if escalated_to:
            record.escalated_to = escalated_to
        if resolution_notes:
            record.resolution_notes = resolution_notes
        if status == "resolved" and not record.resolved_at:
            record.resolved_at = _now()

        # Update customer's open_tickets counter
        if prev_status not in ("resolved", "closed") and status in ("resolved", "closed"):
            profile = self._customers.get(record.customer_id)
            if profile and profile.open_tickets > 0:
                profile.open_tickets -= 1

    def get_ticket(self, ticket_id: str) -> Optional[TicketRecord]:
        return self._tickets.get(ticket_id)

    def get_customer_tickets(
        self, customer_id: str, limit: int = 10
    ) -> list[TicketRecord]:
        """
        Mirrors: SELECT ... FROM tickets WHERE customer_id=$1 ORDER BY created_at DESC.
        """
        tickets = [
            t for t in self._tickets.values()
            if t.customer_id == customer_id
        ]
        tickets.sort(key=lambda t: t.created_at, reverse=True)
        return tickets[:limit]

    # ------------------------------------------------------------------
    # Context summary — used to inject history into agent prompts
    # ------------------------------------------------------------------

    def build_agent_context(self, customer_id: str) -> dict:
        """
        Assemble a rich context summary for the agent prompt.
        This is the 'memory' the agent sees at the start of each turn.

        Equivalent of: SELECT fn_get_customer_summary($1) in production.
        """
        profile = self._customers.get(customer_id)
        if not profile:
            return {"found": False}

        # Active conversation
        conv_id = self._active_convs.get(customer_id)
        conv = self._conversations.get(conv_id) if conv_id else None

        # Recent tickets (last 5)
        recent_tickets = self.get_customer_tickets(customer_id, limit=5)

        # Recent message history for context window
        history: list[dict] = []
        if conv:
            history = self.get_conversation_history(conv.conversation_id, limit=10)

        return {
            "found": True,
            "customer": {
                "customer_id": profile.customer_id,
                "email": profile.email,
                "phone": profile.phone,
                "name": profile.name,
                "plan": profile.plan,
                "company": profile.company,
                "preferred_channel": profile.preferred_channel,
                "lifetime_tickets": profile.lifetime_tickets,
                "open_tickets": profile.open_tickets,
                "last_contact_at": profile.last_contact_at,
                "last_channel": profile.last_channel,
                "tags": profile.tags,
            },
            "conversation": {
                "conversation_id": conv.conversation_id if conv else None,
                "status": conv.status if conv else None,
                "current_channel": conv.current_channel if conv else None,
                "initial_channel": conv.initial_channel if conv else None,
                "channel_switches": conv.channel_switches if conv else [],
                "sentiment_score": conv.sentiment_score if conv else None,
                "sentiment_trend": conv.sentiment_trend if conv else None,
                "message_count": conv.message_count if conv else 0,
                "topics": conv.topics if conv else [],
                "started_at": conv.started_at if conv else None,
            },
            "recent_tickets": [
                {
                    "ticket_id": t.ticket_id,
                    "subject": t.subject,
                    "category": t.category,
                    "status": t.status,
                    "source_channel": t.source_channel,
                    "priority": t.priority,
                    "escalation_reason": t.escalation_reason,
                    "created_at": t.created_at,
                }
                for t in recent_tickets
            ],
            "message_history": history,
            "is_repeat_contact": profile.lifetime_tickets > 1,
        }

    # ------------------------------------------------------------------
    # Convenience: full pipeline helper
    # ------------------------------------------------------------------

    def process_inbound(
        self,
        email: Optional[str],
        phone: Optional[str],
        name: str,
        channel: str,
        message_body: str,
        subject: str = "",
        sentiment_score: Optional[float] = None,
        ticket_id: Optional[str] = None,
    ) -> tuple[CustomerProfile, ConversationContext, TicketRecord]:
        """
        Single call that:
          1. Resolves or creates the customer (email as primary)
          2. Gets or creates the conversation (handles channel switches)
          3. Records the inbound message
          4. Creates a ticket
          5. Updates sentiment if provided

        Returns (profile, conversation, ticket) for downstream use.
        """
        # 1. Customer
        profile = self.find_or_create_customer(
            email=email, phone=phone, name=name, channel=channel
        )

        # 2. Conversation
        conv = self.get_or_create_conversation(profile.customer_id, channel)

        # 3. Message
        self.add_message(
            conversation_id=conv.conversation_id,
            channel=channel,
            direction="inbound",
            role="customer",
            content=message_body,
            sentiment_score=sentiment_score,
        )

        # 4. Ticket
        ticket = self.create_ticket(
            customer_id=profile.customer_id,
            conversation_id=conv.conversation_id,
            source_channel=channel,
            subject=subject or message_body[:80],
            ticket_id=ticket_id,
        )

        return profile, conv, ticket


# ---------------------------------------------------------------------------
# Module-level default store instance
# ---------------------------------------------------------------------------

store = MemoryStore()


# Public API (matches queries.py function signatures for easy swap)

def find_or_create_customer(
    email: Optional[str] = None,
    phone: Optional[str] = None,
    name: str = "",
    channel: str = "web_form",
) -> CustomerProfile:
    return store.find_or_create_customer(email=email, phone=phone, name=name, channel=channel)


def resolve_customer_id(identifier_value: str) -> Optional[str]:
    return store.resolve_customer_id(identifier_value)


def get_or_create_conversation(customer_id: str, channel: str) -> ConversationContext:
    return store.get_or_create_conversation(customer_id, channel)


def add_message(
    conversation_id: str,
    channel: str,
    direction: str,
    role: str,
    content: str,
    sentiment_score: Optional[float] = None,
    **kwargs,
) -> MessageRecord:
    return store.add_message(
        conversation_id, channel, direction, role, content, sentiment_score, **kwargs
    )


def add_topic(conversation_id: str, topic: str) -> None:
    store.add_topic(conversation_id, topic)


def update_sentiment(conversation_id: str, score: float) -> Optional[str]:
    return store.update_sentiment(conversation_id, score)


def close_conversation(
    conversation_id: str,
    status: str = "resolved",
    resolution_type: Optional[str] = None,
) -> None:
    store.close_conversation(conversation_id, status, resolution_type)


def create_ticket(
    customer_id: str,
    conversation_id: Optional[str],
    source_channel: str,
    subject: Optional[str] = None,
    category: Optional[str] = None,
    priority: str = "medium",
    ticket_id: Optional[str] = None,
) -> TicketRecord:
    return store.create_ticket(
        customer_id, conversation_id, source_channel, subject, category, priority, ticket_id
    )


def update_ticket(ticket_id: str, status: str, **kwargs) -> None:
    store.update_ticket(ticket_id, status, **kwargs)


def build_agent_context(customer_id: str) -> dict:
    return store.build_agent_context(customer_id)


def process_inbound(
    email: Optional[str],
    phone: Optional[str],
    name: str,
    channel: str,
    message_body: str,
    subject: str = "",
    sentiment_score: Optional[float] = None,
    ticket_id: Optional[str] = None,
) -> tuple[CustomerProfile, ConversationContext, TicketRecord]:
    return store.process_inbound(
        email, phone, name, channel, message_body, subject, sentiment_score, ticket_id
    )


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

def _demo() -> None:
    """
    Simulate a multi-turn, multi-channel conversation showing all six features.
    """
    s = MemoryStore()

    print("=" * 65)
    print("DEMO: Exercise 1.3 — Conversation Memory")
    print("=" * 65)

    # 1. First contact via email
    print("\n--- Turn 1: Email contact ---")
    p, conv1, t1 = s.process_inbound(
        email="alex@startupco.io",
        phone=None,
        name="Alex Morgan",
        channel="email",
        message_body="I can't log in, my account seems locked.",
        subject="Account locked",
        sentiment_score=0.25,
        ticket_id="NF-T001",
    )
    s.add_topic(conv1.conversation_id, "account login / locked")
    s.add_message(
        conv1.conversation_id, "email", "outbound", "agent",
        "Account locked after 10 failed attempts. Auto-unlocks in 30 minutes. "
        "Contact support for immediate unlock.",
        latency_ms=310,
    )
    s.update_ticket("NF-T001", "responded")
    print(f"  customer_id  : {p.customer_id[:8]}...")
    print(f"  conv_id      : {conv1.conversation_id[:8]}...")
    print(f"  sentiment    : {conv1.sentiment_score} ({conv1.sentiment_trend})")
    print(f"  topics       : {conv1.topics}")

    # 2. Same customer, same session — now via WhatsApp (channel switch)
    print("\n--- Turn 2: WhatsApp follow-up (channel switch) ---")
    p2, conv2, t2 = s.process_inbound(
        email=None,
        phone="+14155559201",
        name="Alex",
        channel="whatsapp",
        message_body="still cant get in",
        sentiment_score=0.2,
        ticket_id="NF-T002",
    )
    # Link phone to the same customer we already know via email
    # (in production, customer_identifiers handles this; here we simulate by
    #  first registering the phone against the known customer_id)
    s._register_identifier(p.customer_id, "+14155559201", "phone")

    # Re-run get_or_create with resolved id
    conv_wa = s.get_or_create_conversation(p.customer_id, "whatsapp")
    s.add_message(
        conv_wa.conversation_id, "whatsapp", "inbound", "customer",
        "still cant get in", sentiment_score=0.2
    )
    s.add_topic(conv_wa.conversation_id, "account locked — follow-up")

    print(f"  same conv_id : {conv_wa.conversation_id == conv1.conversation_id}")
    print(f"  channel_switches: {conv_wa.channel_switches}")
    print(f"  current_channel : {conv_wa.current_channel}")
    print(f"  sentiment trend : {conv_wa.sentiment_trend}")

    # 3. Resolution
    print("\n--- Turn 3: Issue resolved ---")
    s.add_message(
        conv_wa.conversation_id, "whatsapp", "outbound", "agent",
        "Your account has been manually unlocked. You can now log in.",
        latency_ms=250,
    )
    s.update_ticket("NF-T001", "resolved", resolution_notes="Manual unlock applied")
    s.close_conversation(conv_wa.conversation_id, "resolved", "self_service")

    # 4. New session — a different issue (billing), email again
    print("\n--- Turn 4: New session — billing question ---")
    import time; time.sleep(0.01)  # ensure new started_at
    conv_new = s.get_or_create_conversation(p.customer_id, "email")
    # conv_wa is closed so a new one should be created
    # (force close so window check works)
    conv_wa.status = "resolved"
    conv_new2 = s.get_or_create_conversation(p.customer_id, "email")
    s.add_message(
        conv_new2.conversation_id, "email", "inbound", "customer",
        "How do I upgrade to the Business plan?", sentiment_score=0.7
    )
    t3 = s.create_ticket(
        p.customer_id, conv_new2.conversation_id, "email",
        subject="Upgrade to Business plan", category="billing"
    )
    s.add_topic(conv_new2.conversation_id, "plan upgrade — billing")

    # 5. Build full agent context
    print("\n--- Agent context (what the agent sees) ---")
    ctx = s.build_agent_context(p.customer_id)
    print(f"  is_repeat_contact : {ctx['is_repeat_contact']}")
    print(f"  lifetime_tickets  : {ctx['customer']['lifetime_tickets']}")
    print(f"  open_tickets      : {ctx['customer']['open_tickets']}")
    print(f"  last_channel      : {ctx['customer']['last_channel']}")
    print(f"  recent_tickets    : {[t['ticket_id'] for t in ctx['recent_tickets']]}")
    print(f"  conv topics       : {ctx['conversation']['topics']}")
    print(f"  sentiment_score   : {ctx['conversation']['sentiment_score']}")

    print("\n✅ Demo complete — all six memory features exercised.")


if __name__ == "__main__":
    _demo()
