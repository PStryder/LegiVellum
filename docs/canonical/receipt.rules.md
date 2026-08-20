# LegiVellum Receipt Protocol Rules (v1)

**Status:** Normative, except where it defers  
**Version:** 1.1  
**Last Updated:** 2026-08-20

> **Where the binding form of a rule lives.** The obligation lifecycle — which
> states exist, which transitions are legal from which state, which are
> contested, and which errors they raise — is defined by
> `legivellum/schemas/transitions.v1.json`, and the principal model by
> `authority.v1.json`. Those files are loaded by the code that evaluates
> transitions. This document previously restated them in prose; the restatements
> drifted and the prose kept describing a system that had been deliberately
> changed. Sections that used to restate them now cite them instead. Field-level
> invariants below remain normative here, because they are enforced from
> `receipt.schema.v1.json` and this is their readable form.

This document defines the normative rules for the LegiVellum Receipt Protocol v1. The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in RFC 2119.

Terminology Note: ReceiptGate is the canonical receipt ledger for LegiVellum
and may be implemented as a MemoryGate profile. This document uses
ReceiptGate terminology throughout.

---

## 1. Core Semantics

Receipts are the **only** coordination protocol in LegiVellum. A receipt is an immutable, auditable record of an obligation lifecycle event.

### 1.1 Phase: `accepted`

**Obligation Creation:**
- An `accepted` receipt MUST create an obligation for the issuer (`source_system`) acting on behalf of `from_principal`.
- The issuer MUST eventually either:
  - resolve the obligation (via `phase: complete`), or
  - transfer responsibility (via `phase: escalate`).

**Required Invariants:**
- `status` MUST be `"NA"`
- `completed_at` MUST be `null`
- `task_summary` MUST NOT be `"TBD"`
- `outcome_kind` MUST be `"NA"`
- All artifact fields (`artifact_pointer`, `artifact_location`, `artifact_mime`) MUST be `"NA"`
- `escalation_class` MUST be `"NA"`
- `escalation_to` MUST be `"NA"`
- `retry_requested` MUST be `false`

### 1.2 Phase: `complete`

**Obligation Resolution:**
- A `complete` receipt MUST resolve the obligation named by its `obligation_id`.
  A `task_id` groups related work and MAY carry several independent obligations
  — fanning one task out to two reviewers creates two — so it does not identify
  what is being discharged. Only the obligation named may be closed.
- Completion MUST indicate the final outcome: `success`, `failure`, or `canceled`.

**Required Invariants:**
- `status` MUST be one of: `"success"`, `"failure"`, `"canceled"`
- `completed_at` MUST be a valid ISO 8601 timestamp (non-null)
- `outcome_kind` MUST be one of: `"none"`, `"response_text"`, `"artifact_pointer"`, `"mixed"`
- If `outcome_kind` is `"artifact_pointer"` or `"mixed"`:
  - `artifact_pointer` MUST NOT be `"NA"`
  - `artifact_location` MUST NOT be `"NA"`
  - `artifact_mime` MUST NOT be `"NA"`
- `escalation_class` MUST be `"NA"` (complete receipts do not escalate)

### 1.3 Phase: `escalate`

**Obligation Transfer:**
- An `escalate` receipt MUST transfer or transform responsibility across a boundary.
- Escalation is LegiVellum's **only soft push mechanism**: the receipt is routed to `recipient_ai = escalation_to`.
- Escalation transfers custody. It does **not** end the obligation: `ESCALATE`
  targets `OPEN`, so the obligation survives under a new custodian.
  Responsibility moved; it did not end, and something is still owed.
- The obligation therefore still requires a `complete` receipt — from whoever
  holds custody after the transfer, not from the issuer who escalated.

**Routing Invariant:**
- `recipient_ai` MUST equal `escalation_to` (this is enforced at the application level)

**Continuation Pattern:**
- The new owner MUST continue the work by issuing new `accepted` task(s) linked via:
  - `parent_task_id` (points to the original task being escalated), and/or
  - `caused_by_receipt_id` (points to the escalation receipt ID)

