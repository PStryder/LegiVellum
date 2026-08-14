-- Problemata Control Registry (v1)
-- Stores compiled/validated Problemata specs with validation results.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS problemata_registry (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    problemata_id TEXT NOT NULL,
    version TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('validated', 'rejected')),
    source TEXT NOT NULL,
    spec_hash TEXT,
    validation JSONB NOT NULL,
    spec JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT unique_problemata_registry_id UNIQUE (problemata_id)
);

CREATE INDEX IF NOT EXISTS idx_problemata_registry_status ON problemata_registry(status);
CREATE INDEX IF NOT EXISTS idx_problemata_registry_created_at ON problemata_registry(created_at);
CREATE INDEX IF NOT EXISTS idx_problemata_registry_updated_at ON problemata_registry(updated_at);
