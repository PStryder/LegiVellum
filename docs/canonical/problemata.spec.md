# Problemata Contract Specification (v0)

Status: Draft (normative for LegiVellum bootstrap)  
Version: 0.1  
Last updated: 2026-01-26

This document defines the Problemata contract: the declarative spec that
describes how a problemata is composed, configured, and instantiated.

Normative keywords (MUST, SHOULD, MAY, etc.) follow RFC 2119 semantics.

---

## 1. Purpose

LegiVellum builds "problemata": production-ready, composable coordination
architectures built from primitives. A problemata spec is the single source of
truth that tells LegiVellum:

1) Which primitives exist  
2) How they connect (who talks to who and why)  
3) How each primitive is configured

Given a valid spec, LegiVellum can instantiate the problemata automatically.

---

## 2. Required Primitives (always present)

Every problemata MUST include:

1) MetaGate (configuration + topology authority)  
2) ReceiptGate (receipt ledger)  
3) DepotGate (artifact storage)

All other primitives are optional and defined per problemata.

---

## 3. Core Invariants

1) **Bootstrap authority**: MetaGate is the canonical source of component
   configuration and topology.
2) **Receipts are required**: Any component that accepts responsibility MUST
   emit receipts to ReceiptGate.
3) **Artifacts are externalized**: Work products MUST be stored in DepotGate
   and referenced by pointer in receipts.
4) **Topology is explicit**: All inter-component communication MUST be
   declared as edges in the spec.
5) **No secrets in spec**: Credentials and secrets MUST be referenced by
   `*_ref` keys and resolved by MetaGate at runtime.

---

## 4. Spec Format (Top-Level)

The problemata spec is a single document (YAML or JSON) with the following
top-level keys:

```
problemata:   # identity + metadata
primitives:   # component instances and their config
topology:     # explicit communication edges
policies:     # optional global policies
```

### 4.1 problemata (identity)

Required fields:
- `id` (string) Unique identifier
- `version` (string) Semantic version
- `tenant_id` (string) Tenant namespace
- `owner_principal` (string) Owning principal/agent

Optional fields:
- `description` (string)
- `labels` (map[string]string)
- `defaults` (object) (see Section 7)

### 4.2 primitives (component instances)

`primitives` is a map keyed by instance id. Each value MUST include:
- `type` (string) One of: metagate, receiptgate, depotgate, asyncgate,
  cognigate, delegategate, interrogate, interview, memorygate, worker
- `endpoint` (string or ref) Where to reach the instance
- `config` (object) Type-specific config (see Section 6)

### 4.3 topology (communication edges)

Each edge MUST include:
- `from` (primitive id)
- `to` (primitive id)
- `purpose` (bootstrap | lease | receipt_emit | artifact_store | plan_store | observe)

Optional:
- `protocol` (mcp only; if omitted, defaults to mcp)
- `auth_ref` (secret reference)
- `trust_domain` (string)
- `timeout_ms` (int)
- `rate_limit` (object)

---

## 5. Minimum Required Edges

Every problemata MUST include:

1) Each primitive -> MetaGate (purpose: bootstrap)
2) Each receipt-emitting primitive -> ReceiptGate (purpose: receipt_emit)
3) Each artifact-emitting primitive -> DepotGate (purpose: artifact_store)

**For problemata exposed to external agents:**
4) Agent interface -> InterroGate (MCP gateway surface)
5) InterroGate -> internal primitives (based on problemata topology)

---

## 5.1 Agent Interface Pattern

External agents access deployed problemata through InterroGate configured as MCP gateway.

**Registration Flow:**
1. Problemata deploys with InterroGate MCP gateway instance
2. InterroGate registers with LegiVellum service (announces endpoint, capabilities)
3. Agent connects once to LegiVellum MCP interface
4. Agent invokes: `problemata.passthrough(problemata_id, input, mode?)`
5. LegiVellum routes to registered InterroGate
6. InterroGate evaluates policy, routes to internal primitives
7. Response mode (sync/async) determined by policy + workload

**Response Modes:**

*Synchronous* - Task completes within `sync_timeout_ms`:
```json
{
  "mode": "sync",
  "result": {...},
  "receipt_id": "rcpt_xyz"
}
```

*Asynchronous* - Task exceeds timeout or policy forces async:
```json
{
  "mode": "async",
  "receipt_id": "rcpt_xyz",
  "status_endpoint": "receiptgate/receipts/rcpt_xyz",
  "artifacts_location": "depotgate/artifacts/job_abc",
  "estimated_completion_ms": 30000
}
```

The problemata (via InterroGate policy) decides execution mode based on:
- Estimated execution time
- Resource requirements
- Policy configuration (`sync_timeout_ms`, `force_async`)
- Current system load

---

## 6. Primitive Config Requirements (v0)

The following keys are REQUIRED unless noted:

### 6.1 MetaGate
- `bootstrap_token_ref` (optional, if using auth)

### 6.2 ReceiptGate
- `receipt_schema_version` (default: "1.0")
- `auth_ref` (if auth required)

### 6.3 DepotGate
- `auth_ref` (if auth required)
- `default_sink` (string)
- `allowed_mime_types` (list) (optional)
- `max_artifact_size_mb` (optional)

