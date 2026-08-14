# InterroGate Alignment Notes (Canonical)

Role in LegiVellum:
- Admission control for recursion and invariants
- ALLOW or DENY only (no orchestration)

Required contract behavior:
- Bootstrap config from MetaGate
- Query lineage/history from MemoryGate (and receipt chains from ReceiptGate if needed)
- Receipt every admission evaluation. The evaluation itself is the obligation:
  InterroGate accepts responsibility for deciding whether a request is
  admissible under a policy, and completes that obligation with an ALLOW or
  DENY decision in the receipt body.

  A DENY is a *successful completion* whose answer was no, not a failure and
  not an escalation. An ALLOW completes the admission check only -- it does not
  make InterroGate responsible for the admitted work, which is minted by
  whoever holds authority, linking back via `caused_by_receipt_id`.

  Admission needs no receipt phase of its own. "Emit acceptance/rejection
  receipts" was the earlier wording here, and "rejection receipt" reads as a
  lifecycle concept; the phases describe responsibility transitions, not
  everything interesting that can happen.

Alignment status:
- **Aligned** with canonical contracts.