**Required Invariants:**
- `status` MUST be `"NA"`
- `escalation_class` MUST be one of: `"owner"`, `"capability"`, `"trust"`, `"policy"`, `"scope"`, `"other"`
- `escalation_reason` MUST NOT be `"TBD"`
- `escalation_to` MUST be present (non-`"NA"`)
- `recipient_ai` MUST equal `escalation_to` (routing invariant)

**Escalation Classes:**
- `owner`: Cross-tier delegation (ownership boundary)
- `capability`: Worker lacks required capability
- `trust`: Security/trust domain boundary
- `policy`: Retry limit, timeout, or quota exceeded
- `scope`: Task complexity exceeds current scope
- `other`: Catch-all for other escalation reasons

---

## 2. Delegation vs Escalation

**Delegation (Normal Workflow):**
- Modeled as **new tasks** with `parent_task_id` set to parent task
- Used for routine work breakdown and subtask creation
- Does not imply failure or exceptional conditions

**Escalation (Exception Handling):**
- Used when a component **cannot resolve** a task in its current role/capability/trust domain
- Signals a boundary crossing or capability limitation
- Transfers obligation to a more capable/authorized entity
- MUST include a meaningful `escalation_reason`

---

## 3. Multi-Tenant Identity Model

### 3.1 Tenant Isolation

**Server-Assigned Identity:**
- `tenant_id` MUST be derived by the server from the authenticated principal,
  never from the request body
- `tenant_id` is a required receipt field, so a client necessarily sends one.
  A submitted value that contradicts the credential MUST be refused
  (`TENANT_MISMATCH`) rather than silently overwritten, so a caller learns its
  claim was wrong instead of believing it was honoured. This document previously
  said clients "MUST NOT specify" it, which contradicted
  `receipt.schema.v1.json`, where it is one of the required fields.
- All queries MUST be automatically filtered by the authenticated `tenant_id`
- Receipts MUST be isolated at the database level by `tenant_id`

