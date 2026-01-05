-- DeleGate Plans Schema
-- PostgreSQL DDL for plans table
-- Version: 1.0
-- Last Updated: 2026-01-04

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create plans table
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

-- Indexes
CREATE INDEX idx_plans_status ON plans(tenant_id, status);
CREATE INDEX idx_plans_principal ON plans(tenant_id, principal_ai);
CREATE INDEX idx_plans_created ON plans(tenant_id, created_at DESC);

-- Comments
COMMENT ON TABLE plans IS 'DeleGate plans - structured delegation plans from intents';
COMMENT ON COLUMN plans.plan_id IS 'Unique plan identifier (plan-<ULID>)';
COMMENT ON COLUMN plans.intent IS 'Original natural language intent';
COMMENT ON COLUMN plans.steps IS 'Plan steps as JSON array';
COMMENT ON COLUMN plans.confidence IS 'Plan confidence score (0.0-1.0)';


-- Create workers table
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

-- Indexes
CREATE INDEX idx_workers_type ON workers(tenant_id, worker_type);
CREATE INDEX idx_workers_status ON workers(tenant_id, status);

-- Comments
COMMENT ON TABLE workers IS 'DeleGate worker registry - known workers for task routing';
COMMENT ON COLUMN workers.worker_id IS 'Unique worker identifier';
COMMENT ON COLUMN workers.capabilities IS 'Worker capabilities as JSON array';
COMMENT ON COLUMN workers.task_types IS 'Supported task types as JSON array';
