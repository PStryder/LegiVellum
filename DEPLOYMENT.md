# LegiVellum Deployment Guide

This guide covers deploying the full LegiVellum primitive stack. The LegiVellum repo contains MemoryGate, AsyncGate, and DeleGate. Other primitives live in sibling repos (ReceiptGate, MetaGate, DepotGate, CogniGate, InterView).

## Recommended Deployment Order

1. ReceiptGate (or MemoryGate profile acting as ReceiptGate)
2. MetaGate
3. DepotGate
4. MemoryGate (if separate from ReceiptGate)
5. AsyncGate
6. DeleGate
7. CogniGate (workers)
8. InterView (read-only introspection)

## Local Development (Docker Compose)

```bash
# From this repo (MemoryGate + AsyncGate + DeleGate)
docker-compose up -d

docker-compose ps

docker-compose logs -f

docker-compose down
```

Service URLs (default):
- MemoryGate: http://localhost:8001
- AsyncGate: http://localhost:8002
- DeleGate: http://localhost:8003

## Authentication

LegiVellum uses API keys for tenant scoping in the MVP. The header `X-API-Key` determines the `tenant_id` used in the database. In production, replace with JWT-backed auth.

## Fly.io Deployment

You can deploy each primitive as its own Fly app. The examples below assume a shared Postgres cluster, but you can also use separate databases per primitive if you prefer harder isolation.

### Shared Postgres (Recommended for MVP)

```bash
fly postgres create --name legivellum-db --region iad
```

Use the database connection string for `DATABASE_URL` (or `RECEIPTGATE_DATABASE_URL` for ReceiptGate).

### MemoryGate (LegiVellum repo)

```bash
cd components/memorygate
fly launch --name legivellum-memorygate --no-deploy
fly secrets set DATABASE_URL="postgresql+asyncpg://..."
fly secrets set LEGIVELLUM_API_KEY="your-production-key"
fly secrets set LEGIVELLUM_TENANT_ID="your-tenant"
fly secrets set ASYNCGATE_URL="https://legivellum-asyncgate.fly.dev"
fly secrets set DELEGATE_URL="https://legivellum-delegate.fly.dev"
fly deploy
```

### AsyncGate (LegiVellum repo)

```bash
cd components/asyncgate
fly launch --name legivellum-asyncgate --no-deploy
fly secrets set DATABASE_URL="postgresql+asyncpg://..."
fly secrets set MEMORYGATE_URL="https://legivellum-memorygate.fly.dev"
fly secrets set LEGIVELLUM_API_KEY="your-production-key"
fly secrets set LEGIVELLUM_TENANT_ID="your-tenant"
fly deploy
```

### DeleGate (LegiVellum repo)

```bash
cd components/delegate
fly launch --name legivellum-delegate --no-deploy
fly secrets set DATABASE_URL="postgresql+asyncpg://..."
fly secrets set MEMORYGATE_URL="https://legivellum-memorygate.fly.dev"
fly secrets set ASYNCGATE_URL="https://legivellum-asyncgate.fly.dev"
fly secrets set LEGIVELLUM_API_KEY="your-production-key"
fly secrets set LEGIVELLUM_TENANT_ID="your-tenant"
fly deploy
```

### ReceiptGate (ReceiptGate repo)

```bash
cd ../ReceiptGate
fly launch --name legivellum-receiptgate --no-deploy
fly secrets set RECEIPTGATE_DATABASE_URL="postgresql+asyncpg://..."
fly secrets set RECEIPTGATE_API_KEY="your-receiptgate-key"
fly secrets set RECEIPTGATE_ALLOW_INSECURE_DEV="false"
fly secrets set RECEIPTGATE_ENABLE_GRAPH_LAYER="false"
fly secrets set RECEIPTGATE_ENABLE_SEMANTIC_LAYER="false"
fly deploy
```

### MetaGate (MetaGate repo)

