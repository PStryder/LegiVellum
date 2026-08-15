# LegiVellum

Receipt-driven architecture for coordinating AI work. LegiVellum uses immutable receipts as the sole protocol for task acceptance, escalation, and completion—supporting async execution, deep delegation chains, and full auditability without centralized orchestration.

## Overview

LegiVellum is **cognitive infrastructure**, not an agent framework. It provides:

- Persistence without immortality
- Action without blocking
- Delegation without chaos
- Explanation after failure

The system is built as a **ledger-bound substrate** where workers may die, processes may restart, and topologies may change—but the record of responsibility remains.

## The Seven Primitives

LegiVellum separates cognition, authority, memory, time, matter, and oversight into seven primitives:

| Primitive | Role | Description |
|-----------|------|-------------|
| **CogniGate** | Bounded cognition | Reasoning without side effects |
| **DeleGate** | Planning authority | Intent to obligations (produces Plans) |
| **MemoryGate** | Durable memory | Semantic memory, search, and long-horizon knowledge services |
| **AsyncGate** | Time boundary | Async execution and lease management |
| **DepotGate** | Matter vault | Artifact storage and lifecycle |
| **MetaGate** | System warden | Bootstrap, topology, and lifecycle |
| **InterView** | Observation | Read-only introspection |

Two further services complete the runnable stack. They are not counted among
the seven because neither is a primitive: one is the ledger the primitives
write to, the other guards the boundary in front of them.

| Service | Role | Description |
|---------|------|-------------|
| **ReceiptGate** | Obligation ledger | The canonical receipt store and the only global narrative |
| **InterroGate** | Admission control | Decides whether a request is admissible under policy, and receipts that decision |

Receipt ledger role: `ReceiptGate` is the canonical obligation ledger surface.
In deployments that embed ledger capabilities into MemoryGate, this is treated
as a ReceiptGate profile and must preserve the `receiptgate.*` MCP contract.

InterroGate's admission evaluation is itself an obligation with an ordinary
`accepted → complete` lifecycle. A DENY completes successfully with
`decision: "DENY"` in the body — the evaluation did what it accepted, and the
answer was no — so it is not a failure and needs no new receipt phase. An ALLOW
does not make InterroGate responsible for the admitted work; whoever holds
authority mints that obligation, linking back with `caused_by_receipt_id`.

## Receipt Protocol

Receipts are the universal proof-of-obligation protocol with three lifecycle phases:

| Phase | Description |
|-------|-------------|
| `accepted` | Creates an obligation |
| `complete` | Resolves an obligation (success/failure/canceled) |
| `escalate` | Transfers responsibility |

### Receipt Fields

Core fields for all receipts:
- `receipt_id` - Client-generated ULID
- `task_id` - Correlation key for task lifecycle
- `parent_task_id` - Parent task for delegation trees
- `caused_by_receipt_id` - Provenance chain link
- `phase` - Lifecycle phase (accepted/complete/escalate)
- `status` - Completion status (NA/success/failure/canceled)
- `from_principal` - Principal requesting the work
- `for_principal` - Principal the work is done for
- `source_system` - System emitting the receipt
- `recipient_ai` - Agent owning this receipt
- `body` - Structured payload; carries `result` on completion

41 of the schema's 42 fields are required; only `artifact_refs` is optional.
A required field that does not apply carries the `NA` sentinel (or `null` for
timestamps) rather than being omitted, and `additionalProperties` is `false`,
so a receipt cannot carry fields the schema does not define.
`docs/canonical/receipt.schema.v1.json` is authoritative, and the examples
under `examples/` are validated against it in CI.

### Outcome Types

- `NA` - Not applicable to this phase
- `none` - No output
- `response_text` - Text response
- `artifact_pointer` - Reference to stored artifact
- `mixed` - Both text and artifact

### Escalation Classes

- `NA` - Not an escalation
- `owner` - Escalate to owner
- `capability` - Capability not available
- `trust` - Trust boundary issue
- `policy` - Policy violation
- `scope` - Out of scope
- `other` - Other reason

## Worker Docs (Start Here)

- `WORKER_QUICKSTART.md`
- `docs/canonical/worker.contract.md`
- `examples/minimal_worker/README.md`

## Project Structure

```
LegiVellum/
├── shared/legivellum/     # Shared library code, loaded by the gates
│   ├── models.py              # Receipt Pydantic models
│   ├── validation.py          # Receipt validation
│   ├── database.py            # Database utilities
│   ├── auth.py                # Authentication
│   ├── metagate_bootstrap.py  # MetaGate bootstrap client (used by every gate)
│   ├── problemata_control.py  # Problemata control plane
│   ├── problemata_control_ui.py  # Control-plane UI
│   ├── problemata_publish.py  # Publishing a Problemata to MetaGate
│   ├── problemata_validation.py  # Problemata schema validation
│   └── observability/         # Shared logging and tracing helpers
├── tools/                 # Validators and the Problemata control UI
├── schema/                # SQL schemas and migrations
├── examples/              # Canonical receipts and a reference worker
├── problemata_demo/       # Runnable multi-service demo stack (8 services)
├── tests/                 # Test suite
└── docs/canonical/        # Normative specifications (source of truth)
```

This repository ships no primitive. Every implementation lives in its own
repository checked out beside this one (`../AsyncGate`, `../ReceiptGate`, …),
and the demo stack builds from those. `shared/legivellum/` is mounted into the
containers rather than vendored, so there is one copy of the bootstrap client
instead of nine.

## Core Invariants

1. **Authority**: Only Principals and DeleGates may mint obligations
2. **Acceptance**: Any component that accepts responsibility must emit an `accepted` receipt
3. **Immutability**: Receipts are append-only
4. **Provenance**: Receipts form complete causality chains
5. **Derived State**: Inbox state is derived by query, not mutation

## Installation

```bash
pip install -e ".[dev]"
```

## Testing

```bash
pytest tests/
```

## Related Projects

LegiVellum components have standalone implementations:
- [AsyncGate](../AsyncGate) - Async task execution
- [CogniGate](../CogniGate) - Cognitive execution worker
- [DepotGate](../DepotGate) - Artifact storage
- [MetaGate](../MetaGate) - System management
- [MemoryGate](../MemoryGate) - Durable memory and semantic retrieval
- [ReceiptGate](../ReceiptGate) - Canonical receipt ledger

## License

MIT
