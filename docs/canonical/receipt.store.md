# ReceiptGate Receipt Store Specification (MemoryGate profile)

**Version:** 1.0  
**Status:** Normative Implementation Specification  
**Last Updated:** 2026-01-04  
**Purpose:** Define ReceiptGate's role as the passive receipt ledger for LegiVellum

**Terminology Note:** ReceiptGate is the canonical receipt ledger for
LegiVellum and may be implemented as a MemoryGate profile. This document uses
ReceiptGate terminology throughout.

---

## Overview

ReceiptGate is the **single-writer receipt store** and **source of truth** for all coordination in the LegiVellum system.

**Core Responsibilities:**
1. Accept receipt POST requests from components
2. Validate receipts against schema
3. Store receipts in PostgreSQL (append-only ledger)
4. Provide inbox and timeline queries
5. Enable audit trail reconstruction

**What ReceiptGate Is:**
- ✓ Passive ledger (accepts writes, answers queries)
- ✓ Single source of truth for receipts
- ✓ Receipt inbox and timeline provider
- ✓ Audit trail foundation

**What ReceiptGate Is NOT:**
- ✗ Coordinator (does not push notifications)
- ✗ Executor (does not run tasks)
- ✗ Decision maker (does not interpret receipts)
- ✗ State machine (receipts are immutable events, not mutable state)

---

## Design Principles

### 1. Passivity Is Strength

ReceiptGate **never volunteers information**. It only responds to explicit queries.

- Components POST receipts → ReceiptGate validates and stores
- Components query inbox → ReceiptGate returns matching receipts
- Components query timelines → ReceiptGate returns receipt history
- ReceiptGate does NOT push updates or send notifications

MetaGate provides bootstrap configuration; ReceiptGate does not.

### 2. Single Writer

Only ReceiptGate writes to the receipts table. All other components POST receipts to ReceiptGate via API.

This prevents:
- Data corruption from concurrent writes
- Schema validation bypass
- Timestamp inconsistency
- tenant_id spoofing

### 3. Derived State, Not Stored State

ReceiptGate does NOT maintain "task status" or "pairing" as stored fields.

Task state is **derived** from receipt history:
- Open = `accepted` receipt exists AND no `complete` receipt for same `task_id`
- Resolved = `complete` receipt exists for `task_id`
- Escalated = `escalate` receipt exists for `task_id`

Clients reconstruct state via queries, not stored flags.

### 4. Immutability

Receipts are **append-only**. Once stored, they never change.

Updates are modeled as:
- New receipts (e.g., `complete` after `accepted`)
- Archive flag (`archived_at` timestamp)

The only mutable field is `archived_at` (soft delete).

---

## Database Schema

See `/schema/receipts.sql` for the complete DDL.

### Key Design Choices

**Dual Identity System:**
- `uuid` - Database internal primary key (not exposed in API)
- `receipt_id` - Client-generated ULID, stable wire identifier
- Composite unique constraint: `(tenant_id, receipt_id)`

**Multi-Tenant Isolation:**
- `tenant_id` - Required field, server-assigned from auth
- All queries filtered by `tenant_id`
- All indexes lead with `tenant_id` for partition efficiency

**Timestamp Semantics:**
- `stored_at` - ReceiptGate clock, source of truth for ordering
- `created_at` - Issuer clock, forensic only (may be `null`)
- `completed_at` - Required for `phase=complete`, `null` otherwise
- `started_at`, `read_at`, `archived_at` - Optional, may be `null`

**Phase-Based Constraints:**
- Database CHECK constraints enforce phase-specific invariants
- See `schema/receipts.sql` for complete constraint definitions

---

## MCP Tool Surface

Transport: MCP only (no secondary facade in the canonical contract).

### receiptgate.submit_receipt

**Purpose:** Store a new receipt

**Arguments:**
```json
{
  "receipt": {
    "schema_version": "1.0",
    "tenant_id": "pstryder",  // Ignored - server extracts from auth
    "receipt_id": "01HTZQ8S3C8Y8Y1QJQ5Y8Z9F6G",
    "phase": "accepted",
    "...": "Full receipt per schema"
  }
}
```

