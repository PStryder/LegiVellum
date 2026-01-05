# Legacy Specifications

**Status:** Historical documents from early design phases

These documents contain design explorations and early semantics that predate the final LegiVellum architecture. They are preserved for historical context but are **not normative**.

## Normative Specifications

The canonical, authoritative specifications are:

**Receipt Protocol:**
- `/spec/receipt.schema.v1.json` - JSON Schema for receipts
- `/spec/receipt.rules.md` - Receipt protocol rules and semantics
- `/spec/receipt.indexes.sql` - Database indexes for receipts

**Components:**
- `/spec/memorygate_receipt_store.md` - MemoryGate specification
- `/spec/asyncgate.lease.md` - AsyncGate lease protocol

**Architecture:**
- `/LegiVellum_Whitepaper.md` - Complete system architecture

## What Changed

These legacy documents may contain concepts that were **deprecated** in the final design:

### Deprecated Concepts

**Receipt pairing:** Early versions had explicit pairing fields (`paired_with_uuid`) and auto-pairing logic. The final design uses **derived state** via queries instead.

**Progress receipts:** Early versions had intermediate receipt types. The final design uses only **three phases**: `accepted`, `complete`, `escalate`.

**Mutable receipts:** Early versions allowed receipt updates. The final design uses an **append-only ledger**.

**Worker assignment:** Early versions had coordinator-driven worker assignment. The final design uses **worker polling** and self-discovery.

**String "NA" values:** Early versions used `"NA"` strings for unset values. The final design uses **null timestamps**.

**Event types:** Early versions had a taxonomy of event types. The final design uses **phase** as the primary discriminator.

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

*Last updated: 2026-01-04*  
*Technomancy Laboratories*
