# Worker Quickstart (LegiVellum)

This guide gets you from zero to a compliant worker that can accept work,
emit receipts, and publish artifacts. Start here, then read the full contract:
`docs/canonical/worker.contract.md`.

## 1) Minimum contract

Your worker MUST:
- Bootstrap from MetaGate before processing work.
- Accept a task envelope that includes routing + provenance.
- Emit `accepted` and `complete` receipts to ReceiptGate.
- Escalate when it cannot complete (phase=`escalate`).
- Externalize artifacts to DepotGate and reference them by pointer.
- Enforce idempotency on `task_id` or `dedupe_key`.

## 2) Minimal environment

Set these for local dev:

```
METAGATE_ENDPOINT=http://localhost:8010/mcp
METAGATE_API_KEY=mg_your-token

RECEIPTGATE_ENDPOINT=http://localhost:8090/mcp
RECEIPTGATE_API_KEY=rg_your-token

DEPOTGATE_ENDPOINT=http://localhost:8020/mcp
DEPOTGATE_API_KEY=dg_your-token
```

Your worker should prefer endpoints returned by MetaGate, but allow env
overrides for local testing.

## 3) Minimal flow (bootstrap -> accept -> execute -> complete)

1. Call `metagate.bootstrap` to fetch the Welcome Packet.
2. Validate the task envelope (required fields + routing).
3. Emit an `accepted` receipt to ReceiptGate.
4. Execute work (bounded and tool-controlled).
5. Write output to DepotGate (`stage_artifact`).
6. Emit a `complete` receipt referencing the artifact pointer.

## 4) Reference implementation

See the minimal worker example:
- `examples/minimal_worker/minimal_worker.py`
- `examples/minimal_worker/README.md`

## 5) Next steps

- Read the contract: `docs/canonical/worker.contract.md`
- Validate receipts against `docs/canonical/receipt.schema.v1.json`
- Follow the escalation rules in `docs/canonical/receipt.rules.md`
