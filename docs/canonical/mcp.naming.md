# MCP Tool Naming Convention (v0)

Status: Normative  
Version: 0.1  
Last updated: 2026-02-23

This document defines the canonical naming contract for MCP tool surfaces
across LegiVellum-compatible services.

## 1. Core Rule

Service-owned tools MUST be namespaced:

```
<service>.<verb_or_resource>
```

Examples:
- `asyncgate.create_task`
- `receiptgate.submit_receipt`
- `metagate.bootstrap`
- `cognigate.execute_job`

## 2. Transport Rule

MCP HTTP interactions MUST use:
- `tools/list`
- `tools/call`

Service-to-service calls MUST target `/mcp` and MUST NOT require legacy REST
surfaces for core primitive interoperability.

## 3. Canonical Service Prefixes

- `asyncgate.*`
- `cognigate.*`
- `delegate.*`
- `depotgate.*`
- `interrogate.*`
- `interview.*`
- `metagate.*`
- `receiptgate.*`
- `memory_*` (MemoryGate FastMCP contract)

Note: MemoryGate uses `memory_*` function-style tool names as its canonical
surface. This is a permitted exception for backward compatibility.

## 4. Compatibility and Migration

When adopting namespaced tools from legacy un-namespaced names:

1. Services SHOULD provide compatibility aliases during migration windows.
2. Docs MUST identify the canonical name and alias name.
3. New integrations MUST use canonical names only.
4. Aliases MAY be removed only after an announced deprecation window.

## 5. Reserved Names

Tool names ending in `.health` are reserved for health/service-info calls and
SHOULD be read-only and side-effect free.

## 6. Cross-Service Contract Priority

If a repo-level README conflicts with this document:

1. `docs/canonical/mcp.naming.md`
2. `docs/canonical/worker.contract.md`
3. service-local README

## 7. Known Deviations

Recorded so this document does not imply compliance that does not exist. Unlike
the MemoryGate `memory_*` exception in §3, these are **not** sanctioned — they
are open discrepancies awaiting a decision.

### InterView

InterView advertises seven of its eight tools in a `<verb>.<domain>.interview`
form rather than `interview.*`:

| Advertised | §1 form would be |
|------------|------------------|
| `status.receipts.interview` | `interview.status_receipts` |
| `search.receipts.interview` | `interview.search_receipts` |
| `get.receipt.interview` | `interview.get_receipt` |
| `health.async.interview` | `interview.health_async` |
| `queue.async.interview` | `interview.queue_async` |
| `inventory.artifacts.depot.interview` | `interview.inventory_artifacts_depot` |
| `global.ledger.receipts` | `interview.global_ledger_receipts` |
| `interview.health` | *(already compliant)* |

The form is deliberate and documented in InterView's own README as a "Surface
Convention" with a verb taxonomy, so this is a genuine design disagreement
rather than an oversight. Under §6 this document outranks that README, which
means the code is currently non-compliant.

Resolving it requires a choice, not a doc edit:

- Rename the tools to `interview.*`, which breaks any existing caller and the
  `InterView/tests/test_mcp_snapshot.py` contract snapshot that pins the current names; or
- Grant InterView a permitted exception in §3 alongside MemoryGate's, and state
  why observation surfaces name themselves differently from action surfaces.

Note that `global.ledger.receipts` carries no service segment at all, so it is
not merely differently ordered — it is unnamespaced, which §1 forbids outright
regardless of which convention wins.

