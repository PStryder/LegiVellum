# MetaGate Alignment Notes (Canonical)

Role in LegiVellum:
- Bootstrap and topology authority
- Instantiates validated problemata

Required contract behavior:
- Receive validated problemata (e.g., via LegiVellum platform)
- Resolve config + secrets for components
- Emit startup receipts to ReceiptGate
- Never validate problemata specs (platform responsibility)

Alignment status:
- **Aligned**, assuming validation is performed by LegiVellum.
