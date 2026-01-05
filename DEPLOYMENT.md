# LegiVellum Deployment Guide

This guide covers deploying the LegiVellum trilogy (MemoryGate, AsyncGate, DeleGate) locally and to Fly.io.

## Dual Interface: REST API + MCP

Each component supports both REST API (FastAPI) and MCP (Model Context Protocol) interfaces:

- **REST API**: Traditional HTTP endpoints for service-to-service communication
- **MCP**: Tool-based interface for AI agents (Claude Desktop, etc.)

## Local Development

### Prerequisites

- Docker and Docker Compose
- Python 3.12+ (for local development without Docker)

### Quick Start (REST API)

```bash
# Start all services with Docker Compose
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Service URLs

- **MemoryGate**: http://localhost:8001
- **AsyncGate**: http://localhost:8002
- **DeleGate**: http://localhost:8003

### API Authentication

For development, use the pre-configured API keys:

```bash
# MemoryGate
curl -X POST http://localhost:8001/bootstrap \
  -H "X-API-Key: dev-key-pstryder" \
  -H "Content-Type: application/json" \
  -d '{"agent_name": "test"}'

# AsyncGate
curl -X POST http://localhost:8002/tasks \
  -H "X-API-Key: dev-key-pstryder" \
  -H "Content-Type: application/json" \
  -d '{"task_type": "test", "task_summary": "Test task", "recipient_ai": "test", "from_principal": "user", "for_principal": "agent"}'

# DeleGate
curl -X POST http://localhost:8003/plans \
  -H "X-API-Key: dev-key-pstryder" \
  -H "Content-Type: application/json" \
  -d '{"intent": "Generate a test plan", "principal_ai": "test"}'
```

## MCP Server Configuration

### Claude Desktop Integration

Add the LegiVellum MCP servers to your Claude Desktop configuration:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "memorygate": {
      "command": "python",
      "args": ["/path/to/LegiVellum/components/memorygate/src/mcp_server.py"],
      "env": {
        "DATABASE_URL": "postgresql+asyncpg://postgres:postgres@localhost:5432/legivellum",
        "LEGIVELLUM_TENANT_ID": "pstryder"
      }
    },
    "asyncgate": {
      "command": "python",
      "args": ["/path/to/LegiVellum/components/asyncgate/src/mcp_server.py"],
      "env": {
        "DATABASE_URL": "postgresql+asyncpg://postgres:postgres@localhost:5432/legivellum",
        "LEGIVELLUM_TENANT_ID": "pstryder",
        "MEMORYGATE_URL": "http://localhost:8001"
      }
    },
    "delegate": {
      "command": "python",
      "args": ["/path/to/LegiVellum/components/delegate/src/mcp_server.py"],
      "env": {
        "DATABASE_URL": "postgresql+asyncpg://postgres:postgres@localhost:5432/legivellum",
        "LEGIVELLUM_TENANT_ID": "pstryder",
        "MEMORYGATE_URL": "http://localhost:8001",
        "ASYNCGATE_URL": "http://localhost:8002"
      }
    }
  }
}
```

See `mcp-config.example.json` for a complete example.

### Available MCP Tools

**MemoryGate Tools:**
- `memory_bootstrap` - Initialize session with inbox and context
- `memory_store_receipt` - Store a receipt (accepted/complete/escalate)
- `memory_get_inbox` - Get active obligations for an agent
- `memory_get_receipt` - Get a single receipt by ID
- `memory_get_task_timeline` - Get all receipts for a task
- `memory_archive_receipt` - Archive a processed receipt
- `memory_search` - Search receipts with filters

**AsyncGate Tools:**
- `queue_task` - Queue a new task for async execution
- `get_task` - Get task details by ID
- `list_tasks` - List tasks with filters
- `lease_task` - Worker polls for and leases a task
- `complete_task` - Worker marks task complete
- `fail_task` - Worker marks task failed
- `heartbeat` - Worker extends lease

