# Architecture (Steel Beam Summary)

LegiVellum is a receipt-driven coordination architecture for asynchronous work.

## Primitives

### ReceiptGate
- Passive ledger + query engine for receipts.
- **Pull-only**: provides inbox/timeline queries; does not push work.
- Stores immutable receipts as the coordination system of record.

### MemoryGate
- Durable memory substrate for observations, concepts, patterns, and retrieval.
- Supports semantic search and long-horizon recall for agents/components.
- May host a ReceiptGate profile in some deployments, but the canonical ledger
  contract remains `receiptgate.*` MCP tools.

### AsyncGate
- Execution & leasing coordinator for asynchronous workers.
- Emits receipts when it **accepts**, **escalates**, or **completes** obligations.
- Keeps liveness mechanisms (leases/heartbeats) *off-ledger* unless a boundary event occurs.

### DeleGate
- Planning/dispatch layer: accepts intent and emits **plans** and/or **new tasks**.
- Does not execute long-running work directly; it creates obligations via receipts.

### Proctor (pattern)
- Optional intake + supervision role that owns a **master obligation** and drives work to closure by observing receipts/artifacts.
- Not required; when present it must remain legible on-ledger (no hidden controller).
- See `docs/canonical/proctor.pattern.md`.

## Coordination Contract
Receipts are the **only** coordination protocol:
- `accepted` creates obligation
- `complete` resolves obligation
- `escalate` transfers responsibility (soft push)

See `docs/canonical/receipt.rules.md` for the normative contract.
