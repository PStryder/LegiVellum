# Canonical (Normative) Specifications

This folder contains the **normative contracts** for LegiVellum.

If you are building a compatible primitive, worker, validator, or an integration layer, **treat these documents as the source of truth**.

Normative keywords (MUST/SHOULD/MAY/etc.) follow RFC 2119 semantics.

## What’s here

### Problemata
- `problemata.spec.md` — the Problemata Contract Specification (v0)
- `problemata.validation.md` — atomic validation contract (v0)
- `problemata.validation.schema.v1.json` — validation schema (machine-checkable)
- `vellum.problemata.bridge.md` — bridge notes between Vellum and Problemata (reference)

### Receipts
- `receipt.rules.md` — receipt semantics (accepted/complete/escalate) and derived state
- `receipt.schema.v1.json` — JSON Schema for receipts (v1)
- `receipt.store.md` — persistence + query expectations
- `receipt.indexes.sql` — recommended DB indexes

### Worker compatibility
- `worker.contract.md` — minimum contract for a generic MCP worker

### Vellum language
- `vellum.spec.md` — Vellum language specification (draft)

## Design intent (why these exist)

LegiVellum is designed so that:
- bodies/processes can die,
- topologies can change,
- orchestration can be distributed,

…but **responsibility remains legible**.

That legibility is enforced by:
- explicit topology (Problemata)
- mandatory receipts at obligation boundaries
- append-only history (no retroactive truth)

If an implementation violates these invariants, it may still run — but it is no longer LegiVellum.
