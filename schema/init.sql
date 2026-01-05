-- LegiVellum Database Initialization
-- Combines all schema files for initial database setup
-- Run this once to initialize the database

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- RECEIPTS TABLE (MemoryGate)
-- ============================================================================

CREATE TABLE IF NOT EXISTS receipts (
    -- Database internal (not in wire format)
    uuid UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Schema version
    schema_version TEXT NOT NULL DEFAULT '1.0',

    -- Multi-tenant support
    tenant_id TEXT NOT NULL DEFAULT 'pstryder',

    -- Receipt identity
    receipt_id TEXT NOT NULL,

    -- Task correlation
    task_id TEXT NOT NULL,
    parent_task_id TEXT NOT NULL,
    caused_by_receipt_id TEXT NOT NULL,
    dedupe_key TEXT NOT NULL,
    attempt INTEGER NOT NULL DEFAULT 0 CHECK (attempt >= 0),

    -- Routing and accountability
    from_principal TEXT NOT NULL,
    for_principal TEXT NOT NULL,
    source_system TEXT NOT NULL,
    recipient_ai TEXT NOT NULL,
    trust_domain TEXT NOT NULL,

    -- Phase and status
    phase TEXT NOT NULL CHECK (phase IN ('accepted', 'complete', 'escalate')),
    status TEXT NOT NULL DEFAULT 'NA' CHECK (status IN ('NA', 'success', 'failure', 'canceled')),
    realtime BOOLEAN NOT NULL DEFAULT FALSE,

    -- Task definition
    task_type TEXT NOT NULL,
    task_summary TEXT NOT NULL,
    task_body TEXT NOT NULL,
    inputs JSONB NOT NULL DEFAULT '{}'::jsonb,
    expected_outcome_kind TEXT NOT NULL CHECK (expected_outcome_kind IN ('NA', 'none', 'response_text', 'artifact_pointer', 'mixed')),
    expected_artifact_mime TEXT NOT NULL,

    -- Outcome and artifacts
    outcome_kind TEXT NOT NULL CHECK (outcome_kind IN ('NA', 'none', 'response_text', 'artifact_pointer', 'mixed')),
    outcome_text TEXT NOT NULL,
    artifact_location TEXT NOT NULL,
    artifact_pointer TEXT NOT NULL,
    artifact_checksum TEXT NOT NULL,
    artifact_size_bytes BIGINT NOT NULL DEFAULT 0 CHECK (artifact_size_bytes >= 0),
    artifact_mime TEXT NOT NULL,

    -- Escalation
    escalation_class TEXT NOT NULL CHECK (escalation_class IN ('NA', 'owner', 'capability', 'trust', 'policy', 'scope', 'other')),
    escalation_reason TEXT NOT NULL,
    escalation_to TEXT NOT NULL,
    retry_requested BOOLEAN NOT NULL DEFAULT FALSE,

    -- Timestamps
    created_at TIMESTAMPTZ,
    stored_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    read_at TIMESTAMPTZ,
    archived_at TIMESTAMPTZ,

    -- Freeform metadata
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- Phase constraints
    CONSTRAINT phase_accepted_rules CHECK (
        phase != 'accepted' OR (
            status = 'NA' AND
            completed_at IS NULL AND
            task_summary != 'TBD' AND
            escalation_class = 'NA'
        )
    ),

    CONSTRAINT phase_complete_rules CHECK (
        phase != 'complete' OR (
            status IN ('success', 'failure', 'canceled') AND
            completed_at IS NOT NULL AND
            outcome_kind IN ('none', 'response_text', 'artifact_pointer', 'mixed') AND
            escalation_class = 'NA'
        )
    ),

    CONSTRAINT phase_escalate_rules CHECK (
        phase != 'escalate' OR (
            status = 'NA' AND
            escalation_class IN ('owner', 'capability', 'trust', 'policy', 'scope', 'other') AND
            escalation_reason != 'TBD'
        )
    ),

    CONSTRAINT artifact_pointer_rules CHECK (
        outcome_kind NOT IN ('artifact_pointer', 'mixed') OR (
            artifact_pointer != 'NA' AND
            artifact_location != 'NA'
        )
    ),

    CONSTRAINT escalation_owner_rules CHECK (
        escalation_class != 'owner' OR escalation_to != 'NA'
    ),

    CONSTRAINT retry_attempt_rules CHECK (
        NOT retry_requested OR attempt >= 1
    ),

    CONSTRAINT unique_receipt_per_tenant UNIQUE (tenant_id, receipt_id)
);

-- Receipt indexes
CREATE INDEX IF NOT EXISTS idx_receipts_task_id ON receipts(tenant_id, task_id);
CREATE INDEX IF NOT EXISTS idx_receipts_recipient_ai ON receipts(tenant_id, recipient_ai);
CREATE INDEX IF NOT EXISTS idx_receipts_parent_task_id ON receipts(tenant_id, parent_task_id);
CREATE INDEX IF NOT EXISTS idx_receipts_caused_by ON receipts(tenant_id, caused_by_receipt_id);
CREATE INDEX IF NOT EXISTS idx_receipts_stored_at ON receipts(tenant_id, stored_at);
CREATE INDEX IF NOT EXISTS idx_receipts_inbox ON receipts(tenant_id, recipient_ai, phase, archived_at)
    WHERE phase = 'accepted' AND archived_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_receipts_task_phase ON receipts(tenant_id, task_id, phase);
CREATE INDEX IF NOT EXISTS idx_receipts_recipient_time ON receipts(tenant_id, recipient_ai, stored_at DESC);


