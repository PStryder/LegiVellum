# LegiVellum: The Permanent Record of Recursive Cognition

**A System Architecture for AI Agents That Remember, Wait, Delegate, and Prove Their Work**

---

**Version:** 1.1
**Date:** 2026-01-07
**Status:** Reconciled Architecture Specification
**Authors:** PStryder (Technomancy Laboratories), with Kee and Hexy

---

## Executive Summary

LegiVellum is a system architecture for **recursive cognition across agents, systems, and time**.

It addresses three persistent failures in agentic systems:

* **Amnesia** — sessions reset instead of accumulating meaning
* **Blocking** — long-running work halts cognition
* **Chaos** — delegation obscures ownership and provenance

The solution is not more intelligence. It is **structural separation**.

LegiVellum separates cognition, planning authority, memory, time, artifacts, and system lifecycle into **seven primitives**, connected by a single coordination protocol: **Receipts**.

Receipts are proof-of-responsibility. Plans are first-class work products. Memory is passive. Time is neutral.

This architecture allows intelligence to **accumulate** instead of resetting, and allows systems to **scale without losing accountability**.

---

## The Seven Primitives

LegiVellum consists of seven orthogonal primitives, grouped by concern:

### Cognition & Intent

1. **CogniGate** — bounded cognition without side effects
2. **DeleGate** — planning authority (intent → obligations)

### Memory & Proof

3. **MemoryGate** — durable semantic memory and receipt ledger
4. **Receipts** — universal proof-of-obligation protocol

### Time & Matter

5. **AsyncGate** — async boundary (time decoupling)
6. **DepotGate** — artifact storage and lifecycle authority

### System Oversight

7. **MetaGate** — bootstrap, topology, and lifecycle authority

A related primitive class, **InterView**, provides read-only introspection and is explicitly non-coordinating.

---

## Core Authority Rules

### Obligation Minting

Only **Principals (input sources)** and **DeleGates** may mint new obligations.

Obligations include:

* creating tasks
* creating Plans
* escalating responsibility across boundaries

All other components may advise, analyze, or recommend — but may not create obligations.

### Receipt Emission

Any component that **accepts responsibility** must emit an `accepted` receipt.

Receipts prove custody of responsibility. They are not work product.

### Plans

A **Plan** is both:

* a **first-class primitive** (recognized by the system)
* a **work-product artifact** (structured, inspectable, executable)

Only DeleGate may mint Plans that the system treats as authoritative.

---

## CogniGate: Bounded Cognition Without Side Effects

CogniGate provides a controlled surface for cognition:

* reasoning
* synthesis
* reflection
* modeling

CogniGate may:

* read from MemoryGate
* read receipts
* read artifacts via DepotGate
* accept obligations and emit receipts

CogniGate may **not**:

* mint new obligations
* create tasks
* create Plans
* enqueue async work
* escalate responsibility

CogniGate produces **thought**, not action.

---

## DeleGate: Planning Authority

DeleGate is the **only primitive authorized to convert intent into obligations**.

It accepts intent and produces a **Plan**: a structured declaration of what must happen next.

DeleGate may:

* mint new obligations
* create Plans
* enqueue work via AsyncGate
* escalate responsibility

DeleGate does **not** execute work or wait on time.

DeleGate may be implemented as:

* a standalone service
* a constrained CogniGate profile
* an embedded planning module

The invariant is authority, not topology.

---

## MemoryGate: Durable Semantic Memory and Ledger

MemoryGate is the **authoritative record** of what is known and what has happened.

It stores:

* observations
* patterns
* concepts
* document references
* receipts

MemoryGate is passive by design.

It does not:

* execute work
* coordinate time
* interpret plans
* advance state

MemoryGate validates, normalizes, and persists receipts, including those emitted indirectly during bootstrap.

State is derived through queries — not maintained imperatively.

---

## Receipts: Universal Proof of Responsibility

Receipts are append-only records proving that responsibility was:

* accepted
* completed
* escalated

Receipts are first-class primitives of accountability.

They are not work product.

### Receipt Phases

* **accepted** — obligation assumed
* **complete** — obligation resolved
* **escalate** — responsibility transferred

Inbox state is derived:

* Open = accepted without terminal receipt
* Resolved = complete exists
* Escalated = escalate exists

Receipts form complete provenance chains.

---

## AsyncGate: The Async Boundary (Time Decoupling)

AsyncGate exists to **externalize time**.

It allows a component to hand off an obligation and continue without blocking.

AsyncGate does **not** coordinate execution.

It does not:

* schedule
* prioritize
* orchestrate
* reason about outcomes

It does:

* hold obligations while time passes
* allow workers to lease work
* accept completion/failure signals
* emit receipts reflecting lifecycle events

AsyncGate makes time neutral.

---

## DepotGate: Artifact Storage and Lifecycle Authority

DepotGate manages the material outputs of work:

* files
* blobs
* reports
* datasets

It enforces:

* retention policies
* access control
* lifecycle rules

AsyncGate passes pointers. MemoryGate records references.

DepotGate owns artifacts.

---

## MetaGate: System Bootstrap and Topology Authority

MetaGate supervises the system itself.

It is responsible for:

* component registration
* startup sequencing
* topology awareness
* health supervision

MetaGate may emit receipts on behalf of components during bootstrap windows.

This prevents race conditions during cold start and recovery.

---

## InterView: Viewer Primitives

InterView provides read-only introspection across the system.

Viewer primitives:

* may observe state
* may query receipts
* may expose diagnostics

They may never:

* emit receipts
* mutate state
* mint obligations

Observability without control is a hard boundary.

---

## Design Principles

1. **Authority Is Explicit** — only Principals and DeleGates create obligations
2. **Receipts at Boundaries Only** — internal cognition is silent
3. **Plans Are Work Product** — receipts are proof
4. **Passivity Is Strength** — memory does not act
5. **Time Is Neutral** — async decouples waiting
6. **Pointers Over Payloads** — artifacts live elsewhere
7. **Topology Is Orthogonal** — protocol does not assume deployment

---

## Conclusion

LegiVellum does not attempt to build a single, all-knowing agent.

It builds the conditions under which intelligence can **accumulate safely**:

* memory that does not interfere
* cognition that does not leak action
* planning that is authoritative
* time that does not destroy continuity
* artifacts that are governed
* systems that can explain themselves

This is not agent cleverness.

It is **cognitive infrastructure**.

LegiVellum is the permanent record of recursive cognition.

---

*Technomancy Laboratories*