**DeleGate Tools:**
- `create_delegation_plan` - Create a plan from intent
- `get_plan` - Get a plan by ID
- `list_plans` - List plans with filters
- `execute_plan` - Execute a plan by queuing tasks
- `register_worker` - Register a worker
- `list_workers` - List registered workers
- `analyze_intent` - Analyze intent without creating plan

### Running MCP Mode in Docker

To run a component in MCP mode (stdio) instead of REST:

```bash
docker run -e RUN_MODE=mcp -e DATABASE_URL=... legivellum-memorygate
```

## Fly.io Deployment

### Prerequisites

- [Fly CLI](https://fly.io/docs/hands-on/install-flyctl/) installed
- Fly.io account configured

### Database Setup

First, create a PostgreSQL database on Fly.io:

```bash
# Create the database
fly postgres create --name legivellum-db --region iad

# Get the connection string
fly postgres connect -a legivellum-db
```

### Deploy Services

Deploy in order (MemoryGate first, then AsyncGate, then DeleGate):

```bash
# 1. Deploy MemoryGate
cd components/memorygate
fly launch --name legivellum-memorygate --no-deploy
fly secrets set DATABASE_URL="postgresql+asyncpg://..."
fly secrets set LEGIVELLUM_API_KEY="your-production-key"
fly secrets set LEGIVELLUM_TENANT_ID="your-tenant"
fly deploy

# 2. Deploy AsyncGate
cd ../asyncgate
fly launch --name legivellum-asyncgate --no-deploy
fly secrets set DATABASE_URL="postgresql+asyncpg://..."
fly secrets set MEMORYGATE_URL="https://legivellum-memorygate.fly.dev"
fly secrets set LEGIVELLUM_API_KEY="your-production-key"
fly secrets set LEGIVELLUM_TENANT_ID="your-tenant"
fly deploy

# 3. Deploy DeleGate
cd ../delegate
fly launch --name legivellum-delegate --no-deploy
fly secrets set DATABASE_URL="postgresql+asyncpg://..."
fly secrets set MEMORYGATE_URL="https://legivellum-memorygate.fly.dev"
fly secrets set ASYNCGATE_URL="https://legivellum-asyncgate.fly.dev"
fly secrets set LEGIVELLUM_API_KEY="your-production-key"
fly secrets set LEGIVELLUM_TENANT_ID="your-tenant"
fly deploy
```

### Initialize Database

Run the schema initialization on your Fly.io PostgreSQL:

```bash
# Connect to the database
fly postgres connect -a legivellum-db

# Then run the contents of schema/init.sql
```

Or use `psql` with the connection string.

## Environment Variables

### Common Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `RUN_MODE` | `rest` for HTTP API, `mcp` for MCP server | rest |
| `LEGIVELLUM_API_KEY` | API key for auth | None |
| `LEGIVELLUM_TENANT_ID` | Default tenant ID | pstryder |

### MemoryGate

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | Service port | 8001 |

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

## Health Checks

All services expose health endpoints (REST mode only):

- `GET /health` - Basic health check (always returns 200 if running)
- `GET /ready` - Readiness check (verifies database connectivity)

## Architecture

```
                    ┌─────────────────┐
                    │   PostgreSQL    │
                    │   (shared DB)   │
                    └────────┬────────┘
                             │
       ┌─────────────────────┼─────────────────────┐
       │                     │                     │
       ▼                     ▼                     ▼
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│ MemoryGate  │◀──────│  AsyncGate  │       │  DeleGate   │
│   :8001     │       │    :8002    │──────▶│    :8003    │
│             │◀──────│             │       │             │
│ Receipts &  │       │ Task Queue  │       │   Planner   │
│   Memory    │       │  & Workers  │       │             │
└─────────────┘       └─────────────┘       └─────────────┘
     ▲                      ▲                      ▲
     │                      │                      │
     └──────────────────────┴──────────────────────┘
                    MCP or REST API
```

- **MemoryGate**: Single-writer receipt store, bootstrap, inbox queries
- **AsyncGate**: Task queue, worker leasing, receipt emission to MemoryGate
- **DeleGate**: Plan creation, worker registry, task submission to AsyncGate

Each component exposes both REST API (HTTP) and MCP (stdio) interfaces.
