-- ============================================================
-- NimbusFlow Customer Success FTE
-- PostgreSQL Schema v2.0 — Complete CRM / Ticket System
-- ============================================================
-- This database IS your CRM. It replaces Salesforce/HubSpot
-- for this hackathon. Tables: customers, customer_identifiers,
-- conversations, messages, tickets, knowledge_base,
-- channel_configs, agent_metrics, escalations.
--
-- Run:
--   psql -U fte_user -d fte_db -f schema.sql
-- Or via Docker:
--   docker-compose exec postgres psql -U fte_user -d fte_db -f /docker-entrypoint-initdb.d/01-schema.sql
-- ============================================================

-- ============================================================
-- EXTENSIONS
-- ============================================================
CREATE EXTENSION IF NOT EXISTS vector;          -- pgvector: VECTOR(1536) semantic search
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";     -- uuid_generate_v4()
CREATE EXTENSION IF NOT EXISTS pg_trgm;         -- Trigram indexes for ILIKE searches
CREATE EXTENSION IF NOT EXISTS btree_gin;       -- GIN indexes on scalar types

-- ============================================================
-- SCHEMA MIGRATIONS TRACKER
-- Tracks which migration files have been applied.
-- ============================================================
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     VARCHAR(50) PRIMARY KEY,
    applied_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    description TEXT
);

INSERT INTO schema_migrations (version, description)
VALUES ('v2.0.0', 'Initial schema — full CRM + ticket system')
ON CONFLICT (version) DO NOTHING;

-- ============================================================
-- TABLE 1: customers
-- Unified customer record across ALL channels.
-- Primary identifier: email (preferred). Secondary: phone.
-- ============================================================
CREATE TABLE IF NOT EXISTS customers (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity
    email               VARCHAR(255) UNIQUE,                    -- Primary identifier
    phone               VARCHAR(50),                            -- E.164 format: +14155551234
    name                VARCHAR(255),

    -- Computed CRM fields (updated by triggers)
    preferred_channel   VARCHAR(50)  DEFAULT 'web_form'         -- Most-used channel
                        CHECK (preferred_channel IN ('email', 'whatsapp', 'web_form')),
    lifetime_tickets    INTEGER      DEFAULT 0,                  -- Total tickets ever created
    open_tickets        INTEGER      DEFAULT 0,                  -- Currently open tickets
    last_contact_at     TIMESTAMP WITH TIME ZONE,               -- Last inbound message timestamp
    last_channel        VARCHAR(50)                             -- Channel of last contact
                        CHECK (last_channel IN ('email', 'whatsapp', 'web_form', NULL)),

    -- CRM metadata
    plan                VARCHAR(50),                            -- 'starter', 'growth', 'business', 'enterprise'
    company             VARCHAR(255),
    tags                TEXT[]       DEFAULT '{}',              -- e.g. ['vip', 'at-risk', 'churned']

    -- Timestamps
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Flexible extra data (channel-specific metadata, UTM, etc.)
    metadata            JSONB        DEFAULT '{}'

    -- At least one identifier must be present
    -- Enforced in application layer (email OR phone required)
);

COMMENT ON TABLE  customers                  IS 'Unified customer records across all channels. This is the CRM customer database.';
COMMENT ON COLUMN customers.email            IS 'Primary cross-channel identifier. Shared between email and web_form channels.';
COMMENT ON COLUMN customers.phone            IS 'E.164 format. Used as WhatsApp identifier (strip whatsapp: prefix).';
COMMENT ON COLUMN customers.preferred_channel IS 'Channel with the most interactions. Updated by trigger.';
COMMENT ON COLUMN customers.lifetime_tickets IS 'Total tickets created across all channels. Updated by trigger.';

-- ============================================================
-- TABLE 2: customer_identifiers
-- Cross-channel identity resolution table.
-- Allows one customer to be recognised across email, WhatsApp, web.
-- ============================================================
CREATE TABLE IF NOT EXISTS customer_identifiers (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id      UUID        NOT NULL REFERENCES customers(id) ON DELETE CASCADE,

    identifier_type  VARCHAR(50) NOT NULL
                     CHECK (identifier_type IN ('email', 'phone', 'whatsapp', 'web_session')),

    identifier_value VARCHAR(255) NOT NULL,    -- e.g. '+14155551234', 'user@co.com'

    verified         BOOLEAN     DEFAULT FALSE,
    primary_id       BOOLEAN     DEFAULT FALSE, -- Is this the primary identifier for this type?
    source_channel   VARCHAR(50),               -- Channel where this identifier was first seen

    created_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(identifier_type, identifier_value)
);

COMMENT ON TABLE  customer_identifiers                  IS 'Maps channel-specific identifiers to a unified customer_id. Key for cross-channel continuity.';
COMMENT ON COLUMN customer_identifiers.identifier_type  IS 'Type: email, phone (E.164), whatsapp (+number), web_session (cookie/session ID).';
COMMENT ON COLUMN customer_identifiers.primary_id       IS 'True if this is the canonical identifier for this type (e.g. primary email).';

