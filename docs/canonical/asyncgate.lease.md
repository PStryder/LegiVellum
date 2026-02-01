# AsyncGate Lease Protocol

**Version:** 1.0  
**Status:** Draft Specification  
**Last Updated:** 2026-01-04

## Overview

AsyncGate coordinates work execution through a **lease-based polling model**. Workers poll for available tasks, receive task offers, and accept work by emitting receipts. The lease mechanism is internal to AsyncGate—it manages work-in-flight without polluting the receipt ledger with transient state.

Receipt ledger: All receipts are emitted to ReceiptGate (the canonical ledger, which may be implemented as a MemoryGate profile).

Transport: All primitive-to-primitive interactions use MCP. The HTTP shapes
below describe the canonical request/response payloads and tool semantics.

## Core Principle

> **Offers are transient. Acceptance creates obligation.**

- AsyncGate offers tasks via polling (ephemeral, no receipt)
- Workers accept tasks via receipts (durable, auditable)
- Lease mechanics are internal coordination, not protocol

---

## Worker Poll Contract

### Endpoint

```
POST /lease
```

### Request Format

```json
{
  "worker_id": "worker.codegen-aws-i-1234567",
  "capabilities": ["python", "rust", "code-generation"],
  "max_tasks": 1,
  "preferred_kinds": ["code.generate", "code.refactor"]
}
```

**Fields:**

- `worker_id` (required): Unique worker instance identifier
  - Format: `{worker_type}.{instance_id}`
  - Example: `"worker.codegen-aws-i-1234567"`
  - Must be stable across restarts if worker wants to reclaim orphaned leases

- `capabilities` (optional): Array of capability tags
  - Used for task matching/routing
  - Examples: `["python", "rust"]`, `["code-review"]`, `["data-analysis"]`
  - AsyncGate MAY use for smart task assignment
  - Not enforced—workers can accept any task

- `max_tasks` (optional, default: 1): Maximum tasks to return in one poll
  - V1 implementation SHOULD only support `max_tasks: 1`
  - Future: enable batch leasing for high-throughput workers

- `preferred_kinds` (optional): Array of `task_type` values worker prefers
  - Examples: `["code.generate"]`, `["data.analyze", "data.transform"]`
  - AsyncGate MAY prioritize matching tasks
  - Not enforced—worker may receive any task_type

### Response Formats

#### No Work Available

```
HTTP/1.1 204 No Content
```

Empty body. Worker should poll again after backoff interval.

#### Task Offer

```
HTTP/1.1 200 OK
Content-Type: application/json

{
  "lease_id": "lease-01HTZQX7Y8Z9A0B1C2D3E4F5G6",
  "lease_expires_at": "2026-01-04T15:45:00Z",
  "task": {
    "task_id": "T-01HTZQ8S3C8Y8Y1QJQ5Y8Z9F6G",
    "principal_ai": "delegate.root",
    "task_type": "code.generate",
    "task_summary": "Generate Python function for CSV parsing",
    "task_body": "Create a function that reads CSV...",
    "payload_pointer": "depotgate://artifact/01HTZQ8S3C8Y8Y1QJQ5Y8Z9F6G",
    "inputs": {
      "language": "python",
      "framework": "pandas"
    },
    "expected_outcome_kind": "artifact_pointer",
    "expected_artifact_mime": "text/x-python"
  }
}
```

**Fields:**

- `lease_id`: Unique identifier for this lease (internal AsyncGate tracking)
- `lease_expires_at`: ISO 8601 timestamp when lease expires
- `task`: Task details (NOT a full receipt—just work specification)
  - `task.principal_ai`: Principal that owns the task/obligation
  - `task.payload_pointer`: Optional pointer to payload/artifacts in DepotGate

**Critical:** This is an **offer**, not a receipt. No obligation created yet.

---

## Lease Lifecycle

### 1. Lease Grant (Polling)

Worker polls → AsyncGate finds available task → assigns lease → returns offer

**AsyncGate internal state:**
```
task_queue:
  task_id: "T-123"
  status: "leased"
  lease_id: "lease-456"
  worker_id: "worker.codegen-123"
  lease_granted_at: "2026-01-04T15:30:00Z"
  lease_expires_at: "2026-01-04T15:45:00Z"  # 15 min default
```

### 2. Worker Acceptance

Worker receives offer → emits `accepted` receipt to ReceiptGate:

```json
{
  "phase": "accepted",
  "task_id": "T-123",
  "recipient_ai": "worker.codegen",
  "source_system": "worker.codegen-123",
  ...
}
```

**This creates the obligation.** Worker is now accountable via receipt ledger.

### 3. Heartbeat (Optional v1, Required v2)

**V1 (Simple):**
- No explicit heartbeat
- Lease duration = estimated task completion time
- If worker doesn't complete before expiry → lease expires → task requeued

**V2 (Production):**
- Worker sends periodic heartbeats: `POST /lease/{lease_id}/heartbeat`
- Extends `lease_expires_at`
- Enables long-running tasks without large initial lease duration

### 4. Completion

Worker finishes work → emits `complete` receipt to ReceiptGate:

```json
{
  "phase": "complete",
  "task_id": "T-123",
  "status": "success",
  "outcome_kind": "artifact_pointer",
  "artifact_location": "s3://bucket/result.py",
  ...
}
```

AsyncGate detects completion (by polling ReceiptGate for receipts) → marks lease as complete → removes from active leases.

### 5. Lease Expiry (Orphan Detection)

