# Proctor Pattern (Intake + Supervision) — Canonical Guidance

Status: **canonical guidance** (pattern; normative where noted)

## Purpose

The **Proctor** pattern is a compositional way to add **intake supervision** and **end-to-end accountability** to asynchronous work **without** introducing a hidden controller.

A Proctor:
- accepts a request/intent (from a human or agent),
- creates an explicit obligation boundary (a **master obligation**),
- delegates execution to a circuit (often a Problemata circuit),
- supervises by observing receipts and artifacts,
- closes the loop by emitting a terminal receipt when completion criteria are met.

This pattern exists to make it obvious—on the ledger—**who is responsible for closure**, even as workers and topologies change.

## Non-goals

A Proctor is **not**:
- a required component of LegiVellum,
- a centralized scheduler that must be online,
- a privileged “god service” that can mutate state off-ledger,
- a place to hide logic that should be in explicit topology/specs.

## Definitions

### Master obligation
The intake-level obligation representing “this request must be driven to closure.”

- It is tracked by receipts like any other obligation.
- It has a stable identifier (receipt `task_id`/`obligation_id` conventions per `receipt.rules.md`).

### Child obligations
Obligations created as part of executing the request (planning, staging, retrieval, validation, writing, etc.).

### Completion by artifact (DepotGate)
When a workflow’s definition of “done” is best represented by a **materialized artifact** (e.g., a file, bundle, dataset, report, patch), completion is determined by the artifact’s presence + properties in DepotGate, not by a worker saying “trust me.”

## Roles in the pattern

- **Proctor** (supervisor): owns the master obligation.
- **DeleGate / Planner**: expands intent into a plan and/or child obligations.
- **AsyncGate / Leaser**: coordinates execution, leasing, retries, and boundary receipts.
- **Workers / Circuits**: perform steps and emit receipts at obligation boundaries.
- **ReceiptGate / MemoryGate**: store/query receipts as the system of record.
- **DepotGate**: stores artifacts; can be used as the ground-truth completion witness.

## Core invariants (normative)

These constraints are designed to prevent the Proctor pattern from becoming an invisible control plane.

1) **Ledger visibility (MUST)**
- The Proctor MUST create (or cause creation of) an **accepted** receipt that represents the master obligation.
- The Proctor MUST close the master obligation with a terminal receipt (**complete** or **escalate**) when it determines closure.

2) **No hidden control (MUST NOT)**
- The Proctor MUST NOT resolve obligations by off-ledger side effects alone.
- If the Proctor makes a decision that changes responsibility, it MUST be reflected as a receipt boundary event.

3) **Child work remains explicit (SHOULD)**
- Child obligations SHOULD be created as normal receipts and SHOULD be attributable to the primitive that created them (planner, circuit stage, worker).

4) **Completion must be checkable (SHOULD)**
- If “done” can be represented as an artifact, completion SHOULD be determined by verifying DepotGate artifacts (existence + invariants), not by a free-form claim.

5) **Optionality (MAY)**
- A topology MAY omit a Proctor entirely.
- If omitted, the master obligation concept can still exist (e.g., a caller-owned obligation), but the same receipt rules apply.

## Receipt flow (reference)

### 1) Intake
- Proctor receives intent.
- Proctor emits an **accepted** receipt for the master obligation.

### 2) Expansion
- Proctor asks DeleGate (or equivalent) for a plan.
- DeleGate emits receipts for child obligations (or a plan artifact) as appropriate.

### 3) Execution
- AsyncGate leases child obligations to workers.
- Workers emit receipts when they accept/complete/escalate their obligations.

### 4) Supervision
- Proctor watches the ledger (MemoryGate queries) and optionally the artifact store (DepotGate).

### 5) Closure
- When completion criteria are met:
  - Proctor emits a **complete** receipt for the master obligation.
- If completion cannot be reached within policy:
  - Proctor emits an **escalate** receipt for the master obligation, transferring responsibility to a human or another supervisor.

## Determining “done” (recommended strategies)

### A) Artifact-grounded completion (preferred where applicable)
Use DepotGate as the witness:
- required artifacts exist,
- artifacts satisfy invariants (size, checksum, schema, validation receipt, etc.),
- cross-links from receipts to artifact ids are present.

### B) Receipt-derived completion
Where no artifact exists, completion can be derived by receipt closure of a defined set:
- “all required child obligations complete” per a declared plan/spec.

This approach SHOULD be paired with explicit topology/specification so the set of required obligations is auditable.

## Anti-patterns

1) **Hidden controller Proctor**
A Proctor that makes decisions but does not emit receipts. This breaks legibility.

2) **Proctor-as-worker**
A Proctor that performs long-running execution directly. Prefer delegating to workers and supervising.

3) **Uncheckable completion**
Closing the master obligation based on a free-form claim when an artifact witness was feasible.

## Relationship to Problemata

Problemata defines explicit topology and validation semantics.

The Proctor pattern composes naturally with Problemata:
- The circuit spec makes child obligations and stage boundaries explicit.
- The Proctor owns the master obligation and supervises the circuit’s progress via receipts.

A Proctor SHOULD prefer driving **spec-first circuits** (Problemata) when the workflow has meaningful governance or review requirements.

## Implementation notes

- Proctor does not require privileged access. It can be implemented as:
  - a lightweight service,
  - an agent process,
  - or even a human-in-the-loop operator that emits receipts.

- The important property is not where it runs, but that:
  - obligations are created/closed via receipts,
  - completion is checkable.

## References

- `docs/canonical/receipt.rules.md` — normative receipt semantics
- `docs/canonical/problemata.spec.md` — explicit topology and stage semantics
- `docs/canonical/worker.contract.md` — worker minimum compatibility
