# InterView Alignment Notes (Canonical)

Role in LegiVellum:
- Read-only system viewer surfaces
- Must not create work or mutate state

Required contract behavior:
- Bootstrap config from MetaGate
- Query allowed sources only (cache > mirror > component polls > global ledger)
- Read receipts from ReceiptGate and artifacts from DepotGate
- Enforce rate limits and cost bounds

Alignment status:
- **Aligned** with canonical contracts.