**Agent Scoping:**
- `recipient_ai` scopes agents **within** a tenant
- The same agent name MAY exist across different tenants without collision
- Example:
  - `tenant_id: "alice", recipient_ai: "kee"` (Alice's Kee instance)
  - `tenant_id: "bob", recipient_ai: "kee"` (Bob's Kee instance, isolated)

### 3.2 Security Model

**Authentication:**
- API implementations MUST extract `tenant_id` from auth tokens (JWT claim or API key mapping)
- Clients MUST NOT be able to override or spoof `tenant_id`
- All database operations MUST include `tenant_id` in WHERE clauses

---

## 4. Derived State (No Explicit Pairing)

LegiVellum does NOT use explicit "pairing" fields. Task state is **derived** from receipt history.

**Obligation State Derivation:**

State is per **obligation**, not per task, and the set of states and the
transitions between them are defined by `transitions.v1.json` — see
`obligation_states` and `transitions` there rather than a copy here.

It is materialised as a projection (`custody_state`) written in the same
transaction as the receipt that causes it, and rebuildable from the receipt
ledger alone. The ledger remains the record; the projection is an index over it.

Two properties are worth stating because they are not obvious from the state
names:

- Reaching a deadline is not a transition. An overdue obligation is still owed
  by the same custodian; nothing has moved. `OVERDUE` is produced by an
  operational event, never proposed as a transition.
- A scan of receipts by `task_id` does not yield state, because one task may
  carry several obligations.

**Provenance Chains:**
- Task relationships are tracked via `parent_task_id` and `caused_by_receipt_id`
- Clients MUST traverse receipts to reconstruct task trees and escalation chains
- All provenance queries MUST be scoped by `tenant_id`

---

## 5. Timestamps and Ordering

**Clock Semantics:**
- `stored_at`: ReceiptGate clock (source of truth for receipt ordering)
- `created_at`: Issuer clock (forensic/debugging only, MAY differ from `stored_at`)
- `started_at`: Execution start time (OPTIONAL, MAY be `null`)
- `completed_at`: Execution completion time (REQUIRED for `phase: complete`, MUST be `null` otherwise)
- `read_at`: Inbox read time (OPTIONAL, MAY be `null`)
- `archived_at`: Archive time (OPTIONAL, MAY be `null`)

**Timestamp Format:**
- All timestamps MUST be ISO 8601 format with timezone (e.g., `"2026-01-04T17:05:00Z"`)
- `null` is used to represent "not applicable" or "not yet set"

**Ordering:**
- Receipt ordering MUST use `stored_at` as the primary sort key
- `created_at` MAY be used as a secondary sort key for receipts with identical `stored_at` values

---

## 6. Retry Semantics

**Retry Requested:**
- If `retry_requested` is `true`, then `attempt` MUST be >= 1
- `attempt` counter starts at 1 for first retry (0 means "not applicable")
- Retry policy (backoff, max attempts) is implementation-defined

**Idempotency:**
- Clients SHOULD use `dedupe_key` to prevent duplicate receipt processing
- `dedupe_key` of `"NA"` means no deduplication is requested

---

## 7. Query Patterns

All queries MUST be scoped by authenticated `tenant_id`.

**Inbox (Active Obligations):**

An inbox is "what do I currently owe", which is a custody question, not a scan
for `accepted` receipts. The query above used to select every `accepted`
receipt addressed to an agent, which returns obligations that agent has since
completed or handed on, and misses those transferred *to* it.

```sql
SELECT o.*, c.state, c.custody_deadline
FROM custody_state c
JOIN obligations o
  ON o.tenant_id = c.tenant_id AND o.obligation_id = c.obligation_id
WHERE c.tenant_id = ?
  AND c.current_custodian = ?
  AND c.state IN ('OPEN', 'OVERDUE');
```

**Task Timeline:**
```sql
SELECT * FROM receipts
WHERE tenant_id = ?
  AND task_id = ?
ORDER BY stored_at, created_at;
```

**Delegation Tree:**
```sql
SELECT * FROM receipts
WHERE tenant_id = ?
  AND parent_task_id = ?
ORDER BY stored_at;
```

**Escalation Chain (Recursive):**
```sql
WITH RECURSIVE escalation_chain AS (
  SELECT * FROM receipts 
  WHERE tenant_id = ? AND receipt_id = ?
  UNION ALL
  SELECT r.* FROM receipts r
  JOIN escalation_chain e ON r.caused_by_receipt_id = e.receipt_id
  WHERE r.tenant_id = ?
)
SELECT * FROM escalation_chain ORDER BY stored_at;
```

---

## 8. Field Size Constraints

**Recommended Limits:**
- `inputs`: < 64 KB (implementation SHOULD enforce via HTTP 413)
- `metadata`: < 16 KB (implementation SHOULD enforce via HTTP 413)
- `task_body`: < 100 KB (implementation SHOULD enforce via HTTP 413)
- `outcome_text`: < 100 KB (implementation SHOULD enforce via HTTP 413)

Implementations MAY enforce these limits at the API layer before database insertion.

---

## 9. Validation Requirements

**Schema Validation:**
- All receipts MUST validate against the receipt schema. The copy that runs is
  the one packaged at `legivellum/schemas/receipt.schema.v1.json`; the copy here
  is asserted identical to it by `LegiVellum/tests/test_protocol_package.py`
- Schema validation MUST be performed before database insertion

**Application-Level Validation:**
- Routing invariant: `recipient_ai` MUST equal `escalation_to` when `phase == "escalate"`
- This invariant MUST be enforced by application logic (not expressible in JSON Schema)

**Error Handling:**
- Invalid receipts MUST be rejected with clear error messages
- Validation errors SHOULD include the specific field and constraint violated

---

## 10. Immutability

**Once Stored, Never Modified:**
- Receipts MUST be immutable after insertion into ReceiptGate
- Updates are modeled as new receipts, not modifications to existing receipts
- Archival (setting `archived_at`) MAY be performed, but the receipt content MUST NOT change

---

## References

- **RFC 2119:** Key words for use in RFCs to Indicate Requirement Levels
- **JSON Schema 2020-12:** https://json-schema.org/draft/2020-12/schema
- **ISO 8601:** Date and time format

---

**Document version:** 1.1  
**Technomancy Laboratories**  
**LegiVellum Project**
