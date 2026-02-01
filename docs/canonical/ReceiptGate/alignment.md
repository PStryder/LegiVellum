# ReceiptGate Alignment Notes (Canonical)

Role in LegiVellum:
- Canonical receipt ledger (append-only)
- Source of truth for obligations and audit trails

Required contract behavior:
- Bootstrap config from MetaGate
- Validate receipts against `receipt.schema.v1.json` and `receipt.rules.md`
- Provide inbox + query endpoints
- Remain passive (no orchestration)

Alignment status:
- **Aligned** with canonical contracts.
