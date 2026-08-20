> Legacy note (2026-01-26): Canonical LegiVellum protocol is MCP-only. Any REST/HTTP endpoint references in this document are historical and non-normative.

# Legacy Specifications

Note: Documents in this folder are historical and may not reflect the current
canonical contracts. Use them for reference only. The authoritative contracts
live in `LegiVellum/docs/canonical/`.

ReceiptGate is the canonical receipt ledger. Any legacy references to
"MemoryGate as receipt store" should be read as ReceiptGate.

**Status:** Historical documents from early design phases

These documents contain design explorations and early semantics that predate the final LegiVellum architecture. They are preserved for historical context but are **not normative**.

## Normative Specifications

The canonical, authoritative specifications are:

**Receipt Protocol:**
- `receipt.schema.v1.json` - JSON Schema for receipts
- `receipt.rules.md` - Receipt protocol rules and semantics
- `receipt.indexes.sql` - Database indexes for receipts
- `receipt.store.md` - ReceiptGate store specification

**Components:**
- `asyncgate.lease.md` - AsyncGate lease protocol

**Executable, and binding where prose and data disagree:**
- `legivellum/schemas/transitions.v1.json` - obligation states, legal
  transitions, which are contested, and the typed errors they raise
- `legivellum/schemas/authority.v1.json` - the principal model

**Architecture:**
- `vellum.spec.md` - Vellum language specification
- `problemata.spec.md` - Problemata contract

## What Changed

These legacy documents may contain concepts that were **deprecated** in the final design:

### Deprecated Concepts

**Receipt pairing:** Early versions had explicit pairing fields (`paired_with_uuid`) and auto-pairing logic. The final design uses **derived state** via queries instead.

**Progress receipts:** Early versions had intermediate receipt types. The final design uses only **three phases**: `accepted`, `complete`, `escalate`.

**Mutable receipts:** Early versions allowed receipt updates. The final design uses an **append-only ledger**.

**Worker assignment:** Early versions had coordinator-driven worker assignment. The final design uses **worker polling** and self-discovery.

**String "NA" values:** Early versions used `"NA"` strings for unset values. The final design uses **null timestamps**.

**Event types:** Early versions had a taxonomy of event types. The final design uses **phase** as the primary discriminator.

### Moved here from ReceiptGate's repository root (2026-08-20)

Five files sat loose at the top of the ReceiptGate repo. They are design
material from the same era as the rest of this folder, and they were being read
as current because of where they lived:

- `Receipt Protocol Golden.txt` — declares itself **"Status: Canonical /
  Authoritative"**, which it is not. `docs/canonical/` is normative. This
  document's obligation model was mined into `transitions.v1.json`, which is
  what the code actually loads.
- `Escalation Semantics.txt` — states *"Only the receiving component mints the
  escalate receipt."* **The opposite is enforced.** Escalation is issued by the
  principal that currently holds the obligation, because only the custodian may
  hand one on; a receipt claiming otherwise is refused ACTOR_NOT_CUSTODIAN.
- `receipts.put Contract.txt`, `Schema fort receipt and escalation body.txt` —
  REST/OpenAPI shapes for an HTTP surface. The protocol is MCP-only.
- `Excellent. This is the right moment.txt` — a chat transcript.

The escalation one is the reason this move mattered rather than being tidiness.
A reader looking for how escalation works found a confident, wrong answer in a
file whose location implied authority.

### Why These Files Exist

They document the evolution of LegiVellum's design and provide context for architectural decisions. Reading them can help understand *why* certain choices were made, but they should not be implemented.

## Reading Order (If Curious)

1. `trilogy_recursive_cognition_architecture.txt` - Original trilogy concept
2. `receipt_protocol.md` - Early receipt semantics
3. `Receipt schema draft.txt` - First schema attempt
4. `memorygate_inbox_receipt_extension.txt` - Inbox evolution
5. `asyncgate_task_orchestration.txt` - AsyncGate early design
6. `delegate_worker_orchestration.txt` - DeleGate early design
7. `LegiVellum Decisions List.txt` - Decision changelog

**When in doubt:** Ignore these files. Use the normative specifications listed above.

---

*Last updated: 2026-08-20*  
*Technomancy Laboratories*
