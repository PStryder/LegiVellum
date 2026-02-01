# Problemata Validation Contract (v0)

Status: Draft (normative for instantiation)  
Version: 0.1  
Last updated: 2026-01-26

This document defines atomic validation for problemata specs. Validation is
all-or-nothing: a problemata either passes all checks and instantiates, or it
fails fast with specific errors. No partial deployments.

Normative keywords (MUST, SHOULD, MAY, etc.) follow RFC 2119 semantics.

---

## 1. Atomicity Requirement

Validation MUST be atomic:
- If any check fails, instantiation MUST NOT begin.
- No partial deployments, no partial topology activation.
- Errors MUST be returned with precise diagnostics.

---

## 2. Enforcement Authority

LegiVellum (the platform layer) is the validation authority and MUST enforce
this contract. MetaGate MUST only instantiate a problemata that has already
passed validation (e.g., via signed validation token or approved spec hash).

Validation is performed:
- **Pre-instantiation (required)**: by LegiVellum before any component is launched.
- **Continuous validation (optional)**: by LegiVellum for drift detection only.
  Continuous checks MUST NOT mutate running state automatically unless
  explicitly configured to do so by policy.

---

## 3. Validation Layers (Required)

### 3.1 Structural Validation
Invariants:
- Required primitives present: MetaGate, ReceiptGate, DepotGate
- All topology edges reference existing components
- No orphaned components (every component appears in topology)
- No circular bootstrap dependencies
- Protocol MUST be `mcp` if specified

Failure codes:
- PMV-STRUCT-001: Missing required primitive
- PMV-STRUCT-002: Edge references missing component
- PMV-STRUCT-003: Orphaned component
- PMV-STRUCT-004: Circular bootstrap dependency
- PMV-STRUCT-005: Unsupported protocol (non-MCP)

### 3.2 Configuration Validation
Invariants:
- Each primitive/worker has required config keys
- Secret/profile references are resolvable
- Endpoints are well-formed
- Runtime constraints are feasible (timeouts, max concurrency, etc.)

Failure codes:
- PMV-CONFIG-001: Missing required config key
- PMV-CONFIG-002: Secret/profile ref unresolved
- PMV-CONFIG-003: Malformed endpoint
- PMV-CONFIG-004: Runtime constraints infeasible

### 3.3 Semantic Validation
Invariants:
- Every receipt producer has a path to ReceiptGate
- Every artifact producer has a path to DepotGate
- Every component has a bootstrap path to MetaGate
- Trust domains are consistent across edges
- Capability declarations match routing expectations

Failure codes:
- PMV-SEM-001: Missing receipt route
- PMV-SEM-002: Missing artifact route
- PMV-SEM-003: Missing bootstrap route
- PMV-SEM-004: Trust domain mismatch
- PMV-SEM-005: Capability-route mismatch

### 3.4 Security Validation
Invariants:
- Auth refs resolve to actual secrets
- Permission grants are sufficient for declared actions
- Trust boundaries are respected (no unauthorized edge)

Failure codes:
- PMV-SEC-001: Auth ref unresolved
- PMV-SEC-002: Insufficient permissions
- PMV-SEC-003: Trust boundary violation

---

## 4. When Validation Runs

1) **Pre-instantiation (required)**  
   - Executed by LegiVellum before MetaGate is invoked.
   - A failure blocks instantiation.

2) **Continuous (optional)**  
   - Detects drift or broken assumptions.
   - MUST NOT auto-mutate running systems unless explicitly configured.
   - If configured to enforce, MUST produce a receipt documenting action.

---

## 5. Failure Behavior (Fail-Fast)

On first failure, LegiVellum MUST:
1) Stop validation immediately (fail fast)  
2) Return a structured error response  
3) Ensure MetaGate is NOT invoked to instantiate  

Multi-error mode MAY be supported for diagnostics, but MUST NOT proceed to
instantiation while any error exists.

---

## 6. Error Response Shape

LegiVellum MUST return machine-readable errors with:
- `code` (string)
- `layer` (structural|configuration|semantic|security)
- `path` (JSON pointer or component id)
- `message` (human readable)
- `hint` (optional remediation)

Example:
```json
{
  "status": "failed",
  "errors": [
    {
      "code": "PMV-SEM-001",
      "layer": "semantic",
      "path": "primitives.cognigate-1",
      "message": "Receipt-producing component has no route to ReceiptGate",
      "hint": "Add topology edge: cognigate-1 -> receiptgate-main (receipt_emit)"
    }
  ]
}
```

---

## 7. Rollback Semantics

If validation fails:
- No components are started
- No resources are provisioned
- No receipts are emitted (except optional validation receipts if enabled)

If validation passes and instantiation later fails:
- MetaGate MUST emit a failure receipt documenting the failure boundary
- MetaGate MUST report the failure back to LegiVellum
- Any started components MUST be shut down or quarantined per policy

---

## 8. Diagnostics & Observability

Validation SHOULD emit:
- A validation report artifact (DepotGate)
- A validation receipt (ReceiptGate) if configured

Reports MUST include:
- Spec version + hash
- Validator version
- Pass/fail status
- Error list (if any)

---

## 9. Compliance Checklist (v0)

- [ ] Validation is atomic (all-or-nothing)
- [ ] Structural checks enforced
- [ ] Configuration checks enforced
- [ ] Semantic checks enforced
- [ ] Security checks enforced
- [ ] Clear error codes and paths

---

## 10. Canonical References

See:
- `problemata.spec.md`
- `worker.contract.md`
- `receipt.rules.md`
- `receipt.schema.v1.json`
- `receipt.store.md`

All documents are in `LegiVellum/docs/canonical/`.
