# DeleGate Alignment Notes (Canonical)

Role in LegiVellum:
- Pure planning authority
- Only component (besides Principals) that may mint obligations

Required contract behavior:
- Bootstrap config from MetaGate
- Emit planning receipts (`plan_created`, `plan_escalated`) to ReceiptGate
- Store plans in DepotGate and reference by pointer
- Never execute tasks directly

Alignment status:
- **Aligned** with canonical contracts (verify receipt routing to ReceiptGate).