**Returns (Success):**
```json
{
  "receipt_id": "01HTZQ8S3C8Y8Y1QJQ5Y8Z9F6G",
  "stored_at": "2026-01-04T17:30:00Z",
  "tenant_id": "pstryder"
}
```

**Returns (Validation Error):**
```json
{
  "error": "validation_failed",
  "details": [
    {
      "field": "completed_at",
      "constraint": "must_be_non_null_when_phase_complete",
      "message": "completed_at is required when phase=complete"
    }
  ]
}
```

**Validation Steps:**
1. Extract `tenant_id` from MCP auth context (JWT or API key)
2. Validate against `spec/receipt.schema.v1.json`
3. Enforce application-level constraints:
   - Routing invariant: `recipient_ai == escalation_to` when `phase=escalate`
   - Field size limits (inputs <64KB, metadata <16KB, etc.)
4. Insert with server-assigned `tenant_id` and `stored_at = NOW()`

---

### receiptgate.list_inbox

**Purpose:** Retrieve active obligations for an agent

**Arguments:**
```json
{
  "recipient_ai": "kee",
  "limit": 20
}
```

**Returns:**
```json
{
  "tenant_id": "pstryder",
  "recipient_ai": "kee",
  "count": 3,
  "receipts": [
    {
      "receipt_id": "01HTZQ8S3C8Y8Y1QJQ5Y8Z9F6G",
      "task_id": "T-123",
      "phase": "accepted",
      "stored_at": "2026-01-04T17:30:00Z"
    }
  ]
}
```

**Query:**
```sql
SELECT * FROM receipts
WHERE tenant_id = ? AND
      recipient_ai = ? AND
      phase = 'accepted' AND
      archived_at IS NULL
ORDER BY stored_at DESC
LIMIT ?;
```

---

### receiptgate.bootstrap

**Purpose:** Initialize a new session with configuration and inbox

**Arguments:**
```json
{
  "agent_name": "kee",
  "session_id": "sess-abc123"
}
```

**Returns:**
```json
{
  "tenant_id": "pstryder",
  "agent_name": "kee",
  "session_id": "sess-abc123",
  "config": {
    "receipt_schema_version": "1.0",
    "receiptgate_url": "https://receiptgate.example.com",
    "capabilities": ["receipts", "semantic_memory", "audit"]
  },
  "inbox": {
    "count": 3,
    "receipts": []
  },
  "recent_context": {
    "last_10_receipts": [],
    "recent_patterns": []
  }
}
```

**Purpose:** Provide everything an agent needs to resume work:
- Active obligations (inbox)
- Recent context (last actions)
- Configuration (endpoints, schema version)

---

### receiptgate.list_task_receipts

**Purpose:** Retrieve all receipts for a task (lifecycle timeline)

**Arguments:**
```json
{
  "task_id": "T-123",
  "sort": "asc"
}
```

**Returns:**
```json
{
  "tenant_id": "pstryder",
  "task_id": "T-123",
  "receipts": [
    {"receipt_id": "...", "phase": "accepted", "stored_at": "..."},
    {"receipt_id": "...", "phase": "complete", "stored_at": "..."}
  ]
}
```

**Query:**
```sql
SELECT * FROM receipts
WHERE tenant_id = ? AND task_id = ?
ORDER BY stored_at ASC;
```

---

### receiptgate.get_receipt_chain

**Purpose:** Retrieve escalation/causation chain (recursive provenance)

**Arguments:**
```json
{
  "receipt_id": "01HTZQ9A7J6Z3F7C5N8V1K2M3P"
}
```

**Returns:**
```json
{
  "root_receipt_id": "01HTZQ9A7J6Z3F7C5N8V1K2M3P",
  "chain": [
    {"receipt_id": "...", "caused_by_receipt_id": "NA"},
    {"receipt_id": "...", "caused_by_receipt_id": "..."}
  ]
}
```

