# MetaGate Bootstrap (v0)

Status: Normative
Version: 0.1
Last updated: 2026-08-15

Every gate's alignment note lists "bootstrap config from MetaGate" as required
contract behaviour. This document defines what that means, because the gates
now share one implementation of it rather than each carrying a copy.

## 1. What bootstrap is for

A gate starts with configured values from its environment. Bootstrap asks
MetaGate for the topology it belongs to and fills in what the operator did not
specify — principally the endpoints of the other primitives it must reach.

It is a *description* mechanism. MetaGate answers "what does the mesh say you
are wired to?"; it does not instruct, schedule, or dispatch. See
`MetaGate/alignment.md` for the describe-only boundary and the forbidden keys
that enforce it.

## 2. Two load-bearing properties

**Bootstrap must never prevent startup.** MetaGate is a describe-only,
non-blocking authority, not a dependency to wait on. Every failure — endpoint
unreachable, timeout, auth rejected, no binding present, malformed packet —
degrades to a logged warning and "carry on with configured values". A bootstrap
authority that can take the mesh down is a hidden master, which the
architecture forbids.

**Explicit configuration wins.** An operator who set an endpoint said something
specific. Bootstrap fills gaps and never overrides intent. When the mesh
disagrees with an explicitly configured value, the divergence is logged rather
than silently resolved, so it is visible without being enforced.

## 3. Configuration

Every gate honours the same four variables, under its own prefix
(`ASYNCGATE_`, `COGNIGATE_`, `DELEGATE_`, `DEPOTGATE_`, `INTERVIEW_`,
`INTERROGATE_`, `RECEIPTGATE_`):

| Variable | Default | Meaning |
|----------|---------|---------|
| `<PREFIX>METAGATE_ENDPOINT` | *(unset)* | MetaGate MCP endpoint. Unset disables bootstrap entirely; the gate starts on configured values alone. |
| `<PREFIX>METAGATE_API_KEY` | *(unset)* | Credential presented to MetaGate. A component-owner key is sufficient; publishing topology requires an operator key. |
| `<PREFIX>METAGATE_COMPONENT_KEY` | the gate's own name | Which component in the manifest this process is. Override only when running several instances of one primitive in a topology that names them separately. |
| `<PREFIX>METAGATE_BOOTSTRAP_TIMEOUT_SECONDS` | `5.0` | Per-call timeout. Bounded deliberately: a slow MetaGate must not become a slow startup. |

## 4. Bindings

A gate declares which primitive *types* it wants resolved, and which settings
attribute each one lands in. Bindings are keyed by type rather than by service
ref because refs are Problemata-authored names (`receiptgate-main`) while types
are contract vocabulary, stable across every Problemata that declares the
primitive.

Current bindings, as implemented:

| Gate | Component key | Resolves |
|------|---------------|----------|
| AsyncGate | `asyncgate` | `receiptgate` → `receiptgate_endpoint` |
| CogniGate | `cognigate` | `receiptgate` → `receiptgate_endpoint`, `asyncgate` → `asyncgate_endpoint` |
| DeleGate | `delegate` | `receiptgate` → `receiptgate_url`, `memorygate` → `memorygate_url`, `asyncgate` → `asyncgate_url` |
| DepotGate | `depotgate` | `receiptgate` → `receiptgate_endpoint` |
| InterView | `interview` | `receiptgate` → `receiptgate_url`, `asyncgate` → `asyncgate_url`, `depotgate` → `depotgate_url` |
| InterroGate | `interrogate` | `receiptgate` → `receiptgate_url`, `memorygate` → `memorygate_url` |
| ReceiptGate | `receiptgate` | *(none)* — ReceiptGate is a leaf: everything calls it, it calls no other primitive. |

The differing setting names (`receiptgate_endpoint` vs `receiptgate_url`) are
each gate's existing configuration vocabulary, not a contract difference. The
binding exists precisely so a gate does not have to rename its settings to
participate.

## 5. Startup acknowledgement

After bootstrap, a gate reports back:

- `metagate.startup_ready` — with the `startup_id` from the bootstrap packet and
  its `build_version`. MetaGate records which build is running where; the
  contract requires `build_version`, so it is always sent, defaulting to
  `0.1.0` when the gate does not set one.
- `metagate.startup_failed` — when the gate cannot start.

Acknowledgement is best-effort for the same reason bootstrap is: failing to
report readiness must not prevent being ready.

## 6. Implementation

One shared client, at `LegiVellum/shared/legivellum/metagate_bootstrap.py`:

```python
BOOTSTRAP_BINDINGS = (
    EndpointBinding(primitive_type="receiptgate", setting="receiptgate_endpoint"),
)
result = await bootstrap_from_metagate(settings, bindings=BOOTSTRAP_BINDINGS)
await acknowledge_startup(settings, result)
```

Gates load it from a sibling LegiVellum checkout rather than vendoring it. In
the demo stack that path is a read-only mount (`../../LegiVellum/shared`); the
loader degrades to no-bootstrap when the module cannot be found, consistent
with §2.

AsyncGate implemented bootstrap first and this is that implementation
generalized. The four identical `parents[4]` IndexErrors fixed across four
repositories in August 2026 are what the duplicated version looked like a few
months on, and are the reason this is shared rather than copied.
