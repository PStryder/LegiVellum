# LegiVellum Specification Compliance Report

This report documents conflicts and discrepancies between the standalone project implementations and the LegiVellum specification.

**Generated:** 2026-01-07

## Executive Summary

| Component | Compliance Status | Critical Issues | Notes |
|-----------|------------------|-----------------|-------|
| **AsyncGate** | Partial | 2 | Receipt model differs, missing `principal_ai` field |
| **memorygate** | Non-Compliant | 3 | No receipt protocol, no inbox, semantic memory focus |
| **CogniGate** | Partial | 2 | Receipt model differs, may mint obligations |
| **DepotGate** | Compliant | 0 | Follows spec correctly |
| **MetaGate** | Compliant | 0 | Follows spec correctly |

---

## Detailed Findings

### 1. AsyncGate (F:\HexyLab\AsyncGate)

**Role per spec:** Async boundary / time decoupling. Holds tasks until claimed, provides leases and completions.

#### Conflicts Found

| Issue | Severity | Description |
|-------|----------|-------------|
| Receipt Schema Mismatch | HIGH | Standalone AsyncGate does not use LegiVellum receipt schema. Uses internal `Receipt` model with different fields. |
| Missing `recipient_ai` field | HIGH | LegiVellum receipts require `recipient_ai` for routing. Standalone uses `Principal` model with `kind/id/instance_id`. |
| Missing `principal_ai` in tasks | MEDIUM | Spec requires `principal_ai` in task submission. Standalone uses `created_by: Principal`. |
| Missing `payload_pointer` pattern | MEDIUM | Spec says tasks include `payload_pointer` to DepotGate artifacts. Standalone embeds `payload: dict` directly. |
| Missing MemoryGate integration | MEDIUM | Spec says completion emits receipts to MemoryGate. Standalone has optional `receipt_mode` but no MemoryGate client. |

#### LegiVellum Spec Reference (from Updated Specifications)
```
Accept tasks. Clients (Principals or DeleGates) enqueue tasks into AsyncGate
via POST /tasks. A task includes at minimum task_id, principal_ai, tenant_id,
payload_pointer (e.g., to a plan step or input stored in DepotGate) and an
optional not_before timestamp.
```

#### Actual Implementation
```python
# AsyncGate uses different task model:
class Task(BaseModel):
    task_id: UUID
    tenant_id: UUID
    type: str
    payload: dict[str, Any]  # NOT payload_pointer
    created_by: Principal    # NOT principal_ai
```

---

### 2. memorygate (F:\HexyLab\memorygate)

**Role per spec:** Authoritative receipt ledger. Stores every receipt, provides inbox queries, validates receipts.

#### Conflicts Found

| Issue | Severity | Description |
|-------|----------|-------------|
| No Receipt Protocol | CRITICAL | memorygate is a semantic memory service, NOT a receipt ledger. No receipt storage/validation. |
| No `/receipts` Endpoint | CRITICAL | Spec requires `POST /receipts` for receipt submission. Not implemented. |
| No `/inbox` Endpoint | CRITICAL | Spec requires `GET /inbox` for principal inbox queries. Not implemented. |
| No Receipt Schema | CRITICAL | Does not implement LegiVellum receipt schema with phases (accepted/complete/escalate). |
| Different Purpose | CRITICAL | memorygate focuses on vector search, observations, patterns, concepts - not receipts. |

#### What memorygate Actually Does
- Vector-based semantic search (`memory_search`)
- Store observations and documents with embeddings
- Concept management and relationships
- Pattern tracking
- Session management

#### What LegiVellum Requires
```
MemoryGate is the authoritative ledger of the LegiVellum system. It stores
every receipt emitted by Principals, DeleGates, CogniGates, AsyncGate,
MetaGate and DepotGate. It is the source of truth for what has happened and when.

Responsibilities:
- Accept and validate receipts via POST /receipts
- Store receipts immutably
- Provide durable queries (GET /inbox, GET /receipts/task/:task_id, GET /receipts/chain/:receipt_id)
```

#### Resolution Required
The standalone `memorygate` project is a **different service** than LegiVellum's MemoryGate primitive. Either:
1. Rename standalone to `SemanticMemory` or similar
2. Add receipt ledger functionality to standalone memorygate
3. Create a separate LegiVellum-compliant MemoryGate service

---

### 3. CogniGate (F:\HexyLab\CogniGate)

**Role per spec:** Bounded cognition without side effects. May reason/synthesize/reflect but CANNOT mint obligations.

#### Conflicts Found

| Issue | Severity | Description |
|-------|----------|-------------|
| Receipt Model Mismatch | HIGH | Uses internal `Receipt` model that differs from LegiVellum schema. |
| May Produce Plans | HIGH | Executor produces `ExecutionPlan`. Spec says only DeleGate can produce Plans. |
| No Receipt Emission to MemoryGate | MEDIUM | Receipts are internal, not emitted to MemoryGate ledger. |
| Missing Phase Model | MEDIUM | Uses `JobStatus` (pending/running/complete/failed) not LegiVellum phases (accepted/complete/escalate). |

