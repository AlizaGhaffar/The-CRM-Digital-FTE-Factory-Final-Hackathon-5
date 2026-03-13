"""
production/database/queries.py
All database access functions for the Customer Success FTE.
Uses asyncpg for async PostgreSQL access.

Usage:
    from production.database.queries import (
        find_or_create_customer,
        create_ticket,
        search_knowledge_base,
        ...
    )
"""

import asyncpg
import json
import os
import logging
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Connection Pool ────────────────────────────────────────────────────────
_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    """Get or create the shared connection pool."""
    global _pool
    if _pool is None:
        dsn = os.getenv("DATABASE_URL")
        if dsn:
            _pool = await asyncpg.create_pool(
                dsn=dsn,
                min_size=2,
                max_size=10,
                command_timeout=30,
            )
        else:
            _pool = await asyncpg.create_pool(
                host=os.getenv("POSTGRES_HOST", "localhost"),
                port=int(os.getenv("POSTGRES_PORT", 5432)),
                database=os.getenv("POSTGRES_DB", "fte_db"),
                user=os.getenv("POSTGRES_USER", "fte_user"),
                password=os.getenv("POSTGRES_PASSWORD", "changeme"),
                ssl="require",
                min_size=2,
                max_size=10,
                command_timeout=30,
            )
    return _pool


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


# ── Customers ──────────────────────────────────────────────────────────────

async def find_or_create_customer(
    email: Optional[str] = None,
    phone: Optional[str] = None,
    name: Optional[str] = None,
    channel: str = "web_form",
) -> str:
    """
    Find existing customer by email or phone, or create a new one.
    Returns unified customer_id (UUID string).
    Uses the DB-layer fn_find_or_create_customer() stored function.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        customer_id = await conn.fetchval(
            "SELECT fn_find_or_create_customer($1, $2, $3, $4)",
            email, phone, name, channel,
        )
        return str(customer_id)


async def get_customer_by_id(customer_id: str) -> Optional[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM customers WHERE id = $1",
            customer_id,
        )
        return dict(row) if row else None


async def get_customer_summary(customer_id: str) -> Optional[dict]:
    """Full 360-degree customer summary via DB function."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.fetchval(
            "SELECT fn_get_customer_summary($1)", customer_id
        )
        return result  # Already JSONB dict


async def get_customer_history(customer_id: str, limit: int = 5) -> list[dict]:
    """
    Get summarised recent tickets for cross-channel context.
    Returns last `limit` tickets with topic + status.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                t.id,
                t.subject,
                t.category,
                t.status,
                t.source_channel,
                t.priority,
                t.created_at,
                t.escalation_reason
            FROM tickets t
            WHERE t.customer_id = $1
            ORDER BY t.created_at DESC
            LIMIT $2
            """,
            customer_id, limit,
        )
        return [dict(r) for r in rows]


# ── Conversations ──────────────────────────────────────────────────────────

async def get_or_create_conversation(
    customer_id: str,
    channel: str,
) -> str:
    """
    Get active conversation (last 24h) or create a new one.
    Returns conversation_id (UUID string).
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Check for existing active conversation
        existing = await conn.fetchval(
            "SELECT fn_get_active_conversation($1, $2)",
            customer_id, channel,
        )
        if existing:
            return str(existing)

        # Create new conversation
        conv_id = await conn.fetchval(
            """
            INSERT INTO conversations
                (customer_id, initial_channel, current_channel, status)
            VALUES ($1, $2, $2, 'active')
            RETURNING id
            """,
            customer_id, channel,
        )
        return str(conv_id)


async def update_conversation_sentiment(
    conversation_id: str,
    sentiment_score: float,
    sentiment_trend: Optional[str] = None,
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE conversations
            SET sentiment_score = $1, sentiment_trend = $2
            WHERE id = $3
            """,
            sentiment_score, sentiment_trend, conversation_id,
        )