-- ============================================================
-- TABLE 3: conversations
-- One conversation = one support session.
-- A customer can have many conversations across channels.
-- Cross-channel: same conversation_id persists even if customer
-- switches from WhatsApp to email mid-session.
-- ============================================================
CREATE TABLE IF NOT EXISTS conversations (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id      UUID        NOT NULL REFERENCES customers(id) ON DELETE CASCADE,

    -- Channel tracking
    initial_channel  VARCHAR(50) NOT NULL
                     CHECK (initial_channel IN ('email', 'whatsapp', 'web_form')),
    current_channel  VARCHAR(50)
                     CHECK (current_channel IN ('email', 'whatsapp', 'web_form')),
    channel_switches JSONB       DEFAULT '[]',   -- Array of {from, to, switched_at}

    -- Lifecycle
    started_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ended_at         TIMESTAMP WITH TIME ZONE,
    status           VARCHAR(50) DEFAULT 'active'
                     CHECK (status IN ('active', 'waiting', 'responded', 'resolved', 'escalated', 'closed', 'abandoned')),

    -- Quality signals
    sentiment_score  DECIMAL(4,3)               -- Final sentiment: 0.000 – 1.000
                     CHECK (sentiment_score >= 0 AND sentiment_score <= 1),
    sentiment_trend  VARCHAR(20)                -- 'improving', 'stable', 'declining'
                     CHECK (sentiment_trend IN ('improving', 'stable', 'declining', NULL)),
    message_count    INTEGER     DEFAULT 0,      -- Updated by trigger on messages INSERT
    agent_turns      INTEGER     DEFAULT 0,      -- How many times the AI responded

    -- Resolution
    resolution_type  VARCHAR(50)
                     CHECK (resolution_type IN ('self_service', 'escalated', 'abandoned', 'timeout', NULL)),
    escalated_to     VARCHAR(255),               -- Team email or team name
    subject          TEXT,                       -- Summarised topic of conversation

    -- Timestamps
    created_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    metadata         JSONB       DEFAULT '{}'   -- Thread IDs, session data, etc.
);

COMMENT ON TABLE  conversations                  IS 'One support session per row. Tracks the full lifecycle of a customer interaction.';
COMMENT ON COLUMN conversations.channel_switches IS 'JSON array: [{from: "email", to: "whatsapp", switched_at: "ISO"}]. Enables omnichannel continuity reporting.';
COMMENT ON COLUMN conversations.sentiment_score  IS 'Final sentiment score at conversation close. 0=very negative, 1=very positive.';
COMMENT ON COLUMN conversations.message_count    IS 'Auto-incremented by trigger on messages INSERT.';

-- ============================================================
-- TABLE 4: messages
-- Every inbound and outbound message across all channels.
-- Complete audit trail of all AI and human interactions.
-- ============================================================
CREATE TABLE IF NOT EXISTS messages (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id     UUID        NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,

    -- Channel & direction
    channel             VARCHAR(50) NOT NULL
                        CHECK (channel IN ('email', 'whatsapp', 'web_form')),
    direction           VARCHAR(20) NOT NULL
                        CHECK (direction IN ('inbound', 'outbound')),
    role                VARCHAR(20) NOT NULL
                        CHECK (role IN ('customer', 'agent', 'system', 'human_agent')),

    -- Content
    content             TEXT        NOT NULL,
    content_type        VARCHAR(50) DEFAULT 'text'
                        CHECK (content_type IN ('text', 'html', 'markdown')),

    -- Per-message quality signals
    sentiment_score     DECIMAL(4,3)             -- Per-message sentiment (0–1)
                        CHECK (sentiment_score >= 0 AND sentiment_score <= 1),

    -- Performance metrics
    tokens_used         INTEGER,                 -- LLM tokens consumed
    latency_ms          INTEGER,                 -- Processing time in milliseconds
    tool_calls          JSONB       DEFAULT '[]', -- [{tool_name, input, output, duration_ms}]
    kb_results_used     INTEGER     DEFAULT 0,   -- How many KB results were used

    -- External channel identifiers
    channel_message_id  VARCHAR(255),            -- Gmail message ID / Twilio MessageSid
    thread_id           VARCHAR(255),            -- Gmail thread ID / WhatsApp conversation ID
    delivery_status     VARCHAR(50)  DEFAULT 'pending'
                        CHECK (delivery_status IN ('pending', 'queued', 'sent', 'delivered', 'read', 'failed')),
    delivery_error      TEXT,                    -- Error details if delivery_status = 'failed'

    -- Timestamps
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    delivered_at        TIMESTAMP WITH TIME ZONE,
    read_at             TIMESTAMP WITH TIME ZONE
);

COMMENT ON TABLE  messages                     IS 'Complete message log — every customer and agent message across all channels.';
COMMENT ON COLUMN messages.tool_calls          IS 'JSON array of agent tool calls: [{tool_name, input, output, duration_ms}]. Used for debugging and analytics.';
COMMENT ON COLUMN messages.channel_message_id  IS 'External system message ID. Gmail: message.id, Twilio: MessageSid.';
COMMENT ON COLUMN messages.latency_ms          IS 'End-to-end processing latency from message receipt to response send.';

