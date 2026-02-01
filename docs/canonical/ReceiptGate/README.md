# ReceiptGate

ReceiptGate is the canonical receipt ledger for the LegiVellum stack. It is a
MemoryGate profile that stores immutable, append-only receipts and derives
obligation truth (inbox, chain, history) from those receipts.

## Canonical Alignment (LegiVellum)

- Required primitive for every problemata.
- MetaGate distributes ReceiptGate endpoints and auth to components.
- ReceiptGate is passive: it stores receipts and serves queries only.

## What it is
- Immutable receipt ledger
- Idempotent append-only API
- Derived inbox/chain endpoints

## What it is not
- Durable task store (AsyncGate owns task lifecycle)
- Artifact store (DepotGate owns artifact storage)
- Workflow runtime

## Setup
1. Install dependencies: `pip install -e .`
2. Configure env vars (see below)
3. Run the service: `receiptgate`

Schema files live in `schema/` and can be auto-applied on startup when
`RECEIPTGATE_AUTO_MIGRATE_ON_STARTUP=true` (default).

## Environment
- `RECEIPTGATE_DATABASE_URL` (default: `sqlite:///./receiptgate.db`)
- `RECEIPTGATE_API_KEY` (unless `RECEIPTGATE_ALLOW_INSECURE_DEV=true`)
- `RECEIPTGATE_ALLOW_INSECURE_DEV` (dev only)
- `RECEIPTGATE_RECEIPT_BODY_MAX_BYTES` (default 262144)
- `RECEIPTGATE_ENABLE_GRAPH_LAYER` / `RECEIPTGATE_ENABLE_SEMANTIC_LAYER`