async def close_conversation(
    conversation_id: str,
    status: str = "resolved",
    resolution_type: Optional[str] = None,
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE conversations
            SET status = $1, resolution_type = $2, ended_at = NOW()
            WHERE id = $3
            """,
            status, resolution_type, conversation_id,
        )


async def load_conversation_history(conversation_id: str) -> list[dict]:
    """Load messages as {role, content} list for agent context."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT role, content, channel, direction, created_at, tool_calls
            FROM messages
            WHERE conversation_id = $1
            ORDER BY created_at ASC
            """,
            conversation_id,
        )
        return [
            {"role": r["role"], "content": r["content"]}
            for r in rows
        ]


# ── Messages ───────────────────────────────────────────────────────────────

async def store_message(
    conversation_id: str,
    channel: str,
    direction: str,
    role: str,
    content: str,
    channel_message_id: Optional[str] = None,
    thread_id: Optional[str] = None,
    tokens_used: Optional[int] = None,
    latency_ms: Optional[int] = None,
    tool_calls: Optional[list] = None,
    sentiment_score: Optional[float] = None,
    delivery_status: str = "pending",
) -> str:
    """Insert a message and return its ID."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        msg_id = await conn.fetchval(
            """
            INSERT INTO messages (
                conversation_id, channel, direction, role, content,
                channel_message_id, thread_id, tokens_used, latency_ms,
                tool_calls, sentiment_score, delivery_status
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
            RETURNING id
            """,
            conversation_id, channel, direction, role, content,
            channel_message_id, thread_id, tokens_used, latency_ms,
            json.dumps(tool_calls or []), sentiment_score, delivery_status,
        )
        return str(msg_id)


async def update_message_delivery(
    channel_message_id: str,
    delivery_status: str,
    delivered_at: Optional[datetime] = None,
    error: Optional[str] = None,
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE messages
            SET delivery_status = $1,
                delivered_at = $2,
                delivery_error = $3
            WHERE channel_message_id = $4
            """,
            delivery_status, delivered_at, error, channel_message_id,
        )


# ── Tickets ────────────────────────────────────────────────────────────────

async def create_ticket(
    customer_id: str,
    source_channel: str,
    conversation_id: Optional[str] = None,
    subject: Optional[str] = None,
    category: Optional[str] = None,
    priority: str = "medium",
) -> str:
    """Create a support ticket. SLA breach time auto-computed by DB trigger."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        ticket_id = await conn.fetchval(
            """
            INSERT INTO tickets
                (customer_id, conversation_id, source_channel,
                 subject, category, priority, status)
            VALUES ($1,$2,$3,$4,$5,$6,'open')
            RETURNING id
            """,
            customer_id, conversation_id, source_channel,
            subject, category, priority,
        )
        return str(ticket_id)


async def update_ticket_status(
    ticket_id: str,
    status: str,
    escalation_reason: Optional[str] = None,
    escalation_urgency: Optional[str] = None,
    escalated_to: Optional[str] = None,
    resolution_notes: Optional[str] = None,
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE tickets SET
                status             = $1,
                escalation_reason  = COALESCE($2, escalation_reason),
                escalation_urgency = COALESCE($3, escalation_urgency),
                escalated_to       = COALESCE($4, escalated_to),
                resolution_notes   = COALESCE($5, resolution_notes)
            WHERE id = $6
            """,
            status, escalation_reason, escalation_urgency,
            escalated_to, resolution_notes, ticket_id,
        )


async def get_ticket(ticket_id: str) -> Optional[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT t.*, c.email AS customer_email, c.name AS customer_name,
                   c.phone AS customer_phone
            FROM tickets t
            JOIN customers c ON c.id = t.customer_id
            WHERE t.id = $1
            """,
            ticket_id,
        )
        return dict(row) if row else None


async def get_open_tickets(limit: int = 50) -> list[dict]:
    """Fetch open tickets ordered by priority + SLA breach time."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM v_open_tickets
            LIMIT $1
            """,
            limit,
        )
        return [dict(r) for r in rows]


