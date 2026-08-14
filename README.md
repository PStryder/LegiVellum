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

Receipt ledger role: `ReceiptGate` is the canonical obligation ledger surface.
In deployments that embed ledger capabilities into MemoryGate, this is treated
as a ReceiptGate profile and must preserve the `receiptgate.*` MCP contract.

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

### Outcome Types

- `none` - No output
- `response_text` - Text response
- `artifact_pointer` - Reference to stored artifact
- `mixed` - Both text and artifact

### Escalation Classes

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
├── shared/legivellum/     # Shared library code
│   ├── models.py          # Receipt Pydantic models
│   ├── validation.py      # Receipt validation
│   ├── database.py        # Database utilities
│   └── auth.py            # Authentication
│   └── problemata_control.py  # Problemata control plane
├── tools/                 # Validators and the Problemata control UI
├── schema/                # SQL schemas and migrations
├── examples/              # Canonical receipts and a reference worker
├── problemata_demo/       # Runnable multi-service demo stack
├── tests/                 # Test suite
└── docs/canonical/        # Normative specifications (source of truth)
```

Primitive implementations live in their own repositories alongside this one
(`../AsyncGate`, `../ReceiptGate`, …). The demo stack builds from those.

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
