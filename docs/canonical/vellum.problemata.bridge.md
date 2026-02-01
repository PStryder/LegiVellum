# Vellum to Problemata Compilation Bridge (v0)

Status: Draft (compiler contract)
Last Updated: 2026-01-26

## Purpose

Define how Vellum modules compile into a valid problemata specification
(`problemata.spec.md`). This bridge makes Vellum the authoring language for
problemata patterns and guarantees that generated specs pass
`problemata.validation.md`.

## Scope

This document specifies:
- Inputs required by a Vellum compiler.
- Mapping rules from Vellum constructs to problemata primitives, topology,
  and config.
- Minimum invariants the compiler must enforce.

It does NOT define a runtime. It defines a build-time translation.

## Inputs

A Vellum -> Problemata compiler MUST take:
1) One or more Vellum modules (source files).
2) A target environment profile (deployment, tenant, and defaults).
3) A component registry (available primitive instances + workers).
4) Secret reference catalog (keys, profiles, auth refs).
5) Policy profiles (InterroGate rules, trust domains, rate limits).

## Output

A single problemata spec that conforms to `problemata.spec.md` and passes
`problemata.validation.md`. The compiler MUST NOT emit secrets in cleartext.

## Core Mapping Rules

### 1) Module Header -> Problemata Metadata

Vellum header:
- Module name -> problemata.id (compiler may namespace, e.g., module.name)
- Version -> problemata.version
- LegiVellum constraint -> compiler compatibility check (optionally stored in
  problemata.labels, e.g., labels.legivellum_version)
- Requires -> compiler dependency check (optionally stored in labels)

### 2) Receipts -> ReceiptGate Integration

Any Vellum receipt operation implies:
- Include ReceiptGate primitive in problemata.
- Add topology edge to ReceiptGate (purpose: receipt_emit).
- Add ReceiptGate config (schema version, auth_ref).

### 3) Artifacts -> DepotGate Integration

Any Vellum artifact operation implies:
- Include DepotGate primitive in problemata.
- Add topology edge to DepotGate (purpose: artifact_store).
- Add DepotGate config (sink, size limits, allowed mimes).

### 4) Async Work -> AsyncGate Integration

Any Vellum Task/Lease operation implies:
- Include AsyncGate primitive in problemata.
- Add topology edges:
  - AsyncGate -> ReceiptGate (receipt_emit)
  - AsyncGate -> DepotGate (artifact_store if it emits artifacts)
- Add AsyncGate config (lease_ttl, retry policy, receipt_mode).

### 5) Memory Operations -> MemoryGate Integration

Any Vellum Memory operations imply:
- Include MemoryGate primitive in problemata.
- Add topology edges for observation/pattern promotion (purpose: observe).

### 6) Planning -> DeleGate (Optional)

If a Vellum module defines planning procedures (explicit planning stage), then:
- Include DeleGate primitive in problemata.
- Add topology edges:
  - DeleGate -> ReceiptGate (receipt_emit)
  - DeleGate -> DepotGate (plan_store)

### 7) Cognitive Execution -> CogniGate (Optional)

If a Vellum module defines cognition procedures that require LLM execution:
- Include CogniGate primitive in problemata.
- Add CogniGate config (ai endpoint/model/api_key_ref, profiles).

### 8) Admission Control -> InterroGate (Optional)

If a Vellum module declares trust/capability constraints requiring admission
control, the compiler SHOULD:
- Include InterroGate primitive.
- Add topology edges that route through InterroGate where policy applies.

### 9) Introspection -> InterView (Optional)

If a Vellum module declares monitoring or introspection requirements:
- Include InterView primitive.
- Add InterView config (allowed_sources, rate limits).

## Required Primitives (Always Present)

Every compiled problemata MUST include:
- MetaGate
- ReceiptGate
- DepotGate

And must include the corresponding bootstrap and receipt/artifact edges per
`problemata.spec.md`.

## Config Resolution Rules

- Secrets MUST be referenced via *_ref keys and resolved by MetaGate at runtime.
- Compiler MUST NOT inline api keys or credentials.
- If a required config key is missing, compilation fails.

## Topology Defaults

- protocol MUST be mcp (explicit or implicit).
- Every primitive MUST have a bootstrap edge to MetaGate.
- Every receipt emitter MUST have a receipt_emit edge to ReceiptGate.
- Every artifact emitter MUST have an artifact_store edge to DepotGate.

## Validation Contract

The compiler MUST run the generated spec through the validation rules in
`problemata.validation.md`. If any validation error occurs, compilation fails
and no spec is emitted.

## Minimal Example

Vellum (conceptual):
```text
# InvoiceProcessor
Version: 1.0.0
LegiVellum: ^1.1.0
Requires:
  - LegiVellum.Receipt >= 1.0.0
  - LegiVellum.Lease >= 1.0.0
  - LegiVellum.Artifact >= 1.0.0

Define procedure ProcessInvoice:
  - queue async OCR task
  - write artifact
  - emit receipt
```

Compiled problemata (sketch):
```yaml
problemata:
  id: invoice_processor
  version: 1.0.0
  tenant_id: ${TENANT_ID}
  owner_principal: ${OWNER_PRINCIPAL}
  labels:
    vellum.module: InvoiceProcessor
    vellum.version: 1.0.0

primitives:
  metagate_main:
    type: metagate
    endpoint: ${METAGATE_URL}
    config: {}

  receiptgate_main:
    type: receiptgate
    endpoint: ${RECEIPTGATE_URL}
    config:
      receipt_schema_version: "1.0"
      auth_ref: receiptgate_auth

  depotgate_main:
    type: depotgate
    endpoint: ${DEPOTGATE_URL}
    config:
      default_sink: "s3://artifacts"

  asyncgate_main:
    type: asyncgate
    endpoint: ${ASYNCGATE_URL}
    config:
      lease_ttl_seconds: 900
      max_attempts: 3
      retry_backoff_seconds: 30
      receipt_mode: receiptgate_integrated
      receiptgate_ref: receiptgate_main

  worker_ocr:
    type: worker
    endpoint: ${OCR_WORKER_URL}
    config:
      capability: ocr

topology:
  - from: metagate_main
    to: metagate_main
    purpose: bootstrap
    protocol: mcp

  - from: receiptgate_main
    to: metagate_main
    purpose: bootstrap
    protocol: mcp

  - from: depotgate_main
    to: metagate_main
    purpose: bootstrap
    protocol: mcp

  - from: asyncgate_main
    to: metagate_main
    purpose: bootstrap
    protocol: mcp

  - from: worker_ocr
    to: metagate_main
    purpose: bootstrap
    protocol: mcp

  - from: asyncgate_main
    to: receiptgate_main
    purpose: receipt_emit
    protocol: mcp

  - from: asyncgate_main
    to: depotgate_main
    purpose: artifact_store
    protocol: mcp

  - from: worker_ocr
    to: receiptgate_main
    purpose: receipt_emit
    protocol: mcp

  - from: worker_ocr
    to: depotgate_main
    purpose: artifact_store
    protocol: mcp

```

Note: The example includes required bootstrap/receipt/artifact edges per
`problemata.spec.md`. Real specs may add more edges and configs.

## Open Extensions (Future)

- Optional compiler directives for InterroGate routing.
- Vellum annotations for trust domains and policy selection.
- Auto-generation of worker capability manifests.
