-- AsyncGate Task Queue Schema
-- PostgreSQL DDL for tasks table
-- Version: 1.0
-- Last Updated: 2026-01-04

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create tasks table
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

-- Indexes for common query patterns
CREATE INDEX idx_tasks_status ON tasks(tenant_id, status);
CREATE INDEX idx_tasks_queued ON tasks(tenant_id, status, priority DESC, created_at ASC)
    WHERE status = 'queued';
CREATE INDEX idx_tasks_lease ON tasks(tenant_id, lease_id) WHERE lease_id IS NOT NULL;
CREATE INDEX idx_tasks_worker ON tasks(tenant_id, worker_id) WHERE worker_id IS NOT NULL;
CREATE INDEX idx_tasks_expires ON tasks(tenant_id, lease_expires_at)
    WHERE status = 'leased';
CREATE INDEX idx_tasks_recipient ON tasks(tenant_id, recipient_ai);
CREATE INDEX idx_tasks_type ON tasks(tenant_id, task_type);

-- Comments
COMMENT ON TABLE tasks IS 'AsyncGate task queue - work items waiting for execution';
COMMENT ON COLUMN tasks.task_id IS 'Unique task identifier (T-<ULID>)';
COMMENT ON COLUMN tasks.tenant_id IS 'Tenant isolation key';
COMMENT ON COLUMN tasks.status IS 'Task lifecycle: queued → leased → completed/failed/expired';
COMMENT ON COLUMN tasks.lease_id IS 'Current lease identifier (null if not leased)';
COMMENT ON COLUMN tasks.lease_expires_at IS 'Lease expiry time (task returns to queue if exceeded)';
COMMENT ON COLUMN tasks.attempt IS 'Current attempt number (0 = first try)';
