# Canonical Specs Index

This folder contains the authoritative (canonical) specifications for
LegiVellum problemata. Anything outside this folder is non-canonical or legacy.

## Terminology

**Problemata** (singular: problemata) - A LegiVellum assembly; a versioned, declarative specification that defines which primitives to use, how they connect, and how they're configured. The term derives from Aristotle's *Problems* (structured philosophical investigations) and implies purposeful constraint-satisfaction through coordinated components. Not "deployment," "configuration," or "stack."

## System Invariants (Canonical)
- Validation authority: LegiVellum (platform). MetaGate instantiates only validated problemata.
- Required primitives: MetaGate, ReceiptGate, DepotGate.
- Receipt ledger: ReceiptGate (may be implemented as a MemoryGate profile).
- Artifacts: stored in DepotGate; receipts carry pointers.
- Config naming: ReceiptGate integration uses `receiptgate_*` keys.
- **Universal protocol**: All primitive-to-primitive communication uses MCP. If a `protocol` field is present, it MUST be `mcp`.

## Architecture Principles
- **Problemata are declarative specifications** (YAML/JSON), not runtime code
- **Auditing, authority, and accountability** are architectural requirements, not add-ons
- **Agents can compose problemata** - deploy pre-defined patterns OR design custom solutions on-demand
- **Successful agent compositions** become reusable pattern specifications
- **LegiVellum validates and auto-instantiates** - specs must pass validation before deployment

## Interface Layers
LegiVellum provides three interface layers:

1. **Admin/Config Dashboard** - System administration, tenant management, primitive configuration
2. **Problemata Design/Deploy Dashboard** - Visual/form-based problemata specification and deployment
3. **MCP Interface** - Agent-facing API for programmatic problemata creation, deployment, and invocation

### Agent Routing Pattern
External agents access deployed problemata through **InterroGate** configured as MCP gateway:
- Each deployed problemata exposes an InterroGate instance (MCP gateway surface)
- InterroGate registers with the LegiVellum service (announces endpoint and capabilities)
- Agents connect once to LegiVellum MCP and call `problemata.passthrough(problemata_id, input)`
- LegiVellum routes requests to the appropriate InterroGate
- InterroGate enforces policy (auth, rate limits, tenant isolation), then routes to internal primitives
- Responses can be **synchronous** (immediate result) or **asynchronous** (receipt + artifact location)
- The problemata (via InterroGate policy) decides execution mode based on workload complexity

See: `InterroGate/SPEC-IG-0000 (v0).txt` Section 9.1 for complete MCP Gateway specification
See: `problemata.spec.md` Section 5.1 for agent interface pattern details

## Core Contracts
- `problemata.spec.md` — Problemata composition + topology + config contract
- `problemata.validation.md` — Validation layers/invariants (pre-instantiation)
- `problemata.validation.schema.v1.json` — Validation report schema
- `worker.contract.md` — MCP worker interoperability contract

## Receipt Protocol
- `receipt.rules.md` — Normative receipt semantics
- `receipt.schema.v1.json` — Receipt JSON schema
- `receipt.store.md` — ReceiptGate storage + API contract
- `receipt.indexes.sql` — Receipt index definitions

## Other Canonical Specs
- `vellum.spec.md` — Vellum language specification
- `vellum.problemata.bridge.md` — Vellum-to-Problemata compilation contract
- `asyncgate.lease.md` — AsyncGate lease protocol
- `mcp.metrics.exporter.md` — MCP-to-Prometheus exporter contract

## Component Docs (Consolidated)
Each component has a dedicated folder with copied docs and an `alignment.md`
file that states how the component fits the canonical contracts.

Components:
- `AsyncGate/`
- `CogniGate/`
- `DeleGate/`
- `DepotGate/`
- `InterroGate/`
- `InterView/`
- `MetaGate/`
- `MemoryGate/`
- `ReceiptGate/`
- `CorpoVellum/`

## Document Purpose Guide

**Start here if you're:**
- **Implementing a primitive** → Read your component's folder (`AsyncGate/`, `CogniGate/`, etc.), especially `alignment.md` and the spec file
- **Building a custom worker** → Start with `worker.contract.md`, then `problemata.spec.md` for integration
- **Validating a problemata spec** → Read `problemata.validation.md` and reference `problemata.validation.schema.v1.json`
- **Designing a problemata** → Begin with `problemata.spec.md`, then review component READMEs for capabilities
- **Understanding receipts** → Start with `receipt.rules.md`, then `receipt.schema.v1.json` and `receipt.store.md`
- **Writing Vellum specs** → Read `vellum.spec.md`
- **Compiling Vellum to problemata** → Read `vellum.problemata.bridge.md`, then `problemata.spec.md`
- **Working with task orchestration** → Review `asyncgate.lease.md` for lease mechanics and task lifecycle

**Cross-cutting concerns:**
- All primitives must align with core contracts (`problemata.spec.md`, `worker.contract.md`)
- Receipt protocol applies to all primitives that emit work tracking events
- Validation rules in `problemata.validation.md` are enforced before any deployment

## Legacy Specs
See `canonical/legacy/` for historical documents (non-normative).

## Supplemental Specs
See `canonical/supplemental/` for transitional or integration docs (non-normative unless explicitly marked).
