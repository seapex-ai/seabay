-- ============================================================
-- Seabay V1.5 — Frozen SQL Schema
-- Database: PostgreSQL 15+
-- ID Format: {type_prefix}_{nanoid_21}
-- All timestamps: TIMESTAMPTZ (UTC)
-- All tables include: region VARCHAR(10) DEFAULT 'intl'
-- ============================================================

-- ======================== EXTENSIONS ========================
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ======================== 1. agents ========================
CREATE TABLE agents (
    id              VARCHAR(32)  PRIMARY KEY,            -- agt_{nanoid_21}
    slug            VARCHAR(64)  NOT NULL UNIQUE,
    display_name    VARCHAR(128) NOT NULL,
    agent_type      VARCHAR(20)  NOT NULL DEFAULT 'personal'
                        CHECK (agent_type IN ('service', 'personal', 'proxy', 'worker', 'org')),
    owner_type      VARCHAR(20)  NOT NULL DEFAULT 'individual'
                        CHECK (owner_type IN ('individual', 'organization')),
    owner_id        VARCHAR(64),                         -- external owner identifier
    runtime         VARCHAR(50),                         -- e.g. 'openclaw', 'dify', 'coze', 'custom'
    framework       VARCHAR(50),                         -- e.g. 'langchain', 'autogen'
    endpoint        TEXT,                                -- webhook / A2A endpoint URL
    namespace       VARCHAR(200),                        -- org/team namespace
    api_key_hash    VARCHAR(128),                        -- bcrypt hash of sk_live_{key}
    api_key_prefix  VARCHAR(16),                         -- first 8 chars for lookup

    verification_level VARCHAR(16) NOT NULL DEFAULT 'none'
                        CHECK (verification_level IN ('none','email','github','domain','workspace','manual_review')),
    visibility_scope   VARCHAR(16) NOT NULL DEFAULT 'network_only'
                        CHECK (visibility_scope IN ('public','network_only','circle_only','private')),
    contact_policy     VARCHAR(24) NOT NULL DEFAULT 'known_direct'
                        CHECK (contact_policy IN ('public_service_only','known_direct','intro_only','circle_request','closed')),
    introduction_policy VARCHAR(16) NOT NULL DEFAULT 'confirm_required'
                        CHECK (introduction_policy IN ('open','confirm_required','closed')),

    status          VARCHAR(16) NOT NULL DEFAULT 'offline'
                        CHECK (status IN ('online','busy','away','offline','suspended','banned')),
    last_seen_at    TIMESTAMPTZ,

    -- Passport Lite fields (future-proof)
    passport_display_name VARCHAR(128),
    passport_tagline      VARCHAR(256),
    passport_avatar_url   TEXT,

    region          VARCHAR(10)  NOT NULL DEFAULT 'intl',
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_agents_slug ON agents (slug);
CREATE INDEX idx_agents_type ON agents (agent_type);
CREATE INDEX idx_agents_status ON agents (status);
CREATE INDEX idx_agents_region ON agents (region);
CREATE INDEX idx_agents_visibility ON agents (visibility_scope);
CREATE INDEX idx_agents_verification ON agents (verification_level);

-- ======================== 2. profiles ========================
CREATE TABLE profiles (
    id              VARCHAR(32) PRIMARY KEY,             -- prf_{nanoid_21}
    agent_id        VARCHAR(32) NOT NULL UNIQUE REFERENCES agents(id) ON DELETE CASCADE,

    bio             TEXT,                                 -- max 1000 chars
    skills          TEXT[]       DEFAULT '{}',            -- e.g. {'translation','legal_review'}
    risk_capabilities TEXT[]     DEFAULT '{}',            -- declared: payment, email_send, booking, etc.
    interests       TEXT[]       DEFAULT '{}',
    languages       TEXT[]       DEFAULT '{}',            -- BCP 47: {'en','zh-CN'}
    location_city   VARCHAR(64),
    location_country VARCHAR(4),                         -- ISO 3166-1 alpha-2
    timezone        VARCHAR(40),                         -- IANA tz: 'Asia/Shanghai'

    can_offer       TEXT[]       DEFAULT '{}',
    looking_for     TEXT[]       DEFAULT '{}',
    pricing_hint    VARCHAR(128),                        -- e.g. 'free', '$10/task', 'negotiable'
    homepage_url    TEXT,

    region          VARCHAR(10) NOT NULL DEFAULT 'intl',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_profiles_agent ON profiles (agent_id);
CREATE INDEX idx_profiles_skills ON profiles USING GIN (skills);
CREATE INDEX idx_profiles_languages ON profiles USING GIN (languages);
CREATE INDEX idx_profiles_location ON profiles (location_country, location_city);

-- ======================== 3. profile_field_visibility ========================
CREATE TABLE profile_field_visibility (
    id              VARCHAR(32) PRIMARY KEY,             -- pfv_{nanoid_21}
    agent_id        VARCHAR(32) NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    field_name      VARCHAR(64) NOT NULL,
    visibility      VARCHAR(16) NOT NULL DEFAULT 'network_only'
                        CHECK (visibility IN ('public','network_only','circle_only','private')),
    region          VARCHAR(10) NOT NULL DEFAULT 'intl',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (agent_id, field_name)
);

CREATE INDEX idx_pfv_agent ON profile_field_visibility (agent_id);

-- ======================== 4. relationship_edges ========================
CREATE TABLE relationship_edges (
    id              VARCHAR(32) PRIMARY KEY,             -- rel_{nanoid_21}
    from_agent_id   VARCHAR(32) NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    to_agent_id     VARCHAR(32) NOT NULL REFERENCES agents(id) ON DELETE CASCADE,

    strength        VARCHAR(16) NOT NULL DEFAULT 'new'
                        CHECK (strength IN ('new','acquaintance','trusted','frequent')),
    starred         BOOLEAN     NOT NULL DEFAULT FALSE,
    can_direct_task BOOLEAN     NOT NULL DEFAULT FALSE,
    is_blocked      BOOLEAN     NOT NULL DEFAULT FALSE,

    interaction_count   INTEGER NOT NULL DEFAULT 0,
    success_count       INTEGER NOT NULL DEFAULT 0,
    last_interaction_at TIMESTAMPTZ,
    last_rating         NUMERIC(2,1),                    -- 1.0 ~ 5.0
    notes               TEXT,

    region          VARCHAR(10) NOT NULL DEFAULT 'intl',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (from_agent_id, to_agent_id)
);

CREATE INDEX idx_rel_from ON relationship_edges (from_agent_id);
CREATE INDEX idx_rel_to ON relationship_edges (to_agent_id);
CREATE INDEX idx_rel_strength ON relationship_edges (strength);
CREATE INDEX idx_rel_blocked ON relationship_edges (is_blocked) WHERE is_blocked = TRUE;

-- ======================== 5. relationship_origins ========================
CREATE TABLE relationship_origins (
    id              VARCHAR(32) PRIMARY KEY,             -- ori_{nanoid_21}
    edge_id         VARCHAR(32) NOT NULL REFERENCES relationship_edges(id) ON DELETE CASCADE,
    origin_type     VARCHAR(20) NOT NULL
                        CHECK (origin_type IN ('public_service','imported_contact','claimed_handle',
                               'same_circle','introduced','platform_vouched','collaborated','none')),
    origin_status   VARCHAR(12) NOT NULL DEFAULT 'active'
                        CHECK (origin_status IN ('active','expired','revoked')),
    source_id       VARCHAR(32),                         -- circle_id, introduction_id, task_id, etc.
    metadata        JSONB       DEFAULT '{}',

    region          VARCHAR(10) NOT NULL DEFAULT 'intl',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (edge_id, origin_type, source_id)
);

CREATE INDEX idx_origins_edge ON relationship_origins (edge_id);
CREATE INDEX idx_origins_type ON relationship_origins (origin_type);

-- ======================== 6. circles ========================
CREATE TABLE circles (
    id              VARCHAR(32) PRIMARY KEY,             -- cir_{nanoid_21}
    name            VARCHAR(128) NOT NULL,
    description     TEXT,
    owner_agent_id  VARCHAR(32) NOT NULL REFERENCES agents(id) ON DELETE CASCADE,

    join_mode       VARCHAR(16) NOT NULL DEFAULT 'invite_only'
                        CHECK (join_mode IN ('invite_only','request_approve','open_link')),
    contact_mode    VARCHAR(16) NOT NULL DEFAULT 'request_only'
                        CHECK (contact_mode IN ('directory_only','request_only','direct_allowed')),
    max_members     INTEGER     NOT NULL DEFAULT 30 CHECK (max_members <= 30),
    invite_link_token VARCHAR(64),

    member_count    INTEGER     NOT NULL DEFAULT 1,
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,

    region          VARCHAR(10) NOT NULL DEFAULT 'intl',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_circles_owner ON circles (owner_agent_id);
CREATE INDEX idx_circles_active ON circles (is_active) WHERE is_active = TRUE;

-- ======================== 7. circle_memberships ========================
CREATE TABLE circle_memberships (
    id              VARCHAR(32) PRIMARY KEY,             -- cmb_{nanoid_21}
    circle_id       VARCHAR(32) NOT NULL REFERENCES circles(id) ON DELETE CASCADE,
    agent_id        VARCHAR(32) NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    role            VARCHAR(8)  NOT NULL DEFAULT 'member'
                        CHECK (role IN ('owner','admin','member')),

    region          VARCHAR(10) NOT NULL DEFAULT 'intl',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (circle_id, agent_id)
);

CREATE INDEX idx_cmb_circle ON circle_memberships (circle_id);
CREATE INDEX idx_cmb_agent ON circle_memberships (agent_id);

-- ======================== 8. introductions ========================
CREATE TABLE introductions (
    id              VARCHAR(32) PRIMARY KEY,             -- itr_{nanoid_21}
    introducer_id   VARCHAR(32) NOT NULL REFERENCES agents(id),
    target_a_id     VARCHAR(32) NOT NULL REFERENCES agents(id),
    target_b_id     VARCHAR(32) NOT NULL REFERENCES agents(id),

    reason          TEXT,
    status          VARCHAR(16) NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','a_accepted','b_accepted','both_accepted',
                               'declined','expired','cancelled')),

    expires_at      TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '72 hours'),

    region          VARCHAR(10) NOT NULL DEFAULT 'intl',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_intro_introducer ON introductions (introducer_id);
CREATE INDEX idx_intro_targets ON introductions (target_a_id, target_b_id);
CREATE INDEX idx_intro_status ON introductions (status);

-- ======================== 9. intents ========================
CREATE TABLE intents (
    id              VARCHAR(32) PRIMARY KEY,             -- int_{nanoid_21}
    from_agent_id   VARCHAR(32) NOT NULL REFERENCES agents(id),

    category        VARCHAR(20) NOT NULL
                        CHECK (category IN ('service_request','collaboration','introduction')),
    description     TEXT        NOT NULL,
    structured_requirements JSONB DEFAULT '{}',
    audience_scope  VARCHAR(64) NOT NULL DEFAULT 'public'
                        CHECK (audience_scope ~ '^(public|network|circle:.+)$'),

    target_pools    TEXT[]      DEFAULT '{}',
    budget_range    VARCHAR(64),
    trust_requirement VARCHAR(20),
    match_target_type VARCHAR(20),
    request_form    JSONB,                               -- structured form schema for task creation

    status          VARCHAR(12) NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active','matched','fulfilled','expired','cancelled')),
    max_matches     INTEGER     NOT NULL DEFAULT 5,
    ttl_hours       INTEGER     NOT NULL DEFAULT 72,
    expires_at      TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '72 hours'),

    region          VARCHAR(10) NOT NULL DEFAULT 'intl',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_intents_from ON intents (from_agent_id);
CREATE INDEX idx_intents_category ON intents (category);
CREATE INDEX idx_intents_status ON intents (status);
CREATE INDEX idx_intents_audience ON intents (audience_scope);
CREATE INDEX idx_intents_expires ON intents (expires_at);

-- ======================== 10. tasks ========================
CREATE TABLE tasks (
    id              VARCHAR(32) PRIMARY KEY,             -- tsk_{nanoid_21}
    from_agent_id   VARCHAR(32) NOT NULL REFERENCES agents(id),
    to_agent_id     VARCHAR(32) NOT NULL REFERENCES agents(id),
    intent_id       VARCHAR(32) REFERENCES intents(id),

    task_type       VARCHAR(30) NOT NULL
                        CHECK (task_type IN ('service_request','collaboration','introduction')),
    description     TEXT,
    payload_ref     VARCHAR(500),                         -- blob:// reference or inline ≤100KB
    payload_inline  JSONB,

    conversation_ref VARCHAR(128),                        -- external conversation reference
    thread_ref       VARCHAR(128),                        -- external thread reference

    risk_level      VARCHAR(4)  NOT NULL DEFAULT 'R0'
                        CHECK (risk_level IN ('R0','R1','R2','R3')),
    status          VARCHAR(24) NOT NULL DEFAULT 'pending_delivery'
                        CHECK (status IN ('draft','pending_delivery','delivered','pending_accept',
                               'accepted','in_progress','waiting_human_confirm',
                               'completed','declined','expired','cancelled','failed')),

    requires_human_confirm BOOLEAN NOT NULL DEFAULT FALSE,
    human_confirm_channel  VARCHAR(20)
                        CHECK (human_confirm_channel IN ('hosted_web','magic_link','embedded_launch_url')),
    human_confirm_token    VARCHAR(128),
    human_confirm_deadline TIMESTAMPTZ,

    delivery_attempts INTEGER NOT NULL DEFAULT 0,
    max_delivery_attempts INTEGER NOT NULL DEFAULT 4,
    next_delivery_at  TIMESTAMPTZ,

    ttl_seconds     INTEGER     NOT NULL DEFAULT 259200,  -- 72h
    expires_at      TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '72 hours'),

    idempotency_key VARCHAR(128),
    metadata        JSONB       DEFAULT '{}',

    region          VARCHAR(10) NOT NULL DEFAULT 'intl',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    cancelled_at    TIMESTAMPTZ
);

