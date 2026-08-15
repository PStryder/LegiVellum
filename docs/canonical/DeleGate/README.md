# DeleGate

**Pure Planning and Capability Brokering for LegiVellum**

DeleGate is a task delegation framework that decomposes high-level intent into structured execution Plans. It brokers capability between principals (AI agents) and self-describing workers (MCP servers), but DeleGate itself **never executes work**—it only produces Plans.

## Canonical Alignment (LegiVellum)

- Bootstraps from MetaGate for resolved config, secrets, and routing.
- Emits receipts to ReceiptGate (canonical ledger; may be MemoryGate profile).
- Stores artifacts in DepotGate; receipts carry artifact pointers.
- MetaGate instantiates only validated problemata (validation by LegiVellum platform).

## Status

**Specification:** v0 (DRAFT)
**Implementation:** Phase 1 MVP (Initial Draft)

See: `SPEC-DG-0000.txt` for complete specification.

## Quick Start

```bash
# Install dependencies
pip install -e ".[dev]"

# Set environment variables
export DELEGATE_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/delegate"
export DELEGATE_MEMORYGATE_URL="http://localhost:8001"
export DELEGATE_ASYNCGATE_URL="http://localhost:8002"
export DELEGATE_RECEIPTGATE_URL="http://localhost:8003"
export DELEGATE_DEPOTGATE_URL="http://localhost:8004"

# Run database migrations
alembic upgrade head

# Start the server
python -m delegate.main

# Or run as MCP server
python -m delegate.mcp_server
```

## Project Structure

```
src/delegate/
├── __init__.py      # Package exports
├── models.py        # Pydantic models (Plan, Steps, Workers, Trust)
├── config.py        # Configuration via environment
├── database.py      # PostgreSQL async connection
├── registry.py      # Worker registry with capability matching
├── planner.py       # Plan generation logic
├── receipts.py      # ReceiptGate receipt emission
├── api.py           # MCP tool handlers
├── mcp_server.py    # MCP server interface
└── main.py          # Application entry point
```

## Core Doctrine

**CRITICAL INVARIANT:** If output is not a valid Plan, DeleGate has failed.

DeleGate is a pure planner:
- **Input:** Intent (natural language or structured) + optional context
- **Output:** Plan (structured, validated) OR Escalation (cannot plan)
- **Never:** Executes work, tracks progress, retries, or makes decisions for principals

## Plan Structure

Plans consist of three sections:
1. **Metadata** - plan_id, confidence, scope, trust policy
2. **Steps** - Five step types: call_worker, queue_execution, wait_for, aggregate, escalate
3. **References** - Input sources (MemoryGate) and expected outputs (DepotGate + receipt pointers)

## Worker Registry

DeleGate maintains a live registry of available workers through MCP introspection:
- Workers self-register with tool manifests
- Semantic capability matching
- Trust tier validation (trusted, verified, sandbox, untrusted)
- Performance hints (latency, cost, availability)

## Five Step Types

1. **call_worker** - Direct synchronous execution
2. **queue_execution** - Async execution via AsyncGate
3. **wait_for** - Block until receipts/tasks complete
4. **aggregate** - Request synthesis by principal
5. **escalate** - Cannot proceed, deliver report and request decision

## Trust Model

**Trust is NOT transitive.** Principal trusting DeleGate ≠ auto-trusting Workers.

Trust tiers:
- **Trusted** (tier 3): Signed by root authority, full access
- **Verified** (tier 2): Code audit, organization-approved
- **Sandbox** (tier 1): Isolated execution, limited resources
- **Untrusted** (tier 0): Manual approval, full audit

## MCP Tool Surface

Names are namespaced `delegate.*` per `mcp.naming.md`. This list matches what
`tools/list` reports.

- `delegate.create_delegation_plan` - Create plan from intent
- `delegate.validate_plan` - Validate plan structure
- `delegate.get_plan` - Get a plan by ID
- `delegate.list_plans` - List stored plans
- `delegate.analyze_intent` - Analyze intent without creating plan
- `delegate.register_worker` - Register worker with capabilities
- `delegate.search_workers` - Search workers by capability
- `delegate.match_workers` - Match workers to intent
- `delegate.list_workers` - List all registered workers
- `delegate.worker_status` - Get worker status by ID
- `delegate.delete_worker` - Remove a worker from the registry
- `delegate.health` - Health check
- `delegate.stats` - Registry and planning statistics
- `delegate.cache_clear` - Clear registry cache (admin)

## Cognition

Decomposition is cognitive, and DeleGate does not hold cognition of its own.
With `DELEGATE_AI_PROVIDER=cognigate` it calls `cognigate.plan`, which runs
CogniGate's planning phase and stops. CogniGate returns a plan document;
DeleGate remains the only component here that mints obligations from it, so the
authority boundary is unchanged.

`DELEGATE_COGNITION_SCOPES` bounds which classified scopes consult cognition,
and `DELEGATE_PLANNING_FALLBACK` decides what happens when it is unreachable.
The default is `escalate`: a heuristic plan is structurally indistinguishable
from a reasoned one, so substituting it silently would claim thinking that did
not happen, and **Plan OR Escalation (cannot plan)** already makes refusal a
legitimate output. See the DeleGate README for the full variable table.

## Testing

```bash
pytest tests/ -v
```

## License

Proprietary - Technomancy Labs