#### Spec Constraint Violation
```
CogniGate may not:
- mint obligations
- create tasks
- create Plans  ← POTENTIAL VIOLATION
- enqueue async work
- escalate responsibility

CogniGate produces understanding, not action.
```

#### Actual Implementation
```python
class ExecutionPlan(BaseModel):
    """A structured execution plan produced by the planning phase."""
    task_id: str
    steps: list[PlanStep]
    estimated_tool_calls: int
    summary: str
```

The `ExecutionPlan` is an internal concept for execution flow, not a DeleGate-style Plan that creates obligations. However, the naming collision may cause confusion.

#### Recommendation
- Rename `ExecutionPlan` to `ExecutionSteps` or `CognitiveWorkflow` to avoid confusion with DeleGate Plans
- Ensure CogniGate never enqueues tasks to AsyncGate directly (currently it doesn't)

---

### 4. DepotGate (F:\HexyLab\DepotGate)

**Role per spec:** Artifact storage and lifecycle authority.

#### Compliance Status: COMPLIANT

DepotGate correctly implements:
- Artifact staging with `produced_by_receipt_id` tracking
- Deliverable contracts and shipping
- MCP tool interface for AI access
- Receipt session tracking via `receipts_session`
- Proper separation (artifacts vs receipts)

No conflicts found.

---

### 5. MetaGate (F:\HexyLab\MetaGate)

**Role per spec:** Bootstrap, topology, and lifecycle authority. Non-blocking, describe-only.

#### Compliance Status: COMPLIANT

MetaGate correctly implements:
- Bootstrap endpoint returning Welcome Packets
- Startup lifecycle (OPEN receipt witness)
- Non-blocking design (no work assignment)
- Forbidden keys enforcement
- Profile/manifest/binding resolution

The spec states:
```
MetaGate is a non-blocking, describe-only bootstrap authority...
It MUST NOT: Assign work, Provision infrastructure, Wait on other services,
Orchestrate execution, Block on health checks, Distribute task payloads
```

The implementation follows these constraints.

---

## Receipt Schema Comparison

### LegiVellum Receipt (from shared/legivellum/models.py)

```python
class Receipt(BaseModel):
    # Identity
    receipt_id: str          # ULID
    tenant_id: str
    task_id: str
    parent_task_id: str
    caused_by_receipt_id: str

    # Routing
    from_principal: str
    for_principal: str
    source_system: str
    recipient_ai: str        # Critical for inbox routing
    trust_domain: str

    # Phase
    phase: Phase             # accepted | complete | escalate
    status: Status           # NA | success | failure | canceled

    # Escalation
    escalation_class: EscalationClass
    escalation_reason: str
    escalation_to: str       # Must equal recipient_ai when phase=escalate
```

### CogniGate Receipt (from src/cognigate/models.py)

```python
class Receipt(BaseModel):
    lease_id: str
    task_id: str
    worker_id: str
    status: JobStatus        # pending | running | complete | failed
    timestamp: datetime
    artifact_pointers: list[dict]
    summary: str
    error_metadata: dict | None
```

**Key differences:**
- No `recipient_ai` field (cannot route to inbox)
- No `phase` field (no escalation support)
- No `caused_by_receipt_id` (no provenance chain)
- No `tenant_id` (no multi-tenancy)
- Uses `JobStatus` not `Phase`

---

## Recommendations

### Priority 1: Critical Alignment

1. **Create LegiVellum-compliant MemoryGate**
   - Either extend `memorygate` with receipt ledger functionality
   - Or create a new `LegiVellum/components/memorygate` service
   - The receipt store is the heart of LegiVellum coordination

2. **Update AsyncGate task model**
   - Add `principal_ai` field
   - Support `payload_pointer` pattern for DepotGate integration
   - Emit receipts to MemoryGate on completion

### Priority 2: Schema Alignment

3. **Standardize Receipt Schema**
   - All components should use `shared/legivellum/models.py` Receipt model
   - Or at minimum include `recipient_ai`, `phase`, `tenant_id`

4. **CogniGate Naming**
   - Rename `ExecutionPlan` to avoid confusion with DeleGate Plans

### Priority 3: Integration

5. **MemoryGate Integration**
   - AsyncGate should emit `complete` receipts to MemoryGate
   - CogniGate should emit `accepted`/`complete` receipts
   - MetaGate already emits bootstrap receipts (correctly)

---

## Appendix: LegiVellum Internal Components

The LegiVellum repo contains internal component implementations in `components/` that DO follow the spec:

- `components/asyncgate/` - Spec-compliant with `recipient_ai`, receipt emission
- `components/memorygate/` - Proper receipt ledger with inbox queries
- `components/delegate/` - Plan creation with `principal_ai`

These internal versions differ significantly from the standalone repos and should be considered the reference implementations.
