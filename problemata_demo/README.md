# Problemata Demo Stack (P2-001)

This folder contains a local docker-compose assembly for the Problemata stack:
MetaGate, ReceiptGate, AsyncGate, DepotGate, InterView, DeleGate, InterroGate,
and (behind a profile) CogniGate.

Service ports: MetaGate 8100, DepotGate 8200, ReceiptGate 8300, AsyncGate 8400,
CogniGate 8500 (stub AI), InterView 8600, DeleGate 8700, InterroGate 8800.

## Quick Start

1) Copy the env template and set your AI provider key (only needed if you run CogniGate):

```bash
copy .env.example .env
# then edit .env and set COGNIGATE_AI_API_KEY
```

2) Start the stack to build images and run services:

```bash
docker compose up -d
```

3) (Optional) Seed MetaGate with a demo principal/manifest:

```bash
docker compose --profile seed run --rm metagate-seed
```

The seed output prints an API key for MetaGate bootstrap calls.

## Demo Scripts (Minimal Worker)

These scripts run a minimal worker loop (no AI key required) and exercise the
receipt chain using ReceiptGate's MCP endpoints.

Golden path:

```bash
python golden_path.py
```

Escalation path (uses lease expiry + fallback worker):

```bash
python escalation_path.py
```

Observation path — runs a task, then answers "what happened?" entirely through
InterView (read-only: ledger, queue, and artifact inventory):

```bash
python observe_path.py                 # run a task, then observe it
python observe_path.py --task-id UUID  # observe an existing task
```

Topology path — authors a Problemata in the control plane, publishes it to
MetaGate, and bootstraps a component into the resulting topology. Requires the
seed, which issues two deliberately separate credentials: an **admin operator**
that may publish topology, and a **component owner** that may only bootstrap
into it.

```bash
docker compose --profile seed run --rm metagate-seed
# export the two keys the seed prints
export METAGATE_API_KEY=mgk_...        # operator (admin)
export METAGATE_OWNER_API_KEY=mgk_...  # owner (component)
python topology_path.py
```

Bind path — publishes a Problemata owned by AsyncGate's principal, restarts
AsyncGate, and asserts the running gate took its world-truth from MetaGate
rather than from environment variables. Needs the operator key only:

```bash
export METAGATE_API_KEY=mgk_...        # operator (admin)
python bind_asyncgate_path.py
```

AsyncGate keeps `ASYNCGATE_RECEIPTGATE_URL` configured, so explicit
configuration still wins and a bootstrap regression cannot break the other
paths. The proof is that the gate reached MetaGate and resolved the manifest.

## CogniGate

CogniGate runs by default using a **stub AI provider**: it answers locally and
deterministically, so the lease -> plan -> execute -> complete path runs with
no model and no API key. Stub output is prefixed `[stub]` and reports its model
as `stub/echo`, so it is recognisable if it ever reaches an artifact.

To run it against a real provider:

```bash
export COGNIGATE_AI_PROVIDER=openrouter
export COGNIGATE_AI_API_KEY=sk-...
docker compose up -d cognigate
```

## Service Ports (host -> container)

- MetaGate: http://localhost:8100
- DepotGate: http://localhost:8200
- ReceiptGate: http://localhost:8300
- AsyncGate: http://localhost:8400
- CogniGate: http://localhost:8500

## Notes

- ReceiptGate runs against a local SQLite file stored in the `receiptgate_data`
  Docker volume. (Swap to PostgreSQL if desired.)
- AsyncGate is configured to emit receipts directly to ReceiptGate.
- AsyncGate escalation routing defaults to `fallback-worker` (edit
  `docker-compose.yml` or env vars if you want a different fallback).
- CogniGate (optional) is configured to poll AsyncGate and emit receipts to ReceiptGate.
- CogniGate MCP config includes a DepotGate endpoint for artifact delivery.

## Seed Defaults (override via .env)

- Tenant: `PROBLEMATA_TENANT_KEY` (default: `default`)
- Deployment: `PROBLEMATA_DEPLOYMENT_KEY` (default: `local`)
- Principal key: `PROBLEMATA_PRINCIPAL_KEY`
- Auth subject: `PROBLEMATA_AUTH_SUBJECT`
- Profile key: `PROBLEMATA_PROFILE_KEY`
- Manifest key: `PROBLEMATA_MANIFEST_KEY`

## Waiting for readiness

`docker compose up -d` returns before the stack can serve traffic: ReceiptGate
and DepotGate have no healthcheck, and ReceiptGate pip-installs itself on
container start. Block until every service answers its MCP health tool:

```bash
python wait_for_stack.py --timeout 300
```

It exits non-zero and names whatever never came up.

## Continuous integration

The `Stack` workflow (`.github/workflows/stack.yml`) runs exactly this
sequence on every push and PR, plus nightly: build the stack, wait for
readiness, then run both demo scripts. Sibling repositories are checked out
beside LegiVellum from their default branches, so the workflow gates the
integration surface rather than any single repo's pending changes.

A push to AsyncGate or ReceiptGate cannot trigger a workflow in this
repository, which is why the nightly run exists. Wiring each gate to dispatch
this workflow on push requires a cross-repo token.

## Next

Use this stack with the golden path and escalation demo scripts (P2-002/P2-003).
