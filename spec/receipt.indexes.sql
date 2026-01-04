-- LegiVellum Receipt Indexes (PostgreSQL)
-- Assumes a table named `receipts` with columns matching the receipt schema (snake_case).
-- Adjust table/column names as needed.

-- Core lookup: task lifecycle timeline
CREATE INDEX IF NOT EXISTS idx_receipts_task_id ON receipts (task_id);

-- Inbox queries
CREATE INDEX IF NOT EXISTS idx_receipts_recipient_ai ON receipts (recipient_ai);
CREATE INDEX IF NOT EXISTS idx_receipts_recipient_phase ON receipts (recipient_ai, phase);

-- Delegation / tree traversal
CREATE INDEX IF NOT EXISTS idx_receipts_parent_task_id ON receipts (parent_task_id);

-- Provenance graph traversal
CREATE INDEX IF NOT EXISTS idx_receipts_caused_by_receipt_id ON receipts (caused_by_receipt_id);

-- Recent activity
CREATE INDEX IF NOT EXISTS idx_receipts_stored_at ON receipts (stored_at);

-- Optional composite for fast "open tasks" scans (depends on workload)
-- CREATE INDEX IF NOT EXISTS idx_receipts_task_phase_attempt ON receipts (task_id, phase, attempt);
