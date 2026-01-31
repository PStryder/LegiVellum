# Problemata Demo Stack (P2-001)

This folder contains a local docker-compose assembly for the minimal Problemata
stack: MetaGate, ReceiptGate, AsyncGate, CogniGate, and DepotGate.

## Quick Start

1) Copy the env template and set your AI provider key:

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
- CogniGate is configured to poll AsyncGate and emit receipts to ReceiptGate.
- CogniGate MCP config includes a DepotGate endpoint for artifact delivery.

## Seed Defaults (override via .env)

- Tenant: `PROBLEMATA_TENANT_KEY` (default: `default`)
- Deployment: `PROBLEMATA_DEPLOYMENT_KEY` (default: `local`)
- Principal key: `PROBLEMATA_PRINCIPAL_KEY`
- Auth subject: `PROBLEMATA_AUTH_SUBJECT`
- Profile key: `PROBLEMATA_PROFILE_KEY`
- Manifest key: `PROBLEMATA_MANIFEST_KEY`

## Next

Use this stack with the golden path and escalation demo scripts (P2-002/P2-003).
