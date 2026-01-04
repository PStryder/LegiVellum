-- LegiVellum Receipt Store Indexes
-- PostgreSQL index definitions for optimal query performance
-- Version: 1.0
-- Last Updated: 2026-01-04
-- Note: All indexes include tenant_id for multi-tenant partition efficiency

-- Core indexes for common query patterns

-- 1. Task correlation (find all receipts for a task within tenant)
CREATE INDEX idx_receipts_task_id ON receipts(tenant_id, task_id);

-- 2. Inbox queries (find active obligations for a recipient within tenant)
CREATE INDEX idx_receipts_recipient_ai ON receipts(tenant_id, recipient_ai);

-- 3. Delegation tree traversal (find child tasks within tenant)
CREATE INDEX idx_receipts_parent_task_id ON receipts(tenant_id, parent_task_id);

-- 4. Provenance chains (trace causation within tenant)
CREATE INDEX idx_receipts_caused_by ON receipts(tenant_id, caused_by_receipt_id);

-- 5. Chronological ordering (recent receipts, timeline queries within tenant)
CREATE INDEX idx_receipts_stored_at ON receipts(tenant_id, stored_at);

-- Composite indexes for optimized query patterns

-- 6. Inbox filtering (tenant + recipient + phase + archive status)
-- Optimizes: "SELECT * FROM receipts WHERE tenant_id = ? AND recipient_ai = ? AND phase = 'accepted' AND archived_at IS NULL"
CREATE INDEX idx_receipts_inbox ON receipts(tenant_id, recipient_ai, phase, archived_at) 
WHERE phase = 'accepted' AND archived_at IS NULL;

-- 7. Task lifecycle queries (tenant + task + phase)
-- Optimizes: "SELECT * FROM receipts WHERE tenant_id = ? AND task_id = ? AND phase = 'complete'"
CREATE INDEX idx_receipts_task_phase ON receipts(tenant_id, task_id, phase);

-- 8. Recent inbox items (tenant + recipient + timestamp)
-- Optimizes: "SELECT * FROM receipts WHERE tenant_id = ? AND recipient_ai = ? ORDER BY stored_at DESC"
CREATE INDEX idx_receipts_recipient_time ON receipts(tenant_id, recipient_ai, stored_at DESC);

-- Optional: Full-text search on task_summary and task_body
-- Uncomment if you need text search capabilities
-- CREATE INDEX idx_receipts_task_summary_fts ON receipts USING gin(to_tsvector('english', task_summary));
-- CREATE INDEX idx_receipts_task_body_fts ON receipts USING gin(to_tsvector('english', task_body));

-- Notes:
-- - All indexes assume the receipts table already exists (see schema/receipts.sql)
-- - The partial index (idx_receipts_inbox) only indexes active accepted receipts
-- - DESC ordering on idx_receipts_recipient_time supports ORDER BY stored_at DESC
-- - Add additional indexes based on actual query patterns in production
-- - tenant_id leading position enables efficient partition pruning in future multi-tenant deployments
