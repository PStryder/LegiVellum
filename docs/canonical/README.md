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
- `mcp.naming.md` — canonical MCP tool naming and compatibility rules

### Supervision / intake patterns
- `proctor.pattern.md` — Proctor pattern (intake + supervision + master obligation)

### Vellum language
- `vellum.spec.md` — Vellum language specification (draft)

## Per-service directories

Alongside the flat files above, this folder contains a directory per service
(`AsyncGate/`, `CogniGate/`, `DeleGate/`, `DepotGate/`, `InterView/`,
`InterroGate/`, `MemoryGate/`, `MetaGate/`, `ReceiptGate/`, `CorpoVellum/`).

Each holds that service's **alignment note** — what the service must do to be a
compliant LegiVellum primitive — plus a copy of its README and, in some cases,
copies of its own `docs/`.

Two things to know before relying on them:

**Relative paths inside copied documents point at the origin repository.** A
copy under `AsyncGate/docs/` that references `src/asyncgate/config.py` means
that path in the *AsyncGate* repo, not here. Those files exist; they simply do
not resolve from this tree. Read the copies for contract intent and follow code
references in the origin repo.

**The copies have diverged from their originals, in both directions.** As of
2026-08-15 every service README differs from the one in its own repository:
the copy here typically carries a "Canonical Alignment (LegiVellum)" section the
origin lacks, while the origin carries operational detail (run scripts, health
curls, full environment tables) the copy lacks. They are no longer the same
document.

So: for **contract and alignment**, this tree is authoritative — that is what
"canonical" means here. For **how to run, configure, or call a service**, the
service's own repository is authoritative and more current. Where a service
README here restates operational detail, treat it as secondary.

Keeping both in sync is currently manual and unenforced. A change to a service's
tool surface or configuration needs applying in both places, and nothing checks
that it was.

## Design intent (why these exist)

## Service Role Mapping

- `ReceiptGate` is the canonical receipt ledger contract (`receiptgate.*` tools).
- `MemoryGate` is the canonical durable memory/search contract (`memory_*` tools).
- If receipts are implemented as a MemoryGate profile, the runtime must still
  preserve the ReceiptGate MCP surface and semantics.

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