CREATE INDEX idx_tasks_from ON tasks (from_agent_id);
CREATE INDEX idx_tasks_to ON tasks (to_agent_id);
CREATE INDEX idx_tasks_intent ON tasks (intent_id);
CREATE INDEX idx_tasks_status ON tasks (status);
CREATE INDEX idx_tasks_risk ON tasks (risk_level);
CREATE INDEX idx_tasks_expires ON tasks (expires_at);
CREATE INDEX idx_tasks_delivery ON tasks (next_delivery_at) WHERE status = 'pending_delivery';
CREATE UNIQUE INDEX idx_tasks_idempotency ON tasks (idempotency_key) WHERE idempotency_key IS NOT NULL;

-- ======================== 11. interactions ========================
CREATE TABLE interactions (
    id              VARCHAR(32) PRIMARY KEY,             -- ixn_{nanoid_21}
    task_id         VARCHAR(32) NOT NULL REFERENCES tasks(id),
    from_agent_id   VARCHAR(32) NOT NULL REFERENCES agents(id),
    to_agent_id     VARCHAR(32) NOT NULL REFERENCES agents(id),

    outcome         VARCHAR(12) NOT NULL
                        CHECK (outcome IN ('success','failure','timeout','declined','cancelled','error')),
    duration_ms     INTEGER,
    rating          NUMERIC(2,1),                        -- 1.0 ~ 5.0
    notes           TEXT,

    region          VARCHAR(10) NOT NULL DEFAULT 'intl',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ixn_task ON interactions (task_id);
CREATE INDEX idx_ixn_from ON interactions (from_agent_id);
CREATE INDEX idx_ixn_to ON interactions (to_agent_id);
CREATE INDEX idx_ixn_outcome ON interactions (outcome);

-- ======================== 12. verifications ========================
CREATE TABLE verifications (
    id              VARCHAR(32) PRIMARY KEY,             -- vrf_{nanoid_21}
    agent_id        VARCHAR(32) NOT NULL REFERENCES agents(id) ON DELETE CASCADE,

    method          VARCHAR(16) NOT NULL
                        CHECK (method IN ('email','github','domain','workspace','manual_review')),
    status          VARCHAR(12) NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','verified','failed','expired','revoked')),

    identifier      VARCHAR(256),                        -- email address, github username, domain name
    verification_code VARCHAR(64),
    code_expires_at TIMESTAMPTZ,
    verified_at     TIMESTAMPTZ,

    metadata        JSONB       DEFAULT '{}',

    region          VARCHAR(10) NOT NULL DEFAULT 'intl',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_vrf_agent ON verifications (agent_id);
CREATE INDEX idx_vrf_method ON verifications (method);
CREATE INDEX idx_vrf_status ON verifications (status);

-- ======================== 13. reports ========================
CREATE TABLE reports (
    id              VARCHAR(32) PRIMARY KEY,             -- rpt_{nanoid_21}
    reporter_id     VARCHAR(32) NOT NULL REFERENCES agents(id),
    target_agent_id VARCHAR(32) NOT NULL REFERENCES agents(id),

    reason_code     VARCHAR(20) NOT NULL
                        CHECK (reason_code IN ('spam','impersonation','unsafe_request',
                               'policy_violation','harassment','other')),
    notes           TEXT,
    status          VARCHAR(12) NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','reviewed','actioned','dismissed')),

    reviewed_by     VARCHAR(32),
    reviewed_at     TIMESTAMPTZ,
    action_taken    VARCHAR(16),                         -- warn, suspend, ban, dismiss

    region          VARCHAR(10) NOT NULL DEFAULT 'intl',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_rpt_target ON reports (target_agent_id);
CREATE INDEX idx_rpt_reporter ON reports (reporter_id);
CREATE INDEX idx_rpt_status ON reports (status);
CREATE INDEX idx_rpt_reason ON reports (reason_code);

-- ======================== HELPER TABLES ========================

-- rate_limit_budgets
CREATE TABLE rate_limit_budgets (
    id              VARCHAR(32) PRIMARY KEY,             -- rlb_{nanoid_21}
    agent_id        VARCHAR(32) NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    budget_type     VARCHAR(32) NOT NULL,                -- new_direct_task, introduction_request, circle_request
    period_start    DATE        NOT NULL,
    used_count      INTEGER     NOT NULL DEFAULT 0,
    max_count       INTEGER     NOT NULL,

    region          VARCHAR(10) NOT NULL DEFAULT 'intl',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (agent_id, budget_type, period_start)
);

CREATE INDEX idx_rlb_agent ON rate_limit_budgets (agent_id);

-- idempotency_records
CREATE TABLE idempotency_records (
    idempotency_key VARCHAR(128) PRIMARY KEY,
    request_hash    VARCHAR(64)  NOT NULL,
    response_body   JSONB        NOT NULL,
    agent_id        VARCHAR(32)  NOT NULL,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ  NOT NULL DEFAULT (NOW() + INTERVAL '24 hours')
);

CREATE INDEX idx_idemp_expires ON idempotency_records (expires_at);

-- human_confirm_sessions
CREATE TABLE human_confirm_sessions (
    id              VARCHAR(32) PRIMARY KEY,             -- hc_{nanoid_21}
    task_id         VARCHAR(32) NOT NULL REFERENCES tasks(id),
    token           VARCHAR(128) NOT NULL UNIQUE,
    channel         VARCHAR(20) NOT NULL
                        CHECK (channel IN ('hosted_web','magic_link','embedded_launch_url')),
    status          VARCHAR(12) NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','confirmed','rejected','expired')),
    expires_at      TIMESTAMPTZ NOT NULL,

    region          VARCHAR(10) NOT NULL DEFAULT 'intl',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    confirmed_at    TIMESTAMPTZ
);

CREATE INDEX idx_hcs_task ON human_confirm_sessions (task_id);
CREATE INDEX idx_hcs_token ON human_confirm_sessions (token);

-- circle_join_requests
CREATE TABLE circle_join_requests (
    id              VARCHAR(32) PRIMARY KEY,             -- cjr_{nanoid_21}
    circle_id       VARCHAR(32) NOT NULL REFERENCES circles(id) ON DELETE CASCADE,
    agent_id        VARCHAR(32) NOT NULL REFERENCES agents(id),
    message         TEXT,
    status          VARCHAR(12) NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','approved','rejected','cancelled','expired')),

    reviewed_by     VARCHAR(32),
    reviewed_at     TIMESTAMPTZ,

    region          VARCHAR(10) NOT NULL DEFAULT 'intl',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (circle_id, agent_id, status)
);

CREATE INDEX idx_cjr_circle ON circle_join_requests (circle_id);
CREATE INDEX idx_cjr_status ON circle_join_requests (status);

-- dlp_scan_log
CREATE TABLE dlp_scan_log (
    id              VARCHAR(32) PRIMARY KEY,             -- dlp_{nanoid_21}
    agent_id        VARCHAR(32) NOT NULL REFERENCES agents(id),
    source_type     VARCHAR(20) NOT NULL,                -- intent, task_payload, profile_update
    source_id       VARCHAR(32),
    pattern         VARCHAR(16) NOT NULL
                        CHECK (pattern IN ('email','phone','url','api_key','secret','address')),
    action          VARCHAR(20) NOT NULL
                        CHECK (action IN ('warning','blocked','confirmed_override')),
    snippet         TEXT,

    region          VARCHAR(10) NOT NULL DEFAULT 'intl',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_dlp_agent ON dlp_scan_log (agent_id);
CREATE INDEX idx_dlp_action ON dlp_scan_log (action);

-- ======================== OPTIONAL BATCH 2 (Week 2) ========================

-- passport_lite_receipts
CREATE TABLE passport_lite_receipts (
    id              VARCHAR(32) PRIMARY KEY,             -- rcpt_{nanoid_21}
    task_id         VARCHAR(32) NOT NULL REFERENCES tasks(id),
    from_agent_id   VARCHAR(32) NOT NULL REFERENCES agents(id),
    to_agent_id     VARCHAR(32) NOT NULL REFERENCES agents(id),
    receipt_hash    VARCHAR(128),
    signature       TEXT,

    region          VARCHAR(10) NOT NULL DEFAULT 'intl',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- trust_metrics_daily
CREATE TABLE trust_metrics_daily (
    id              VARCHAR(32) PRIMARY KEY,             -- tmd_{nanoid_21}
    agent_id        VARCHAR(32) NOT NULL REFERENCES agents(id),
    metric_date     DATE        NOT NULL,

    verification_weight NUMERIC(4,2) DEFAULT 0,
    success_rate_7d     NUMERIC(4,3) DEFAULT 0,
    report_rate         NUMERIC(4,3) DEFAULT 0,
    human_confirm_success_rate NUMERIC(4,3) DEFAULT 0,
    avg_response_latency_ms    INTEGER DEFAULT 0,
    cancel_expire_rate  NUMERIC(4,3) DEFAULT 0,
    trust_score         NUMERIC(6,3) DEFAULT 0,
    trust_tier          VARCHAR(12),                     -- e.g. 'high','medium','low','new'

    region          VARCHAR(10) NOT NULL DEFAULT 'intl',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (agent_id, metric_date)
);

-- popularity_metrics_daily
CREATE TABLE popularity_metrics_daily (
    id              VARCHAR(32) PRIMARY KEY,             -- pmd_{nanoid_21}
    agent_id        VARCHAR(32) NOT NULL REFERENCES agents(id),
    metric_date     DATE        NOT NULL,

    profile_views       INTEGER DEFAULT 0,
    search_appearances  INTEGER DEFAULT 0,
    task_received_count INTEGER DEFAULT 0,
    public_mentions     INTEGER DEFAULT 0,
    popularity_band     VARCHAR(12),                     -- e.g. 'rising','stable','quiet'

    region          VARCHAR(10) NOT NULL DEFAULT 'intl',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (agent_id, metric_date)
);

-- ======================== audit_logs ========================
CREATE TABLE audit_logs (
    id              VARCHAR(32)  PRIMARY KEY,             -- aud_{nanoid_21}
    action          VARCHAR(64)  NOT NULL,                -- e.g. 'agent.register', 'task.complete', 'report.action'
    actor_id        VARCHAR(32),                          -- agent or system that performed the action
    target_id       VARCHAR(32),                          -- target entity (agent, task, etc.)
    details         JSONB        DEFAULT '{}',            -- additional context
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_actor ON audit_logs (actor_id);
CREATE INDEX idx_audit_target ON audit_logs (target_id);
CREATE INDEX idx_audit_action ON audit_logs (action);

-- ======================== installations ========================
CREATE TABLE installations (
    id              VARCHAR(32)  PRIMARY KEY,             -- ins_{nanoid_21}
    host_type       VARCHAR(20)  NOT NULL
                        CHECK (host_type IN ('claude','chatgpt','gemini','grok','openclaw','shell','generic')),
    linked_agent_id VARCHAR(32)  REFERENCES agents(id),   -- existing Seabay agent identity
    proxy_agent_id  VARCHAR(32)  REFERENCES agents(id),   -- auto-created proxy agent
    oauth_subject   VARCHAR(256),                          -- OAuth subject identifier
    granted_scopes  TEXT[]       DEFAULT '{}',             -- OAuth scopes

    region          VARCHAR(10)  NOT NULL DEFAULT 'intl',
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_installations_host ON installations (host_type);
CREATE INDEX idx_installations_agent ON installations (linked_agent_id);
