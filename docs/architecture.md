# Architecture (Steel Beam Summary)

LegiVellum is a receipt-driven coordination architecture for asynchronous work.

## Primitives

### MemoryGate
- Passive ledger + query engine for receipts (and later: semantic memory).
- **Pull-only**: provides bootstrap/inbox queries; does not push work.
- Stores immutable receipts as the system of record.

### AsyncGate
- Execution & leasing coordinator for asynchronous workers.
- Emits receipts when it **accepts**, **escalates**, or **completes** obligations.
- Keeps liveness mechanisms (leases/heartbeats) *off-ledger* unless a boundary event occurs.

### DeleGate
- Planning/dispatch layer: accepts intent and emits **plans** and/or **new tasks**.
- Does not execute long-running work directly; it creates obligations via receipts.

## Coordination Contract
Receipts are the **only** coordination protocol:
- `accepted` creates obligation
- `complete` resolves obligation
- `escalate` transfers responsibility (soft push)

See `spec/receipt.rules.md` for the normative contract.