-- ============================================================================
-- TASKS TABLE (AsyncGate)
-- ============================================================================

CREATE TABLE IF NOT EXISTS tasks (
    -- Database internal
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Task identity
    task_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,

    -- Task definition
    task_type TEXT NOT NULL,
    task_summary TEXT NOT NULL,
    task_body TEXT NOT NULL DEFAULT '',
    inputs JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- Routing
    recipient_ai TEXT NOT NULL,
    from_principal TEXT NOT NULL,
    for_principal TEXT NOT NULL,

    -- Expected outcome
    expected_outcome_kind TEXT NOT NULL DEFAULT 'NA',
    expected_artifact_mime TEXT NOT NULL DEFAULT 'NA',

    -- Chain linking
    caused_by_receipt_id TEXT NOT NULL DEFAULT 'NA',
    parent_task_id TEXT NOT NULL DEFAULT 'NA',

    -- Status and priority
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'leased', 'completed', 'failed', 'expired')),
    priority INTEGER NOT NULL DEFAULT 0 CHECK (priority >= 0 AND priority <= 10),

    -- Lease tracking
    lease_id TEXT,
    worker_id TEXT,
    lease_expires_at TIMESTAMPTZ,

    -- Retry tracking
    attempt INTEGER NOT NULL DEFAULT 0 CHECK (attempt >= 0),
    max_attempts INTEGER NOT NULL DEFAULT 3 CHECK (max_attempts >= 1),

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,

    -- Unique constraint
    CONSTRAINT unique_task_per_tenant UNIQUE (tenant_id, task_id)
);

-- Task indexes
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_tasks_queued ON tasks(tenant_id, status, priority DESC, created_at ASC)
    WHERE status = 'queued';
CREATE INDEX IF NOT EXISTS idx_tasks_lease ON tasks(tenant_id, lease_id) WHERE lease_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_tasks_worker ON tasks(tenant_id, worker_id) WHERE worker_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_tasks_expires ON tasks(tenant_id, lease_expires_at)
    WHERE status = 'leased';
CREATE INDEX IF NOT EXISTS idx_tasks_recipient ON tasks(tenant_id, recipient_ai);
CREATE INDEX IF NOT EXISTS idx_tasks_type ON tasks(tenant_id, task_type);


-- ============================================================================
-- PLANS TABLE (DeleGate)
-- ============================================================================

CREATE TABLE IF NOT EXISTS plans (
    -- Database internal
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Plan identity
    plan_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,

    -- Plan metadata
    principal_ai TEXT NOT NULL,
    intent TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 0.8 CHECK (confidence >= 0 AND confidence <= 1),

    -- Plan structure (stored as JSON)
    steps JSONB NOT NULL DEFAULT '[]'::jsonb,

    -- Estimates
    estimated_total_runtime_seconds INTEGER,
    notes TEXT,

    -- Chain linking
    caused_by_receipt_id TEXT NOT NULL DEFAULT 'NA',
    parent_task_id TEXT NOT NULL DEFAULT 'NA',

    -- Status
    status TEXT NOT NULL DEFAULT 'created'
        CHECK (status IN ('created', 'executing', 'completed', 'failed', 'canceled')),

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,

    -- Unique constraint
    CONSTRAINT unique_plan_per_tenant UNIQUE (tenant_id, plan_id)
);

-- Plan indexes
CREATE INDEX IF NOT EXISTS idx_plans_status ON plans(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_plans_principal ON plans(tenant_id, principal_ai);
CREATE INDEX IF NOT EXISTS idx_plans_created ON plans(tenant_id, created_at DESC);


-- ============================================================================
-- WORKERS TABLE (DeleGate)
-- ============================================================================

CREATE TABLE IF NOT EXISTS workers (
    -- Database internal
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Worker identity
    worker_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,

    -- Worker metadata
    worker_type TEXT NOT NULL,
    capabilities JSONB NOT NULL DEFAULT '[]'::jsonb,
    task_types JSONB NOT NULL DEFAULT '[]'::jsonb,
    description TEXT,
    endpoint TEXT,

    -- Configuration
    is_async BOOLEAN NOT NULL DEFAULT TRUE,
    estimated_runtime_seconds INTEGER NOT NULL DEFAULT 60,

    -- Status
    status TEXT NOT NULL DEFAULT 'unknown'
        CHECK (status IN ('unknown', 'healthy', 'unhealthy')),
    last_seen TIMESTAMPTZ,

    -- Unique constraint
    CONSTRAINT unique_worker_per_tenant UNIQUE (tenant_id, worker_id)
);

-- Worker indexes
CREATE INDEX IF NOT EXISTS idx_workers_type ON workers(tenant_id, worker_type);
CREATE INDEX IF NOT EXISTS idx_workers_status ON workers(tenant_id, status);


-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE receipts IS 'LegiVellum receipt store - immutable audit ledger for task coordination';
COMMENT ON TABLE tasks IS 'AsyncGate task queue - work items waiting for execution';
COMMENT ON TABLE plans IS 'DeleGate plans - structured delegation plans from intents';
COMMENT ON TABLE workers IS 'DeleGate worker registry - known workers for task routing';

-- Grant permissions (adjust as needed)
-- GRANT SELECT, INSERT ON receipts TO memorygate_service;
-- GRANT SELECT, INSERT, UPDATE ON tasks TO asyncgate_service;
-- GRANT SELECT, INSERT, UPDATE ON plans TO delegate_service;
-- GRANT SELECT, INSERT, UPDATE ON workers TO delegate_service;
