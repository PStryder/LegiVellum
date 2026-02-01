# MemoryGate Alignment Notes (Canonical)

Role in LegiVellum:
- Semantic memory service (observations, patterns, concepts)

Required contract behavior:
- Bootstrap config from MetaGate
- Provide semantic memory services (no receipt ledger role)
- Remain passive (respond to queries only)

Alignment status:
- **Non-ledger**: Receipt ledger responsibilities belong to ReceiptGate.
  If any docs imply MemoryGate is the canonical receipt store, defer to
  `receipt.store.md` and the ReceiptGate contract.
