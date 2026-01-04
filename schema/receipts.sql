-- LegiVellum Receipt Store Schema
-- PostgreSQL DDL for receipts table
-- Version: 1.0
-- Last Updated: 2026-01-04

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create receipts table
CREATE TABLE IF NOT EXISTS receipts (
  -- Database internal (not in wire format)
  uuid UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  
  -- Schema version
  schema_version TEXT NOT NULL DEFAULT '1.0',
  
  -- Multi-tenant support (future-proofing)
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
  
  -- Timestamps (NULL represents "NA" from wire format)
  created_at TIMESTAMPTZ,
  stored_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  read_at TIMESTAMPTZ,
  archived_at TIMESTAMPTZ,
  
  -- Freeform metadata
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  
  -- Constraint: phase-specific validation
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
  
  -- Unique constraint for multi-tenant support
  CONSTRAINT unique_receipt_per_tenant UNIQUE (tenant_id, receipt_id)
);

-- Create indexes (see receipt.indexes.sql for full index definitions)
-- Core indexes (include tenant_id for partition efficiency)
CREATE INDEX idx_receipts_task_id ON receipts(tenant_id, task_id);
CREATE INDEX idx_receipts_recipient_ai ON receipts(tenant_id, recipient_ai);
CREATE INDEX idx_receipts_parent_task_id ON receipts(tenant_id, parent_task_id);
CREATE INDEX idx_receipts_caused_by ON receipts(tenant_id, caused_by_receipt_id);
CREATE INDEX idx_receipts_stored_at ON receipts(tenant_id, stored_at);

-- Composite indexes for optimized queries
CREATE INDEX idx_receipts_inbox ON receipts(tenant_id, recipient_ai, phase, archived_at) 
WHERE phase = 'accepted' AND archived_at IS NULL;

CREATE INDEX idx_receipts_task_phase ON receipts(tenant_id, task_id, phase);
CREATE INDEX idx_receipts_recipient_time ON receipts(tenant_id, recipient_ai, stored_at DESC);

-- Add comments for documentation
COMMENT ON TABLE receipts IS 'LegiVellum receipt store - immutable audit ledger for task coordination';
COMMENT ON COLUMN receipts.uuid IS 'Database internal primary key (not exposed in API)';
COMMENT ON COLUMN receipts.tenant_id IS 'Tenant identifier for multi-tenant isolation. Single-tenant MVP uses default value. Server-assigned from auth token.';
COMMENT ON COLUMN receipts.receipt_id IS 'Client-generated ULID - stable wire identifier';
COMMENT ON COLUMN receipts.task_id IS 'Correlation key for task lifecycle (accepted → escalate → complete)';
COMMENT ON COLUMN receipts.parent_task_id IS 'Links to parent task for delegation trees (NA if root)';
COMMENT ON COLUMN receipts.caused_by_receipt_id IS 'Provenance chain - which receipt spawned this one (NA if none)';
COMMENT ON COLUMN receipts.phase IS 'Lifecycle event: accepted (creates obligation), complete (resolves), escalate (transfers)';
COMMENT ON COLUMN receipts.stored_at IS 'MemoryGate clock - source of truth for ordering';
COMMENT ON COLUMN receipts.escalation_class IS 'Why escalation occurred: owner/capability/trust/policy/scope/other';
COMMENT ON COLUMN receipts.metadata IS 'Freeform JSONB metadata (keep under 16KB recommended)';

-- Grant permissions (adjust as needed for your deployment)
-- GRANT SELECT, INSERT ON receipts TO memorygate_service;
-- GRANT SELECT ON receipts TO asyncgate_service;
-- GRANT SELECT ON receipts TO delegate_service;