### 6.4 AsyncGate
- `lease_ttl_seconds`
- `max_attempts`
- `retry_backoff_seconds`
- `receipt_mode` ("receiptgate_integrated" or "standalone")
- `receiptgate_ref` (which receiptgate to emit to)

### 6.5 CogniGate
- `ai.endpoint`
- `ai.model`
- `ai.api_key_ref`
- `profiles` (inline) OR `profile_ref` (external)
- `tools.mcp_endpoints` (optional)
- `receiptgate_ref`
- `depotgate_ref`

### 6.6 DeleGate
- `planner.model`
- `planner.api_key_ref`
- `plan_store_ref` (DepotGate)
- `receiptgate_ref`

### 6.7 InterroGate
- `policy_profile_id` (required for all surfaces)
- `memorygate_ref` (for lineage queries)
- `metagate_ref` (for policy retrieval)

**For MCP Gateway surfaces (agent access), additionally:**
- `problemata_id` (identifier for registration with LegiVellum service)
- `sync_timeout_ms` (optional, timeout for synchronous responses)
- `force_async` (optional, always use async mode)
- `rate_limits` (optional, per-principal rate limiting config)

**For Internal Admission surfaces (recursion control), additionally:**
- `max_spawn_depth` (required)
- `max_total_descendants` (optional)
- `max_repeats_per_capability` (optional)
- `recursion_budget_initial` (optional)

### 6.8 InterView
- `allowed_sources` (projection_cache, ledger_mirror, component_poll, global_ledger)
- `rate_limits`

### 6.9 Worker (generic)
- `capabilities` (list)
- `receiptgate_ref`
- `depotgate_ref`

---

## 7. Defaults

`problemata.defaults` MAY define shared defaults, such as:
- `receipt_schema_version`
- `trust_domain`
- `depotgate_ref`
- `receiptgate_ref`
- `rate_limits`

Defaults are applied at build time by the LegiVellum compiler and can be
overridden in individual primitive configs.

---

## 8. Bootstrap Contract

Every primitive MUST call MetaGate to retrieve its resolved config before
starting. The MetaGate response MUST include:

- Resolved endpoints for all referenced primitives
- Auth credentials for references (`*_ref`)
- Receipt routing configuration
- Artifact sink configuration
- Policy constraints and trust domain

---

## 9. Validation Rules (non-exhaustive)

LegiVellum MUST reject a problemata spec if:

1) Required primitives are missing  
2) A topology edge references an unknown primitive  
3) A receipt-emitting primitive has no receiptgate edge  
4) An artifact-emitting primitive has no depotgate edge  
5) Required config keys are missing for a primitive type  
6) Any secret is provided inline (not via *_ref)

---

## 10. Example (YAML)

```yaml
problemata:
  id: "prob-summarizer"
  version: "0.1.0"
  tenant_id: "acme"
  owner_principal: "agent.kee"
  description: "Async summarizer"

primitives:
  metagate-main:
    type: metagate
    endpoint: "https://metagate.internal"
    config: {}

  receiptgate-main:
    type: receiptgate
    endpoint: "https://receiptgate.internal"
    config:
      receipt_schema_version: "1.0"
      auth_ref: "secrets/receiptgate_token"

  depotgate-main:
    type: depotgate
    endpoint: "https://depotgate.internal"
    config:
      auth_ref: "secrets/depotgate_token"
      default_sink: "filesystem"

  asyncgate-default:
    type: asyncgate
    endpoint: "https://asyncgate.internal"
    config:
      lease_ttl_seconds: 300
      max_attempts: 2
      retry_backoff_seconds: 15
      receipt_mode: "receiptgate_integrated"
      receiptgate_ref: "receiptgate-main"

  cognigate-summarizer:
    type: cognigate
    endpoint: "https://cognigate.internal"
    config:
      ai:
        endpoint: "https://openrouter.ai/api/v1"
        model: "anthropic/claude-3-opus"
        api_key_ref: "secrets/openrouter_key"
      profile_ref: "profiles/summarizer.yaml"
      receiptgate_ref: "receiptgate-main"
      depotgate_ref: "depotgate-main"

topology:
  - from: "cognigate-summarizer"
    to: "metagate-main"
    purpose: "bootstrap"
  - from: "cognigate-summarizer"
    to: "asyncgate-default"
    purpose: "lease"
  - from: "cognigate-summarizer"
    to: "receiptgate-main"
    purpose: "receipt_emit"
  - from: "cognigate-summarizer"
    to: "depotgate-main"
    purpose: "artifact_store"
  - from: "asyncgate-default"
    to: "receiptgate-main"
    purpose: "receipt_emit"
```

---

## 11. Canonical Receipt Specs

Receipt validation and routing MUST follow:
- `receipt.rules.md`
- `receipt.schema.v1.json`
- `receipt.store.md`

These canonical specs live alongside this document.

---

## 12. Validation Contract

All problemata MUST pass atomic validation as defined in:
- `problemata.validation.md`

Validation is enforced by LegiVellum (platform layer) and is all-or-nothing.
MetaGate instantiates only validated problemata.
