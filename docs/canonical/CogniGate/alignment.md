# CogniGate Alignment Notes (Canonical)

Role in LegiVellum:
- Bounded cognitive worker operating under lease
- Executes cognition without side effects or delegation
- Emits receipts to ReceiptGate

Required contract behavior:
- Bootstrap config from MetaGate
- Accept leases from AsyncGate
- Emit `accepted` and `complete` receipts to ReceiptGate
- Store outputs in DepotGate and reference by pointer
- Must NOT mint obligations or create plans that imply authority

Alignment status:
- **Docs aligned**: planning output is advisory only (not a DeleGate plan).
  Implementation should ensure receipts follow the canonical protocol and route to ReceiptGate.
