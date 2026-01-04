# LegiVellum Receipt Protocol (v1)

Receipts are the **only** coordination protocol in LegiVellum. A receipt is an immutable, auditable record of an obligation being accepted, completed, or escalated across a boundary.

## Multi-Tenant Identity Model

### `tenant_id`
- **Server-assigned** from authenticated context, never from client request
- Enables multi-tenant isolation at database level
- **MVP default**: `"pstryder"` (single tenant)
- **Future**: Each user/org gets unique `tenant_id`

### Agent Scoping
- `recipient_ai` scopes agents **within** a tenant
- Same agent name can exist across tenants without collision
- Examples:
  - `tenant_id: "pstryder", recipient_ai: "kee"`
  - `tenant_id: "pstryder", recipient_ai: "hexy"`
  - `tenant_id: "alice", recipient_ai: "kee"` (different tenant, same agent name)

### Security Model
- API extracts `tenant_id` from auth token (JWT claim or API key mapping)
- Client cannot specify `tenant_id` in request
- All queries automatically filtered by authenticated `tenant_id`
- Receipts are tenant-isolated at database level

## Core Semantics

### `phase: accepted`
- **Creates an obligation** for the issuer (`source_system`) on behalf of `from_principal`.
- The issuer must eventually either:
  - resolve the obligation (`phase: complete`), or
  - transfer responsibility (`phase: escalate`).

### `phase: complete`
- **Resolves** the obligation created by `accepted` for the same `task_id`.
- Completion must include `status` (`success|failure|canceled`) and `completed_at`.
- Outcomes are expressed as:
  - `outcome_text` (response),
  - `artifact_pointer` (+ `artifact_location`, `artifact_mime`, optional checksum), or
  - both (`mixed`).

### `phase: escalate`
- **Transfers or transforms responsibility** across a boundary.
- Escalation is LegiVellum's only **soft push**:
  - the receipt is routed to `recipient_ai = escalation_to`.
  - the receiver did not issue the escalation receipt.
- **Ends the issuer's obligation** for that task instance *if* the escalation targets a valid inbox owner.
- Escalation does **not** require its own completion receipt.
- The new owner continues the work by issuing new `accepted` tasks linked back via:
  - `parent_task_id` (points at the task being escalated), and/or
  - `caused_by_receipt_id` (points at the escalation receipt).

## Delegation vs Escalation

- **Delegation** (normal workflow) is modeled as **new tasks** with `parent_task_id` set.
- **Escalation** is an **exception condition** used when a component cannot resolve a task in its current role/capability/trust domain.

## Derived State (no pairing)

LegiVellum does not require explicit “pairing” fields.

A task is considered:
- **Open** if there exists an `accepted` receipt for `task_id` and no `complete` receipt for the same `task_id` (optionally per `attempt`).
- **Resolved** if there exists a `complete` receipt for `task_id`.

## Mechanical Invariants (MUST)

1. `receipt_id`, `task_id`, `from_principal`, `for_principal`, `source_system`, `recipient_ai` must be meaningful strings (not `"NA"`/`"TBD"`).
2. If `phase == "complete"`:
   - `status` MUST be `success|failure|canceled`
   - `completed_at` MUST be non-null
   - `outcome_kind` MUST be non-NA
3. If `outcome_kind in {"artifact_pointer","mixed"}`:
   - `artifact_location`, `artifact_pointer`, `artifact_mime` MUST be non-NA
4. If `phase == "escalate"`:
   - `escalation_class` MUST be non-NA
   - `escalation_to` MUST be present
   - `recipient_ai` MUST equal `escalation_to` (routing invariant)

## Query Patterns

All queries are automatically scoped by `tenant_id` from authenticated context:

- **Inbox**: `tenant_id = ? AND recipient_ai = ? AND archived_at IS NULL AND phase != 'complete'`
- **Task timeline**: `tenant_id = ? AND task_id = ? ORDER BY stored_at, created_at`
- **Delegation tree**: `tenant_id = ? AND parent_task_id = ?`
- **Provenance trace**: follow `caused_by_receipt_id` within same `tenant_id` (application recursion)

Where `tenant_id` is extracted from authentication, not client input.