**Query (PostgreSQL Recursive CTE):**
```sql
WITH RECURSIVE chain AS (
  SELECT * FROM receipts 
  WHERE tenant_id = ? AND receipt_id = ?
  UNION ALL
  SELECT r.* FROM receipts r
  JOIN chain c ON r.caused_by_receipt_id = c.receipt_id
  WHERE r.tenant_id = ?
)
SELECT * FROM chain ORDER BY stored_at;
```

---

## Indexes

See `/spec/receipt.indexes.sql` for complete index definitions.

**Core indexes (all lead with `tenant_id`):**
1. `idx_receipts_task_id` - Task lifecycle queries
2. `idx_receipts_recipient_ai` - Inbox queries
3. `idx_receipts_parent_task_id` - Delegation tree traversal
4. `idx_receipts_caused_by` - Provenance chains
5. `idx_receipts_stored_at` - Chronological ordering

**Composite indexes:**
6. `idx_receipts_inbox` - Partial index for active accepted receipts
7. `idx_receipts_task_phase` - Task + phase queries
8. `idx_receipts_recipient_time` - Recent inbox items (DESC ordering)

---

## Validation Rules

### Schema Validation

All receipts MUST validate against `/spec/receipt.schema.v1.json`.

Validation performed on POST:
1. JSON Schema validation
2. Application-level constraints (routing invariant)
3. Field size limits (HTTP 413 if exceeded)

### Application-Level Constraints

**Routing Invariant (Phase: escalate):**
```python
if receipt["phase"] == "escalate":
    if receipt["recipient_ai"] != receipt["escalation_to"]:
        raise ValidationError("recipient_ai must equal escalation_to")
```

**Field Size Limits:**
- `inputs`: < 64 KB
- `metadata`: < 16 KB
- `task_body`: < 100 KB
- `outcome_text`: < 100 KB

Enforced at API layer before database insertion.

---

## Error Handling

### Validation Errors (400 Bad Request)

```json
{
  "error": "validation_failed",
  "details": [
    {
      "field": "completed_at",
      "constraint": "required_for_phase_complete",
      "message": "completed_at is required when phase=complete"
    }
  ]
}
```

### Duplicate Receipt ID (409 Conflict)

```json
{
  "error": "duplicate_receipt_id",
  "receipt_id": "01HTZQ8S3C8Y8Y1QJQ5Y8Z9F6G",
  "message": "Receipt with this ID already exists"
}
```

### Unauthorized (401/403)

```json
{
  "error": "unauthorized",
  "message": "Invalid or missing authentication token"
}
```

### Database Unavailable (503 Service Unavailable)

```json
{
  "error": "database_unavailable",
  "message": "Receipt store temporarily unavailable"
}
```

---

## Security Model

### Authentication

- All MCP tool calls require authentication
- JWT or API key is presented via MCP transport metadata
- `tenant_id` extracted from auth context, never from request body

### Authorization

- Users can only access receipts in their `tenant_id`
- All queries automatically filtered by authenticated `tenant_id`
- Cross-tenant access prevented at database level

### Audit

- All receipt POST operations logged
- Immutable ledger provides complete audit trail
- External audit API for compliance (future)

---

## Implementation Checklist

**Phase 1: Core Receipt Store**
- [x] PostgreSQL schema with CHECK constraints
- [ ] POST /receipts endpoint with validation
- [ ] GET /inbox endpoint
- [ ] Authentication middleware (JWT/API key)
- [ ] Schema validation integration
- [ ] Error handling and logging

**Phase 2: Query APIs**
- [ ] GET /receipts/task/:task_id
- [ ] GET /receipts/chain/:receipt_id
- [ ] POST /bootstrap endpoint
- [ ] Pagination support
- [ ] Query performance optimization

**Phase 3: Production Hardening**
- [ ] Rate limiting
- [ ] Database connection pooling
- [ ] Metrics and monitoring
- [ ] Backup and recovery procedures
- [ ] External audit API

---

## References

- `/spec/receipt.schema.v1.json` - Receipt JSON Schema
- `/spec/receipt.rules.md` - Protocol rules and semantics
- `/spec/receipt.indexes.sql` - Database indexes
- `/schema/receipts.sql` - PostgreSQL DDL

---

*Document version: 1.0*  
*Technomancy Laboratories*  
*LegiVellum Project*
