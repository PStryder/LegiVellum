# LegiVellum Docs

LegiVellum is **receipt-driven coordination infrastructure**: immutable receipts are the sole protocol for task acceptance, completion, and escalation.

This folder contains both:
- **Concept + architecture docs** (human-readable)
- **Canonical contracts** (normative specs you can implement against)

## Start here (10 minutes)

1) **Architecture overview**
- `architecture.md` — the “steel beam summary”

2) **The rules that keep it from turning into agent soup**
- `RFC-0001.txt` — composition rules + system invariants (normative tone)
- `composition-invariants.md` — practical composition rules (single-page)

3) **How to actually interop with the system (canonical contracts)**
- `canonical/README.md` — the normative index

## Implementer path (platform / components)

If you are implementing primitives, workers, or validators, start in `docs/canonical/`:

- **Problemata**
  - `canonical/problemata.spec.md` — what a problemata *is* (spec)
  - `canonical/problemata.validation.md` — atomic validation contract
  - `canonical/problemata.validation.schema.v1.json` — machine-checkable validation schema

- **Receipts**
  - `canonical/receipt.rules.md` — normative semantics (accepted/complete/escalate)
  - `canonical/receipt.schema.v1.json` — JSON Schema (v1)
  - `canonical/receipt.store.md` — storage + query expectations
  - `canonical/receipt.indexes.sql` — DB indexes

- **Workers**
  - `canonical/worker.contract.md` — minimum worker contract (MCP)

## Language path (Vellum)

If you care about the specification language layer:
- `canonical/vellum.spec.md` — Vellum language spec
- `vellum-integration.md` — integration guide (Vellum ↔ LegiVellum primitives)

## Notes

- **Normative vs reference**: anything under `docs/canonical/` is intended to be implementable and testable. Other files are explanatory, exploratory, or RFC-style.
- **Receipts are append-only**: fixes happen by supersession, never edits.
