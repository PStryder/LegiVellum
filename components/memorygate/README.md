# MemoryGate

**The Permanent Record**

MemoryGate is the durable semantic memory layer and source of truth for the LegiVellum system.

## Purpose

- Store receipts as an immutable audit ledger
- Provide universal bootstrap for session initialization
- Manage semantic memory (observations, patterns, concepts, documents)
- Serve as inbox for all components

## Responsibilities

- **Receipt Storage:** Single-writer for all receipts (accepted, complete, escalate)
- **Bootstrap API:** Return inbox + recent context for session start
- **Query API:** Support inbox queries, task lifecycle queries, provenance chains
- **Semantic Search:** Vector search across observations and documents
- **Passivity:** Never volunteers state updates, only responds to explicit queries

## What MemoryGate Does NOT Do

- Execute tasks
- Track work-in-flight (AsyncGate's job)
- Manage retries or progress
- Decide what should happen next (DeleGate's job)
- Block or schedule

## Architecture Notes

MemoryGate is **intentionally centralized** for epistemic clarity. This is not a weakness—it's a deliberate choice that makes the system understandable and trustworthy.

## Key Principle

> MemoryGate remembers so agents can act—not the other way around.

---

See `/spec/memorygate_receipt_store.md` for detailed specification.
