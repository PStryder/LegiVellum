# Receipt Protocol Rules v1.0

**LegiVellum Receipt Contract: Invariants and Semantics**

---

## Core Invariants

### 1. Phase Lifecycle

A receipt has exactly one `phase`:
- **`accepted`** — Creates an obligation
- **`complete`** — Resolves an obligation
- **`escalate`** — Transfers/transforms an obligation

### 2. Phase-Specific Requirements

**When `phase = "accepted"`:**
- `status` MUST be `"NA"`
- `completed_at` MUST be `"NA"`
- `task_summary` MUST NOT be `"TBD"` (inbox items require meaningful summaries)
- `escalation_class` MUST be `"NA"`

**When `phase = "complete"`:**
- `status` MUST be one of: `success`, `failure`, `canceled`
- `completed_at` MUST be a valid ISO 8601 timestamp
- `outcome_kind` MUST NOT be `"NA"`
- `escalation_class` MUST be `"NA"`

**When `phase = "escalate"`:**
- `status` MUST be `"NA"`
- `escalation_class` MUST NOT be `"NA"`
- `escalation_reason` MUST NOT be `"TBD"`

### 3. Artifact Pointer Contract

When `outcome_kind` includes `"artifact_pointer"` or `"mixed"`:
- `artifact_pointer` MUST NOT be `"NA"`
- `artifact_location` MUST NOT be `"NA"`

### 4. Escalation Class Requirements

When `escalation_class = "owner"` (ownership boundary crossing):
- `escalation_to` MUST NOT be `"NA"`
- `recipient_ai` MUST equal `escalation_to` (inbox must match transfer target)

When `retry_requested = true`:
- `attempt` MUST be >= 1
- New accepted receipt should increment `attempt` field

---

## Escalation Semantics

**Critical Rule: Escalation is a boundary signal, not an execution command.**

### The Escalation Handoff Protocol

**1. `accepted` creates obligation**
- Component receives a task
- Component emits `accepted` receipt
- This creates the component's obligation to either `complete` or `escalate`

**2. Issuer satisfies obligation by `complete` or `escalate`**
- If component can resolve: emit `complete` receipt
- If component cannot resolve: emit `escalate` receipt

**3. `escalate` must target a new `recipient_ai` (soft push)**
- Escalation receipt sets `escalation_to` to new owner
- Escalation receipt sets `recipient_ai` to new owner (lands in their inbox)
- **This ends the issuer's obligation**

**4. Receiver must respond by issuing a new `accepted` task**
- New owner sees `escalate` receipt in inbox
- New owner MUST emit a **new** `accepted` receipt that:
  - Uses a **new `task_id`** (fresh obligation instance, recommended)
  - Sets `parent_task_id` to original task_id
  - Sets `caused_by_receipt_id` to escalation receipt_id
- Alternative: reuse same `task_id` (continuation, but blurs obligation tracking)

### Why This Matters

**Escalation transfers responsibility WITHOUT executing anything.**

The escalate receipt is NOT:
- An instruction to execute
- A scheduled task
- An automatic retry

The escalate receipt IS:
- A boundary crossing event
- A transfer of ownership
- A signal requiring explicit acknowledgment

The receiving component must **actively accept** the escalated obligation by creating a new `accepted` receipt. This provides:
- Clean responsibility boundaries
- Explicit acknowledgment chains
- Full audit trails
- No accidental "push execution" behavior

---

## Pairing and Lifecycle Queries

**LegiVellum does NOT use explicit pairing fields.**

Relationships are derived via query on `task_id`:

```sql
-- Find all receipts for a task lifecycle
SELECT * FROM receipts WHERE task_id = ? ORDER BY stored_at;

-- Find completion for a task (if exists)
SELECT * FROM receipts WHERE task_id = ? AND phase = 'complete';

-- Find inbox items (active obligations)
SELECT * FROM receipts 
WHERE recipient_ai = ? 
  AND phase = 'accepted' 
  AND archived_at IS NULL;
```

---

## Field Constraints

### Forbidden Values (Policy)

The following fields MUST NOT be `"NA"` or `"TBD"`:
- `receipt_id`
- `task_id`
- `from_principal`
- `for_principal`
- `source_system`
- `recipient_ai`

### Size Limits (Recommended)

To prevent payload bloat, use artifact pointers for large data:
- `inputs`: < 64KB
- `metadata`: < 16KB
- `task_body`: < 100KB
- `outcome_text`: < 100KB

Validation enforced at API layer (HTTP 413 Payload Too Large).

---

## Escalation Classes

**`owner`** — Cross-tier/cross-component delegation
- Worker → DeleGate
- Basic tier → Advanced tier
- Requires: `escalation_to` set to new owner

**`capability`** — Worker lacks required capability
- Example: "Requires GPU for inference", "Needs database access"
- Specify missing capability in `escalation_reason`

**`trust`** — Security/permission boundary
- Example: Task requires elevated privileges, crosses trust domain

**`policy`** — Retry, timeout, quota, backoff
- Often paired with `retry_requested = true`
- Example: Rate limit hit, temporary failure, resource exhaustion

**`scope`** — Task too large/complex for current tier
- Example: "Requires breaking into subtasks", "Exceeds worker memory limits"

**`other`** — Undefined/catchall
- Use when none of the above fit
- Document clearly in `escalation_reason`

---

## Timestamp Semantics

**`created_at`** — Issuer clock (when receipt formed)
- May have clock skew between components

**`stored_at`** — MemoryGate clock (when persisted)
- **SOURCE OF TRUTH** for ordering
- Used for all chronological queries

**`started_at`** — Execution start time
- Optional, set by workers

**`completed_at`** — Completion time
- Required when `phase = "complete"`

**`read_at`** — Inbox read tracking
- Optional, UX feature

**`archived_at`** — Archive time
- Lifecycle management

---

## Identity Model

**`receipt_id`** — Wire identifier
- Client-generated ULID (26 chars, sortable)
- Enables offline operation
- Enables idempotent retries

**`uuid`** — Database internal (NOT in wire format)
- Server-assigned PostgreSQL `gen_random_uuid()`
- Primary key
- Not exposed in API

---

**Version:** 1.0  
**Last Updated:** 2026-01-04  
**Technomancy Laboratories**