-- ============================================================
-- TABLE 5: tickets
-- One ticket = one support issue.
-- A conversation can have multiple tickets (if topic changes).
-- ============================================================
CREATE TABLE IF NOT EXISTS tickets (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id     UUID        REFERENCES conversations(id) ON DELETE SET NULL,
    customer_id         UUID        NOT NULL REFERENCES customers(id) ON DELETE CASCADE,

    -- Channel provenance
    source_channel      VARCHAR(50) NOT NULL
                        CHECK (source_channel IN ('email', 'whatsapp', 'web_form')),

    -- Classification
    category            VARCHAR(100)
                        CHECK (category IN ('general', 'technical', 'billing', 'bug_report', 'feedback', 'security', 'enterprise')),
    subject             TEXT,
    priority            VARCHAR(20) DEFAULT 'medium'
                        CHECK (priority IN ('low', 'medium', 'high', 'critical')),

    -- Lifecycle
    status              VARCHAR(50) DEFAULT 'open'
                        CHECK (status IN ('open', 'in_progress', 'waiting_customer', 'responded', 'escalated', 'resolved', 'closed', 'spam')),

    -- SLA tracking
    sla_breach_at       TIMESTAMP WITH TIME ZONE,  -- Computed from priority + created_at
    first_response_at   TIMESTAMP WITH TIME ZONE,  -- When agent first responded
    resolved_at         TIMESTAMP WITH TIME ZONE,
    resolution_time_min INTEGER,                   -- Minutes to resolution (computed on close)

    -- Escalation details
    escalation_reason   VARCHAR(100),
    escalation_urgency  VARCHAR(20)
                        CHECK (escalation_urgency IN ('low', 'normal', 'high', 'critical', NULL)),
    escalated_to        VARCHAR(255),              -- Email or team name

    -- Resolution
    resolution_notes    TEXT,
    csat_score          SMALLINT                   -- Customer satisfaction: 1–5
                        CHECK (csat_score >= 1 AND csat_score <= 5),

    -- Timestamps
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE  tickets                   IS 'Support ticket per issue. This is the primary CRM work item. Tickets link customers to conversations and resolutions.';
COMMENT ON COLUMN tickets.sla_breach_at    IS 'Auto-computed on INSERT based on priority: critical=2h, high=4h, medium=8h, low=24h.';
COMMENT ON COLUMN tickets.resolution_time_min IS 'Auto-computed on status=resolved: (resolved_at - created_at) in minutes.';
COMMENT ON COLUMN tickets.csat_score       IS 'Customer satisfaction score 1–5 collected after resolution.';

-- ============================================================
-- TABLE 6: knowledge_base
-- Product documentation chunks for semantic search.
-- Embeddings generated by OpenAI text-embedding-3-small (1536d).
-- ============================================================
CREATE TABLE IF NOT EXISTS knowledge_base (
    id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Content
    title        VARCHAR(500) NOT NULL,
    content      TEXT         NOT NULL,
    content_hash VARCHAR(64),                 -- SHA-256 of content for dedup/change detection

    -- Classification
    category     VARCHAR(100),               -- 'getting_started', 'billing', 'api', 'integrations', etc.
    subcategory  VARCHAR(100),
    tags         TEXT[]       DEFAULT '{}',  -- e.g. ['password', 'login', 'security']
    source_doc   VARCHAR(255),               -- 'product-docs.md', 'faq.md', 'runbook.md'
    chunk_index  INTEGER      DEFAULT 0,     -- Position within source doc (for ordering)

    -- Vector embedding (OpenAI text-embedding-3-small = 1536 dims)
    embedding    VECTOR(1536),

    -- Usage analytics
    search_count    INTEGER DEFAULT 0,       -- How many times this chunk was retrieved
    helpful_count   INTEGER DEFAULT 0,       -- Positive feedback from resolution
    unhelpful_count INTEGER DEFAULT 0,       -- Negative feedback

    -- Timestamps
    created_at   TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at   TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE  knowledge_base           IS 'Chunked product documentation with vector embeddings for semantic search. This is the agent RAG store.';
COMMENT ON COLUMN knowledge_base.embedding IS 'OpenAI text-embedding-3-small output. 1536 dimensions. Used for cosine similarity search via pgvector.';
COMMENT ON COLUMN knowledge_base.content_hash IS 'SHA-256 of content field. Used to detect stale embeddings when docs change.';
COMMENT ON COLUMN knowledge_base.chunk_index  IS 'Order of this chunk within source_doc. Enables reassembling full sections.';

-- ============================================================
-- TABLE 7: channel_configs
-- Per-channel API keys, webhook URLs, and runtime settings.
-- Secrets are stored encrypted (encrypt at app layer, store here).
-- ============================================================
CREATE TABLE IF NOT EXISTS channel_configs (
    id                   UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    channel              VARCHAR(50)  UNIQUE NOT NULL
                         CHECK (channel IN ('email', 'whatsapp', 'web_form')),

    -- Status
    enabled              BOOLEAN      DEFAULT TRUE,
    health_status        VARCHAR(20)  DEFAULT 'unknown'
                         CHECK (health_status IN ('healthy', 'degraded', 'down', 'unknown')),
    last_health_check    TIMESTAMP WITH TIME ZONE,

    -- Channel-specific config (non-secret)
    config               JSONB        NOT NULL DEFAULT '{}',
    -- Gmail:     {"pub_sub_topic": "...", "label_ids": ["INBOX"], "user_id": "me"}
    -- WhatsApp:  {"from_number": "whatsapp:+14155238886", "max_message_length": 1600}
    -- Web Form:  {"cors_origins": ["https://app.nimbusflow.io"], "rate_limit_per_ip": 10}

    -- Encrypted secrets (encrypt with app-level key before INSERT, decrypt on read)
    -- Store as base64(encrypt(JSON)) — never store plaintext secrets
    secrets_encrypted    TEXT,
    -- Gmail:     {"credentials_json": "...", "token_json": "..."}
    -- WhatsApp:  {"account_sid": "...", "auth_token": "...", "webhook_secret": "..."}
    -- Web Form:  {"api_key": "..."}

    -- Response formatting
    response_template       TEXT,
    max_response_length     INTEGER,   -- Hard character limit per message
    response_style          VARCHAR(50) DEFAULT 'standard',
    -- 'standard', 'formal' (email), 'conversational' (whatsapp)

    -- Webhook settings
    webhook_url             TEXT,      -- Inbound webhook URL (for validation)
    webhook_secret          TEXT,      -- Signing secret for webhook validation (Twilio HMAC)

    -- Rate limiting
    rate_limit_per_minute   INTEGER    DEFAULT 60,
    rate_limit_per_day      INTEGER    DEFAULT 10000,

    -- Timestamps
    created_at              TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at              TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE  channel_configs                   IS 'Runtime configuration for each channel. config = non-secret settings. secrets_encrypted = AES-encrypted JSON of API keys.';
COMMENT ON COLUMN channel_configs.secrets_encrypted IS 'NEVER store plaintext. Encrypt at application layer with AES-256 before INSERT. Decrypt on SELECT in app.';
COMMENT ON COLUMN channel_configs.webhook_secret    IS 'Twilio webhook signing secret for HMAC-SHA256 signature validation. Stored encrypted.';

-- ============================================================
-- TABLE 8: agent_metrics
-- Time-series performance data for every agent action.
-- Used for dashboards, alerting, and daily reports.
-- ============================================================
CREATE TABLE IF NOT EXISTS agent_metrics (
    id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Metric identity
    metric_name   VARCHAR(100) NOT NULL,
    -- e.g. 'response_latency_ms', 'escalation_rate', 'kb_hit_rate',
    --      'message_processed', 'tool_call_count', 'sentiment_score',
    --      'token_cost_usd', 'delivery_failed'

    metric_value  DECIMAL(14,4) NOT NULL,

    -- Segmentation
    channel       VARCHAR(50)
                  CHECK (channel IN ('email', 'whatsapp', 'web_form', NULL)),
    ticket_id     UUID REFERENCES tickets(id) ON DELETE SET NULL,
    conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,

    -- Flexible dimensions for grouping/filtering
    dimensions    JSONB         DEFAULT '{}',
    -- e.g. {"priority": "high", "category": "billing", "escalated": true,
    --        "kb_results_count": 3, "model": "gpt-4o", "tool": "search_knowledge_base"}

    -- Timestamp (use for time-series queries)
    recorded_at   TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE  agent_metrics             IS 'Append-only time-series metrics. One row per metric event. Query with time_bucket() or date_trunc() for aggregations.';
COMMENT ON COLUMN agent_metrics.dimensions  IS 'JSONB bag for arbitrary segmentation dimensions. Indexed with GIN for flexible queries.';

-- ============================================================
-- TABLE 9: escalations
-- Audit log of every escalation event.
-- Separate from tickets to allow multiple escalations per ticket.
-- ============================================================
CREATE TABLE IF NOT EXISTS escalations (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id       UUID        NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    conversation_id UUID        REFERENCES conversations(id) ON DELETE SET NULL,
    customer_id     UUID        NOT NULL REFERENCES customers(id) ON DELETE CASCADE,

    -- Escalation classification
    reason          VARCHAR(100) NOT NULL,
    -- e.g. 'legal_threat', 'refund_request', 'security_incident',
    --      'sentiment_negative', 'repeat_contact', 'explicit_human_request',
    --      'data_loss', 'chargeback_threat', 'knowledge_gap', 'enterprise_sla'

    urgency         VARCHAR(20) NOT NULL DEFAULT 'normal'
                    CHECK (urgency IN ('low', 'normal', 'high', 'critical')),

    -- Routing
    routed_to       VARCHAR(255),  -- 'billing@nimbusflow.io', 'security@', 'technical'
    source_channel  VARCHAR(50)
                    CHECK (source_channel IN ('email', 'whatsapp', 'web_form', NULL)),

    -- SLA
    sla_target_at   TIMESTAMP WITH TIME ZONE,  -- When human must respond by
    sla_breached    BOOLEAN     DEFAULT FALSE,

    -- Resolution
    status          VARCHAR(50) DEFAULT 'open'
                    CHECK (status IN ('open', 'in_progress', 'resolved', 'closed')),
    notes           TEXT,
    resolution      TEXT,
    resolved_at     TIMESTAMP WITH TIME ZONE,
    resolved_by     VARCHAR(255),  -- Human agent who resolved

    -- Trigger context (for analysis)
    trigger_message TEXT,          -- The message that triggered escalation
    sentiment_at_escalation DECIMAL(4,3)
                    CHECK (sentiment_at_escalation >= 0 AND sentiment_at_escalation <= 1),

    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE  escalations          IS 'Audit log for every escalation. Enables SLA tracking, escalation pattern analysis, and human handoff management.';
COMMENT ON COLUMN escalations.reason   IS 'Specific trigger code. Used for pattern analysis and improving escalation thresholds.';
COMMENT ON COLUMN escalations.sla_target_at IS 'Computed from urgency: critical/high=2h, normal=4h, low=24h.';

-- ============================================================
-- INDEXES
-- ============================================================

-- ── customers ──────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_customers_email
    ON customers(email);
CREATE INDEX IF NOT EXISTS idx_customers_phone
    ON customers(phone);
CREATE INDEX IF NOT EXISTS idx_customers_last_contact
    ON customers(last_contact_at DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_customers_tags
    ON customers USING GIN(tags);                -- Array search
CREATE INDEX IF NOT EXISTS idx_customers_metadata
    ON customers USING GIN(metadata);            -- JSONB search

-- ── customer_identifiers ───────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_customer_identifiers_lookup
    ON customer_identifiers(identifier_type, identifier_value);
CREATE INDEX IF NOT EXISTS idx_customer_identifiers_customer
    ON customer_identifiers(customer_id);

-- ── conversations ──────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_conversations_customer
    ON conversations(customer_id);
CREATE INDEX IF NOT EXISTS idx_conversations_status
    ON conversations(status);
CREATE INDEX IF NOT EXISTS idx_conversations_channel
    ON conversations(initial_channel);
CREATE INDEX IF NOT EXISTS idx_conversations_started
    ON conversations(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversations_active
    ON conversations(customer_id, status)
    WHERE status = 'active';                     -- Partial: only active convos
CREATE INDEX IF NOT EXISTS idx_conversations_metadata
    ON conversations USING GIN(metadata);

-- ── messages ───────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_messages_conversation
    ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_channel
    ON messages(channel);
CREATE INDEX IF NOT EXISTS idx_messages_created
    ON messages(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_direction
    ON messages(direction);
CREATE INDEX IF NOT EXISTS idx_messages_delivery
    ON messages(delivery_status)
    WHERE delivery_status IN ('pending', 'failed');  -- Partial: actionable only
CREATE INDEX IF NOT EXISTS idx_messages_external_id
    ON messages(channel_message_id)
    WHERE channel_message_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_messages_tool_calls
    ON messages USING GIN(tool_calls);           -- JSONB search on tool usage

-- ── tickets ────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_tickets_customer
    ON tickets(customer_id);
CREATE INDEX IF NOT EXISTS idx_tickets_status
    ON tickets(status);
CREATE INDEX IF NOT EXISTS idx_tickets_channel
    ON tickets(source_channel);
CREATE INDEX IF NOT EXISTS idx_tickets_priority
    ON tickets(priority);
CREATE INDEX IF NOT EXISTS idx_tickets_created
    ON tickets(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tickets_open
    ON tickets(customer_id, status, priority)
    WHERE status IN ('open', 'in_progress', 'escalated');  -- Partial: open tickets
CREATE INDEX IF NOT EXISTS idx_tickets_sla
    ON tickets(sla_breach_at)
    WHERE status NOT IN ('resolved', 'closed');  -- Partial: only for SLA monitoring
CREATE INDEX IF NOT EXISTS idx_tickets_conversation
    ON tickets(conversation_id);

-- ── knowledge_base ─────────────────────────────────────────
-- Primary: IVFFlat approximate nearest-neighbor for cosine similarity
-- lists=100 is good for up to ~1M rows (sqrt(rows))
CREATE INDEX IF NOT EXISTS idx_knowledge_embedding_ivfflat
    ON knowledge_base USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Exact search fallback (use for < 10k rows or high-precision needs)
-- CREATE INDEX IF NOT EXISTS idx_knowledge_embedding_hnsw
--     ON knowledge_base USING hnsw (embedding vector_cosine_ops)
--     WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_knowledge_category
    ON knowledge_base(category);
CREATE INDEX IF NOT EXISTS idx_knowledge_tags
    ON knowledge_base USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_knowledge_source
    ON knowledge_base(source_doc, chunk_index);
CREATE INDEX IF NOT EXISTS idx_knowledge_title_trgm
    ON knowledge_base USING GIN(title gin_trgm_ops);   -- Fast ILIKE search on title

-- ── channel_configs ────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_channel_configs_channel
    ON channel_configs(channel);
CREATE INDEX IF NOT EXISTS idx_channel_configs_enabled
    ON channel_configs(enabled, channel);

-- ── agent_metrics ──────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_metrics_name
    ON agent_metrics(metric_name);
CREATE INDEX IF NOT EXISTS idx_metrics_channel
    ON agent_metrics(channel);
CREATE INDEX IF NOT EXISTS idx_metrics_recorded
    ON agent_metrics(recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_metrics_name_recorded
    ON agent_metrics(metric_name, recorded_at DESC);   -- Composite for time-series
CREATE INDEX IF NOT EXISTS idx_metrics_ticket
    ON agent_metrics(ticket_id)
    WHERE ticket_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_metrics_dimensions
    ON agent_metrics USING GIN(dimensions);

-- ── escalations ────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_escalations_ticket
    ON escalations(ticket_id);
CREATE INDEX IF NOT EXISTS idx_escalations_customer
    ON escalations(customer_id);
CREATE INDEX IF NOT EXISTS idx_escalations_status
    ON escalations(status);
CREATE INDEX IF NOT EXISTS idx_escalations_urgency
    ON escalations(urgency, status)
    WHERE status = 'open';                             -- Partial: open escalations only
CREATE INDEX IF NOT EXISTS idx_escalations_sla
    ON escalations(sla_target_at)
    WHERE status IN ('open', 'in_progress');           -- Partial: SLA monitoring

-- ============================================================
-- TRIGGERS
-- Auto-maintain updated_at and denormalized counters.
-- ============================================================

-- ── Generic updated_at trigger function ───────────────────
CREATE OR REPLACE FUNCTION fn_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply updated_at to all tables that have the column
CREATE OR REPLACE TRIGGER trg_customers_updated_at
    BEFORE UPDATE ON customers
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();

CREATE OR REPLACE TRIGGER trg_conversations_updated_at
    BEFORE UPDATE ON conversations
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();

CREATE OR REPLACE TRIGGER trg_tickets_updated_at
    BEFORE UPDATE ON tickets
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();

CREATE OR REPLACE TRIGGER trg_knowledge_base_updated_at
    BEFORE UPDATE ON knowledge_base
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();

CREATE OR REPLACE TRIGGER trg_channel_configs_updated_at
    BEFORE UPDATE ON channel_configs
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();

CREATE OR REPLACE TRIGGER trg_escalations_updated_at
    BEFORE UPDATE ON escalations
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();

-- ── Auto-increment conversations.message_count ─────────────
CREATE OR REPLACE FUNCTION fn_increment_message_count()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE conversations
    SET
        message_count = message_count + 1,
        -- Count only agent outbound turns
        agent_turns = CASE
            WHEN NEW.role = 'agent' AND NEW.direction = 'outbound'
            THEN agent_turns + 1
            ELSE agent_turns
        END,
        updated_at = NOW()
    WHERE id = NEW.conversation_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_messages_count
    AFTER INSERT ON messages
    FOR EACH ROW EXECUTE FUNCTION fn_increment_message_count();

-- ── Auto-compute ticket SLA breach time on INSERT ──────────
CREATE OR REPLACE FUNCTION fn_set_ticket_sla()
RETURNS TRIGGER AS $$
BEGIN
    NEW.sla_breach_at = NEW.created_at + CASE NEW.priority
        WHEN 'critical' THEN INTERVAL '2 hours'
        WHEN 'high'     THEN INTERVAL '4 hours'
        WHEN 'medium'   THEN INTERVAL '8 hours'
        WHEN 'low'      THEN INTERVAL '24 hours'
        ELSE                 INTERVAL '8 hours'
    END;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_tickets_sla
    BEFORE INSERT ON tickets
    FOR EACH ROW EXECUTE FUNCTION fn_set_ticket_sla();

-- ── Auto-compute resolution_time_min when ticket resolves ──
CREATE OR REPLACE FUNCTION fn_set_resolution_time()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status IN ('resolved', 'closed') AND OLD.status NOT IN ('resolved', 'closed') THEN
        NEW.resolved_at        = NOW();
        NEW.resolution_time_min = EXTRACT(EPOCH FROM (NOW() - NEW.created_at)) / 60;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_tickets_resolution
    BEFORE UPDATE ON tickets
    FOR EACH ROW EXECUTE FUNCTION fn_set_resolution_time();

-- ── Update customer denormalized fields on ticket INSERT ───
CREATE OR REPLACE FUNCTION fn_update_customer_on_ticket()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE customers
    SET
        lifetime_tickets = lifetime_tickets + 1,
        open_tickets     = open_tickets + 1,
        last_contact_at  = NEW.created_at,
        last_channel     = NEW.source_channel,
        updated_at       = NOW()
    WHERE id = NEW.customer_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_customers_ticket_count
    AFTER INSERT ON tickets
    FOR EACH ROW EXECUTE FUNCTION fn_update_customer_on_ticket();

-- ── Decrement open_tickets when ticket closes ──────────────
CREATE OR REPLACE FUNCTION fn_update_customer_on_ticket_close()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status IN ('resolved', 'closed') AND OLD.status NOT IN ('resolved', 'closed') THEN
        UPDATE customers
        SET
            open_tickets = GREATEST(0, open_tickets - 1),
            updated_at   = NOW()
        WHERE id = NEW.customer_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_customers_ticket_close
    AFTER UPDATE ON tickets
    FOR EACH ROW EXECUTE FUNCTION fn_update_customer_on_ticket_close();

-- ── Set escalation SLA target time ────────────────────────
CREATE OR REPLACE FUNCTION fn_set_escalation_sla()
RETURNS TRIGGER AS $$
BEGIN
    NEW.sla_target_at = NEW.created_at + CASE NEW.urgency
        WHEN 'critical' THEN INTERVAL '2 hours'
        WHEN 'high'     THEN INTERVAL '2 hours'
        WHEN 'normal'   THEN INTERVAL '4 hours'
        WHEN 'low'      THEN INTERVAL '24 hours'
        ELSE                 INTERVAL '4 hours'
    END;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_escalations_sla
    BEFORE INSERT ON escalations
    FOR EACH ROW EXECUTE FUNCTION fn_set_escalation_sla();

-- ============================================================
-- HELPER FUNCTIONS
-- Reusable DB-layer logic called from application queries.
-- ============================================================

-- ── Find or create customer by email ──────────────────────
CREATE OR REPLACE FUNCTION fn_find_or_create_customer(
    p_email   VARCHAR,
    p_phone   VARCHAR DEFAULT NULL,
    p_name    VARCHAR DEFAULT NULL,
    p_channel VARCHAR DEFAULT 'web_form'
)
RETURNS UUID AS $$
DECLARE
    v_customer_id UUID;
BEGIN
    -- Try find by email first
    SELECT id INTO v_customer_id
    FROM customers
    WHERE email = p_email
    LIMIT 1;

    -- If not found by email, try phone
    IF v_customer_id IS NULL AND p_phone IS NOT NULL THEN
        SELECT c.id INTO v_customer_id
        FROM customers c
        WHERE c.phone = p_phone
        LIMIT 1;
    END IF;

    -- Create if still not found
    IF v_customer_id IS NULL THEN
        INSERT INTO customers (email, phone, name, last_channel)
        VALUES (p_email, p_phone, p_name, p_channel)
        RETURNING id INTO v_customer_id;
    END IF;

    -- Upsert identifier record
    IF p_email IS NOT NULL THEN
        INSERT INTO customer_identifiers
            (customer_id, identifier_type, identifier_value, source_channel)
        VALUES
            (v_customer_id, 'email', p_email, p_channel)
        ON CONFLICT (identifier_type, identifier_value) DO NOTHING;
    END IF;

    IF p_phone IS NOT NULL THEN
        INSERT INTO customer_identifiers
            (customer_id, identifier_type, identifier_value, source_channel)
        VALUES
            (v_customer_id, 'whatsapp', p_phone, p_channel)
        ON CONFLICT (identifier_type, identifier_value) DO NOTHING;
    END IF;

    RETURN v_customer_id;
END;
$$ LANGUAGE plpgsql;

-- ── Search knowledge base by embedding (cosine similarity) ─
-- Usage: SELECT * FROM fn_search_knowledge_base('[0.1, 0.2, ...]'::vector, 5, 0.7)
CREATE OR REPLACE FUNCTION fn_search_knowledge_base(
    p_embedding     VECTOR(1536),
    p_max_results   INTEGER DEFAULT 5,
    p_min_similarity FLOAT  DEFAULT 0.7,
    p_category      VARCHAR DEFAULT NULL
)
RETURNS TABLE (
    id          UUID,
    title       VARCHAR,
    content     TEXT,
    category    VARCHAR,
    tags        TEXT[],
    similarity  FLOAT
) AS $$
BEGIN
    -- Increment search_count for returned rows
    RETURN QUERY
    WITH results AS (
        SELECT
            kb.id,
            kb.title,
            kb.content,
            kb.category,
            kb.tags,
            1 - (kb.embedding <=> p_embedding) AS similarity
        FROM knowledge_base kb
        WHERE
            kb.embedding IS NOT NULL
            AND (p_category IS NULL OR kb.category = p_category)
            AND 1 - (kb.embedding <=> p_embedding) >= p_min_similarity
        ORDER BY kb.embedding <=> p_embedding
        LIMIT p_max_results
    )
    SELECT r.id, r.title, r.content, r.category, r.tags, r.similarity
    FROM results r;

    -- Update search counts (fire-and-forget, non-blocking)
    UPDATE knowledge_base kb
    SET search_count = search_count + 1
    WHERE kb.id IN (
        SELECT kb2.id
        FROM knowledge_base kb2
        WHERE kb2.embedding IS NOT NULL
          AND (p_category IS NULL OR kb2.category = p_category)
          AND 1 - (kb2.embedding <=> p_embedding) >= p_min_similarity
        ORDER BY kb2.embedding <=> p_embedding
        LIMIT p_max_results
    );
END;
$$ LANGUAGE plpgsql;

-- ── Get active conversation for customer ──────────────────
CREATE OR REPLACE FUNCTION fn_get_active_conversation(
    p_customer_id UUID,
    p_channel     VARCHAR DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
    v_conversation_id UUID;
BEGIN
    SELECT id INTO v_conversation_id
    FROM conversations
    WHERE
        customer_id = p_customer_id
        AND status = 'active'
        AND started_at > NOW() - INTERVAL '24 hours'
    ORDER BY started_at DESC
    LIMIT 1;

    RETURN v_conversation_id;  -- NULL if none found
END;
$$ LANGUAGE plpgsql;

-- ── Get customer 360 summary ───────────────────────────────
CREATE OR REPLACE FUNCTION fn_get_customer_summary(p_customer_id UUID)
RETURNS JSONB AS $$
DECLARE
    v_result JSONB;
BEGIN
    SELECT jsonb_build_object(
        'customer_id',       c.id,
        'name',              c.name,
        'email',             c.email,
        'phone',             c.phone,
        'lifetime_tickets',  c.lifetime_tickets,
        'open_tickets',      c.open_tickets,
        'last_contact_at',   c.last_contact_at,
        'preferred_channel', c.preferred_channel,
        'channels_used',    (
            SELECT jsonb_agg(DISTINCT ci.identifier_type)
            FROM customer_identifiers ci
            WHERE ci.customer_id = c.id
        ),
        'recent_tickets', (
            SELECT jsonb_agg(
                jsonb_build_object(
                    'ticket_id',   t.id,
                    'subject',     t.subject,
                    'status',      t.status,
                    'priority',    t.priority,
                    'channel',     t.source_channel,
                    'created_at',  t.created_at
                ) ORDER BY t.created_at DESC
            )
            FROM tickets t
            WHERE t.customer_id = c.id
            LIMIT 5
        )
    ) INTO v_result
    FROM customers c
    WHERE c.id = p_customer_id;

    RETURN v_result;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- VIEWS
-- Pre-built query shortcuts for common dashboard needs.
-- ============================================================

-- ── Open tickets with SLA status ──────────────────────────
CREATE OR REPLACE VIEW v_open_tickets AS
SELECT
    t.id,
    t.subject,
    t.category,
    t.priority,
    t.status,
    t.source_channel,
    t.created_at,
    t.sla_breach_at,
    CASE
        WHEN t.sla_breach_at < NOW() THEN 'breached'
        WHEN t.sla_breach_at < NOW() + INTERVAL '1 hour' THEN 'at_risk'
        ELSE 'within_sla'
    END AS sla_status,
    EXTRACT(EPOCH FROM (t.sla_breach_at - NOW())) / 60 AS minutes_until_breach,
    c.email     AS customer_email,
    c.name      AS customer_name,
    c.lifetime_tickets
FROM tickets t
JOIN customers c ON c.id = t.customer_id
WHERE t.status IN ('open', 'in_progress', 'escalated')
ORDER BY t.priority DESC, t.created_at ASC;

COMMENT ON VIEW v_open_tickets IS 'All open/in-progress/escalated tickets with SLA status. Use for agent dashboard and monitoring.';

-- ── Channel performance summary (last 24h) ─────────────────
CREATE OR REPLACE VIEW v_channel_daily_summary AS
SELECT
    c.initial_channel                              AS channel,
    COUNT(*)                                       AS total_conversations,
    COUNT(*) FILTER (WHERE c.status = 'resolved')  AS resolved,
    COUNT(*) FILTER (WHERE c.status = 'escalated') AS escalated,
    ROUND(AVG(c.sentiment_score)::NUMERIC, 3)      AS avg_sentiment,
    ROUND(AVG(c.message_count)::NUMERIC, 1)        AS avg_messages,
    ROUND(AVG(c.agent_turns)::NUMERIC, 1)          AS avg_agent_turns,
    ROUND(
        COUNT(*) FILTER (WHERE c.status = 'escalated')::DECIMAL /
        NULLIF(COUNT(*), 0) * 100, 1
    )                                              AS escalation_rate_pct,
    AVG(m.latency_ms)                              AS avg_latency_ms
FROM conversations c
LEFT JOIN messages m
    ON m.conversation_id = c.id
    AND m.direction = 'outbound'
    AND m.role = 'agent'
WHERE c.started_at >= NOW() - INTERVAL '24 hours'
GROUP BY c.initial_channel;

COMMENT ON VIEW v_channel_daily_summary IS 'Last 24-hour channel performance. Used for daily reporting and SLO monitoring.';

-- ── Knowledge base usage ranking ──────────────────────────
CREATE OR REPLACE VIEW v_knowledge_base_usage AS
SELECT
    id,
    title,
    category,
    tags,
    search_count,
    helpful_count,
    unhelpful_count,
    CASE
        WHEN search_count = 0 THEN NULL
        ELSE ROUND(helpful_count::DECIMAL / search_count * 100, 1)
    END AS helpful_rate_pct,
    embedding IS NOT NULL AS has_embedding,
    updated_at
FROM knowledge_base
ORDER BY search_count DESC;

COMMENT ON VIEW v_knowledge_base_usage IS 'Knowledge base articles ranked by usage. Use to identify gaps and improve content.';

-- ── SLA breach monitoring ─────────────────────────────────
CREATE OR REPLACE VIEW v_sla_breaches AS
SELECT
    e.id          AS escalation_id,
    e.urgency,
    e.reason,
    e.created_at  AS escalated_at,
    e.sla_target_at,
    e.status,
    CASE WHEN e.sla_target_at < NOW() AND e.status IN ('open', 'in_progress')
        THEN TRUE ELSE FALSE
    END           AS is_breached,
    t.source_channel,
    t.priority,
    c.email       AS customer_email,
    c.name        AS customer_name
FROM escalations e
JOIN tickets t ON t.id = e.ticket_id
JOIN customers c ON c.id = e.customer_id
WHERE e.status IN ('open', 'in_progress')
ORDER BY e.urgency DESC, e.sla_target_at ASC;

COMMENT ON VIEW v_sla_breaches IS 'All open escalations with SLA status. Critical for human agent prioritisation.';

-- ============================================================
-- SEED DATA
-- ============================================================

-- ── Channel configurations ─────────────────────────────────
INSERT INTO channel_configs (
    channel, enabled, config, max_response_length,
    response_style, rate_limit_per_minute
)
VALUES
    (
        'email', TRUE,
        '{
            "provider": "gmail",
            "user_id": "me",
            "label_ids": ["INBOX"],
            "pub_sub_topic": "projects/YOUR_GCP_PROJECT/topics/gmail-push",
            "format": "text",
            "include_greeting": true,
            "include_signature": true,
            "signature": "— NimbusFlow Support"
        }',
        4000, 'formal', 60
    ),
    (
        'whatsapp', TRUE,
        '{
            "provider": "twilio",
            "from_number": "whatsapp:+14155238886",
            "max_chars_per_message": 1600,
            "format": "plain_text",
            "split_long_messages": true,
            "max_message_parts": 2
        }',
        1600, 'conversational', 120
    ),
    (
        'web_form', TRUE,
        '{
            "provider": "fastapi",
            "cors_origins": ["http://localhost:3000"],
            "format": "plain_text",
            "send_email_confirmation": true,
            "rate_limit_per_ip": 10
        }',
        2000, 'standard', 30
    )
ON CONFLICT (channel) DO UPDATE SET
    config = EXCLUDED.config,
    updated_at = NOW();