```bash
cd ../MetaGate
fly launch --name legivellum-metagate --no-deploy
fly secrets set DATABASE_URL="postgresql+asyncpg://..."
fly secrets set JWT_SECRET="your-jwt-secret"
fly secrets set METAGATE_VERSION="0.1"
fly secrets set DEFAULT_TENANT_KEY="default"
fly deploy
```

### DepotGate (DepotGate repo)

```bash
cd ../DepotGate
fly launch --name legivellum-depotgate --no-deploy
fly secrets set DEPOTGATE_POSTGRES_HOST="..."
fly secrets set DEPOTGATE_POSTGRES_USER="..."
fly secrets set DEPOTGATE_POSTGRES_PASSWORD="..."
fly secrets set DEPOTGATE_POSTGRES_METADATA_DB="..."
fly secrets set DEPOTGATE_POSTGRES_RECEIPTS_DB="..."
fly deploy
```

### CogniGate (CogniGate repo)

```bash
cd ../CogniGate
fly launch --name legivellum-cognigate --no-deploy
fly secrets set COGNIGATE_ASYNCGATE_ENDPOINT="https://legivellum-asyncgate.fly.dev"
fly secrets set COGNIGATE_ASYNCGATE_AUTH_TOKEN="..."
fly secrets set COGNIGATE_RECEIPTGATE_ENDPOINT="https://legivellum-receiptgate.fly.dev"
fly secrets set COGNIGATE_RECEIPTGATE_AUTH_TOKEN="..."
fly secrets set COGNIGATE_AI_ENDPOINT="https://openrouter.ai/api/v1"
fly secrets set COGNIGATE_AI_API_KEY="..."
fly secrets set COGNIGATE_API_KEY="..."
fly deploy
```

### InterView (InterView repo)

```bash
cd ../InterView
fly launch --name legivellum-interview --no-deploy
fly secrets set INTERVIEW_RECEIPTGATE_ENDPOINT="https://legivellum-receiptgate.fly.dev"
fly secrets set INTERVIEW_RECEIPTGATE_AUTH_TOKEN="..."
fly deploy
```

## Environment Variables

### Common (LegiVellum components)

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `LEGIVELLUM_API_KEY` | API key for auth | None |
| `LEGIVELLUM_TENANT_ID` | Default tenant for auth | pstryder |
| `ENABLE_METRICS` | Enable Prometheus metrics | false |
| `SQL_ECHO` | SQLAlchemy echo logging | false |

### MemoryGate

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | Service port | 8001 |
| `MEMORYGATE_URL` | Self URL (bootstrap config) | None |
| `ASYNCGATE_URL` | AsyncGate URL (bootstrap config) | None |
| `DELEGATE_URL` | DeleGate URL (bootstrap config) | None |

### AsyncGate

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | Service port | 8002 |
| `MEMORYGATE_URL` | MemoryGate URL | http://memorygate:8001 |
| `LEASE_DURATION_SECONDS` | Lease timeout | 900 |

### DeleGate

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | Service port | 8003 |
| `MEMORYGATE_URL` | MemoryGate URL | http://memorygate:8001 |
| `ASYNCGATE_URL` | AsyncGate URL | http://asyncgate:8002 |

### ReceiptGate

| Variable | Description | Default |
|----------|-------------|---------|
| `RECEIPTGATE_DATABASE_URL` | PostgreSQL connection string | Required |
| `RECEIPTGATE_API_KEY` | API key for auth | None |
| `RECEIPTGATE_ALLOW_INSECURE_DEV` | Disable auth (dev only) | false |
| `RECEIPTGATE_AUTO_MIGRATE_ON_STARTUP` | Apply migrations on startup | true |
| `RECEIPTGATE_ENABLE_GRAPH_LAYER` | Optional graph features | false |
| `RECEIPTGATE_ENABLE_SEMANTIC_LAYER` | Optional semantic features | false |
| `RECEIPTGATE_RECEIPT_BODY_MAX_BYTES` | Max receipt size | 262144 |