# ── Knowledge Base ─────────────────────────────────────────────────────────

async def search_knowledge_base(
    embedding: list[float],
    max_results: int = 5,
    min_similarity: float = 0.7,
    category: Optional[str] = None,
) -> list[dict]:
    """
    Vector similarity search using pgvector cosine distance.
    embedding: list of 1536 floats from OpenAI text-embedding-3-small.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Register pgvector type codec
        await conn.execute("SET LOCAL enable_seqscan = OFF;")  # Force index use

        rows = await conn.fetch(
            """
            SELECT * FROM fn_search_knowledge_base($1::vector, $2, $3, $4)
            """,
            embedding, max_results, min_similarity, category,
        )
        return [dict(r) for r in rows]


async def upsert_knowledge_base_entry(
    title: str,
    content: str,
    embedding: list[float],
    category: Optional[str] = None,
    source_doc: Optional[str] = None,
    chunk_index: int = 0,
    tags: Optional[list[str]] = None,
) -> str:
    """Insert or update a KB entry. Uses content hash for dedup."""
    import hashlib
    content_hash = hashlib.sha256(content.encode()).hexdigest()

    pool = await get_pool()
    async with pool.acquire() as conn:
        kb_id = await conn.fetchval(
            """
            INSERT INTO knowledge_base
                (title, content, content_hash, embedding, category,
                 source_doc, chunk_index, tags)
            VALUES ($1,$2,$3,$4::vector,$5,$6,$7,$8)
            ON CONFLICT (id) DO UPDATE SET
                title        = EXCLUDED.title,
                content      = EXCLUDED.content,
                content_hash = EXCLUDED.content_hash,
                embedding    = EXCLUDED.embedding,
                updated_at   = NOW()
            RETURNING id
            """,
            title, content, content_hash, embedding, category,
            source_doc, chunk_index, tags or [],
        )
        return str(kb_id)


# ── Escalations ────────────────────────────────────────────────────────────

async def create_escalation(
    ticket_id: str,
    customer_id: str,
    reason: str,
    urgency: str = "normal",
    conversation_id: Optional[str] = None,
    routed_to: Optional[str] = None,
    source_channel: Optional[str] = None,
    trigger_message: Optional[str] = None,
    sentiment_at_escalation: Optional[float] = None,
) -> str:
    """Log an escalation event. SLA target auto-set by DB trigger."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        esc_id = await conn.fetchval(
            """
            INSERT INTO escalations (
                ticket_id, customer_id, conversation_id, reason,
                urgency, routed_to, source_channel,
                trigger_message, sentiment_at_escalation
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
            RETURNING id
            """,
            ticket_id, customer_id, conversation_id, reason,
            urgency, routed_to, source_channel,
            trigger_message, sentiment_at_escalation,
        )
        return str(esc_id)


# ── Metrics ────────────────────────────────────────────────────────────────

async def record_metric(
    metric_name: str,
    metric_value: float,
    channel: Optional[str] = None,
    ticket_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    dimensions: Optional[dict] = None,
):
    """Record a single metric event (fire-and-forget, non-blocking)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO agent_metrics
                (metric_name, metric_value, channel, ticket_id,
                 conversation_id, dimensions)
            VALUES ($1,$2,$3,$4,$5,$6)
            """,
            metric_name, metric_value, channel, ticket_id,
            conversation_id, json.dumps(dimensions or {}),
        )


async def get_channel_summary() -> list[dict]:
    """Get last 24h channel performance summary."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM v_channel_daily_summary")
        return [dict(r) for r in rows]


# ── Channel Config ─────────────────────────────────────────────────────────

async def get_channel_config(channel: str) -> Optional[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM channel_configs WHERE channel = $1 AND enabled = TRUE",
            channel,
        )
        return dict(row) if row else None
