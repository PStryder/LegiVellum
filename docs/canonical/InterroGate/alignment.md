# InterroGate Alignment Notes (Canonical)

Role in LegiVellum:
- Admission control for recursion and invariants
- ALLOW or DENY only (no orchestration)

Required contract behavior:
- Bootstrap config from MetaGate
- Query lineage/history from MemoryGate (and receipt chains from ReceiptGate if needed)
- Emit acceptance/rejection receipts to ReceiptGate

Alignment status:
- **Aligned** with canonical contracts.