If `now() > lease_expires_at` and no `complete` receipt exists:

1. AsyncGate marks lease as expired
2. Task returns to `queued` status (or `retry_pending` if retries configured)
3. Task becomes available for new lease grant
4. If late `complete` receipt arrives, AsyncGate handles idempotently (deduplication via `dedupe_key`)

---

## Offer vs Acceptance Model

### Why Separate?

**Offer (via polling):**
- Ephemeral assignment
- No audit trail (just internal AsyncGate state)
- Worker can ignore/crash/timeout with no protocol-level consequence

**Acceptance (via receipt):**
- Durable commitment
- Audit trail in ReceiptGate
- Protocol-level obligation created
- Enables provenance tracking, delegation chains, escalation

### Worker Behavior

**Correct flow:**
```
1. Poll AsyncGate → receive offer
2. Validate can do work (capability check, resource check)
3. Emit `accepted` receipt to ReceiptGate
4. Do work
5. Emit `complete` receipt to ReceiptGate
```

**Edge cases:**

**Worker receives offer but can't accept:**
```
1. Poll → receive offer
2. Realize insufficient memory/capabilities
3. Simply don't emit `accepted` receipt
4. Lease expires → task requeued → no harm
```

**Worker crashes after accepting:**
```
1. Poll → receive offer
2. Emit `accepted` receipt
3. Worker crashes
4. Lease expires → AsyncGate detects orphan
5. Emit `escalate` receipt (escalation_class: "policy", reason: "lease_expired")
6. Task requeued for retry (or escalated to supervisor)
```

---

## Lease Configuration

### Default Parameters (V1)

- **Lease Duration:** 15 minutes (900 seconds)
- **Poll Backoff:** 
  - No work: 5 seconds
  - Work received: immediate (worker busy)
  - Error: exponential backoff (5s → 10s → 20s → 40s, max 60s)
- **Max Retries:** 3 attempts per task
- **Requeue Delay:** 30 seconds after lease expiry before retry

### Tuning Considerations

**Short tasks (<1 min):**
- Lease duration: 2 minutes
- Enables fast retry on worker failure

**Long tasks (>10 min):**
- Lease duration: 30-60 minutes
- Requires heartbeat in V2
- Or: emit progress receipts (future: `phase: progress`)

**High-throughput workers:**
- Batch leasing (`max_tasks > 1`)
- Reduces polling overhead

---

## Error Handling

### AsyncGate Errors

**No database connection:**
```
HTTP/1.1 503 Service Unavailable
{"error": "database_unavailable"}
```

Worker should retry with exponential backoff.

**Invalid worker_id format:**
```
HTTP/1.1 400 Bad Request
{"error": "invalid_worker_id", "detail": "must match pattern {type}.{instance}"}
```

**Internal error:**
```
HTTP/1.1 500 Internal Server Error
{"error": "internal_error"}
```

Worker should retry with exponential backoff.

### Worker Responsibilities

- **Poll regularly** (but respect backoff on 204/503)
- **Emit `accepted` receipt** before starting work
- **Emit `complete` receipt** on finish (success or failure)
- **Handle `task_type` gracefully** (ignore unsupported types, or emit escalate receipt)
- **Respect lease expiry** (don't emit `complete` hours after lease expired—use `dedupe_key` for idempotency)

---

## Implementation Notes

### AsyncGate Internal State

AsyncGate maintains **transient** lease state (in-memory or Redis):

```
active_leases:
  lease_id → {task_id, worker_id, expires_at, granted_at}

task_queue:
  task_id → {status, lease_id, attempt, retry_after}
```

This state is **not in ReceiptGate**. It's coordination machinery.

### Receipt Emission Rules

AsyncGate emits receipts for:

1. **Task Queued** (optional, informational):
   - `phase: accepted` from AsyncGate to itself
   - Indicates task entered queue
   - V1: skip this, too noisy

2. **Lease Expired** (worker didn't complete):
   - `phase: escalate`
   - `escalation_class: policy`
   - `escalation_reason: lease_expired`
   - Routes to retry logic or supervisor

3. **Max Retries Exceeded**:
   - `phase: escalate`
   - `escalation_class: policy`
   - `escalation_reason: max_retries_exceeded`
   - Routes to DLQ or supervisor for cognitive intervention

---

## Future Enhancements

### V2 Features

- **Heartbeat endpoint:** `POST /lease/{lease_id}/heartbeat`
- **Batch leasing:** `max_tasks > 1` support
- **Priority queues:** `task_priority` field for urgent work
- **Affinity hints:** route retry to same worker if possible
- **Progress receipts:** `phase: progress` for long-running tasks

### Advanced Patterns

- **Speculative execution:** Lease same task to 2 workers, first to complete wins
- **Preemption:** Revoke lease if higher-priority task arrives
- **Worker health scoring:** Track completion rates, adjust assignment

---

## Summary

**What's in receipts:**
- Task acceptance (`phase: accepted`)
- Task completion (`phase: complete`)
- Escalation on failure (`phase: escalate`)

**What's NOT in receipts:**
- Lease assignment (transient)
- Heartbeats (transient)
- Queue position (transient)
- Worker polling (transient)

**The protocol is clean: Workers poll, receive offers, accept via receipts, complete via receipts.**

Everything else is internal AsyncGate coordination machinery.

---

*Document version: 1.0*  
*Technomancy Laboratories*  
*Part of the LegiVellum Trilogy*
