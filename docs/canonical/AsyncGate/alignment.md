# AsyncGate Alignment Notes (Canonical)

Role in LegiVellum:
- Asynchronous execution boundary (task queue + leasing)
- Receives tasks from Principals/DeleGates
- Leases work to workers
- Emits receipts to ReceiptGate

Required contract behavior:
- Bootstrap config from MetaGate
- Accept tasks with `principal_ai` and `payload_pointer`
- Emit `accepted`/`complete`/`escalate` receipts to ReceiptGate
- Externalize outputs to DepotGate and reference by pointer
- Never plan or mint obligations

Alignment status:
- **Docs aligned**: canonical contracts require ReceiptGate as the receipt ledger.
  Inline payloads remain supported for backward compatibility but pointers are preferred.
