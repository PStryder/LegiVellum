# Minimal Worker (Reference)

This is a tiny, stdlib-only worker that demonstrates:

1) MetaGate bootstrap
2) `accepted` receipt
3) Artifact staging in DepotGate
4) `complete` receipt with artifact pointer

It is intentionally small and not production-hardened.

## Run

```
python minimal_worker.py
```

## Environment

Required (or discoverable via MetaGate packet):

```
METAGATE_ENDPOINT=http://localhost:8010/mcp
METAGATE_API_KEY=mg_your-token

RECEIPTGATE_ENDPOINT=http://localhost:8090/mcp
RECEIPTGATE_API_KEY=rg_your-token

DEPOTGATE_ENDPOINT=http://localhost:8020/mcp
DEPOTGATE_API_KEY=dg_your-token
```

Optional:

```
WORKER_COMPONENT_KEY=worker_minimal
WORKER_ID=worker.minimal
TASK_ID=task-demo-001
TENANT_ID=default
PRINCIPAL_AI=principal.demo
```

## Notes

- Replace UUID receipt_ids with ULIDs in production.
- Idempotency and retries are required for real workers; this example is a single-shot demo.