### MetaGate

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `JWT_SECRET` | JWT signing secret | Required |
| `JWT_ALGORITHM` | JWT algorithm | HS256 |
| `API_KEY_HEADER` | API key header name | X-API-Key |
| `DEFAULT_TENANT_KEY` | Default tenant | default |
| `DEFAULT_DEPLOYMENT_KEY` | Default deployment | default |

### DepotGate

| Variable | Description | Default |
|----------|-------------|---------|
| `DEPOTGATE_POSTGRES_HOST` | PostgreSQL host | Required |
| `DEPOTGATE_POSTGRES_USER` | PostgreSQL user | depotgate |
| `DEPOTGATE_POSTGRES_PASSWORD` | PostgreSQL password | depotgate |
| `DEPOTGATE_POSTGRES_METADATA_DB` | Metadata DB | depotgate_metadata |
| `DEPOTGATE_POSTGRES_RECEIPTS_DB` | Receipts DB | depotgate_receipts |
| `DEPOTGATE_STORAGE_BACKEND` | Storage backend | filesystem |
| `DEPOTGATE_STORAGE_BASE_PATH` | Staging path | ./data/staging |

### CogniGate

| Variable | Description | Default |
|----------|-------------|---------|
| `COGNIGATE_ASYNCGATE_ENDPOINT` | AsyncGate MCP endpoint | Required |
| `COGNIGATE_ASYNCGATE_AUTH_TOKEN` | AsyncGate auth token | Required |
| `COGNIGATE_RECEIPTGATE_ENDPOINT` | ReceiptGate MCP endpoint | Optional |
| `COGNIGATE_RECEIPTGATE_AUTH_TOKEN` | ReceiptGate token | Optional |
| `COGNIGATE_AI_ENDPOINT` | AI provider endpoint | Required |
| `COGNIGATE_AI_API_KEY` | AI provider key | Required |
| `COGNIGATE_API_KEY` | MCP auth key | Required |

### InterView

| Variable | Description | Default |
|----------|-------------|---------|
| `INTERVIEW_RECEIPTGATE_ENDPOINT` | ReceiptGate MCP endpoint | Required |
| `INTERVIEW_RECEIPTGATE_AUTH_TOKEN` | ReceiptGate token | Required |

## Secret Management

- Use `fly secrets set` for API keys, database URLs, JWT secrets, and AI provider keys.
- Rotate keys regularly; treat all API keys as tenant-scoped credentials.
- Never commit `.env` files or secrets to git.

## Multi-Tenant Setup

- Tenant isolation is enforced by `tenant_id` in the database and resolved from auth.
- Use distinct API keys per tenant; map keys to tenants in auth logic or JWT claims.
- For hard isolation, run separate databases or separate Fly apps per tenant.

## Monitoring and Observability

- Set `ENABLE_METRICS=true` to expose Prometheus metrics (where supported).
- Use MCP health tools (for example, `*_health` via `/mcp` JSON-RPC) for liveness/readiness checks.
- Centralize logs and include correlation keys (task_id, receipt_id, lease_id).

## Backup and Recovery

- PostgreSQL is the system of record. Back it up regularly with `pg_dump` or managed backups.
- Verify restore procedures with a staging database at least once per release.
- Receipt data is append-only; prefer full backups over partial exports.

## Deployment Checklist

- [ ] Postgres provisioned and reachable
- [ ] Schema initialized (`schema/init.sql` for LegiVellum services)
- [ ] Secrets set in Fly (DB URLs, API keys, JWT secrets, AI keys)
- [ ] ReceiptGate and MetaGate healthy
- [ ] MemoryGate health + readiness OK
- [ ] AsyncGate emits receipts to ReceiptGate/MemoryGate
- [ ] DeleGate can create plans and queue tasks
- [ ] Workers (CogniGate or other) can accept leases and emit receipts
- [ ] InterView is read-only and returns receipt views
- [ ] Backups enabled and restore tested
- [ ] Observability wired (metrics + logs)
