# DepotGate v0

**Artifact Staging, Closure Verification, and Outbound Logistics**

DepotGate is an infrastructure primitive for managing artifact delivery in asynchronous and multi-agent systems. It enforces declared closure requirements before releasing deliverables, preventing both premature delivery and permanent limbo.

## Canonical Alignment (LegiVellum)

- Bootstraps from MetaGate for resolved config, secrets, and routing.
- Receipts that reference artifacts are stored in ReceiptGate; DepotGate provides the artifact pointers.
- MetaGate instantiates only validated problemata (validation by LegiVellum platform).

## Quick Start

### Using Docker Compose

```bash
# Start PostgreSQL and DepotGate
docker-compose up -d

# MCP endpoint available at http://localhost:8000/mcp
```

### Local Development

```bash
# Install dependencies
pip install -e ".[dev]"

# Set up PostgreSQL (requires running instance)
# Copy and edit environment config
cp .env.example .env

# Run the service
python -m depotgate.main
```

## MCP Tool Surface

Transport: MCP only (no secondary facade in the canonical contract).

**Tools:**
- `stage_artifact` - Stage an artifact in DepotGate
- `list_staged_artifacts` - List artifacts staged for a task
- `get_artifact` - Get artifact metadata by ID
- `declare_deliverable` - Declare a deliverable contract
- `check_closure` - Check if closure requirements are met
- `ship` - Ship a deliverable (verifies closure first)
- `purge` - Purge staged artifacts

## MCP Usage (Tool Call Payload)

```json
{
  "tool": "stage_artifact",
  "arguments": {
    "root_task_id": "agent-task-1",
    "content_base64": "<base64-encoded-bytes>",
    "mime_type": "application/json",
    "artifact_role": "final_output"
  }
}
```

## Configuration

Environment variables (prefix: `DEPOTGATE_`):

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | 0.0.0.0 | Service bind address |
| `PORT` | 8000 | Service port |
| `DEBUG` | false | Enable debug mode |
| `TENANT_ID` | default | Single tenant identifier |
| `POSTGRES_HOST` | localhost | PostgreSQL host |
| `POSTGRES_PORT` | 5432 | PostgreSQL port |
| `POSTGRES_USER` | depotgate | Database user |
| `POSTGRES_PASSWORD` | depotgate | Database password |
| `POSTGRES_METADATA_DB` | depotgate_metadata | Metadata database |
| `POSTGRES_RECEIPTS_DB` | depotgate_receipts | Receipts database |
| `STORAGE_BACKEND` | filesystem | Storage backend type |
| `STORAGE_BASE_PATH` | ./data/staging | Staging directory |
| `STORAGE_MAX_ARTIFACT_SIZE_MB` | 100 | Max artifact size (0=unlimited) |
| `ENABLED_SINKS` | filesystem | Comma-separated sink list |
| `SINK_FILESYSTEM_BASE_PATH` | ./data/shipped | Shipped artifacts directory |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        DepotGate                            │
├─────────────────────────────────────────────────────────────┤
│  Transport Layer (MCP)                                        │
│  └── /mcp/*    - MCP tools                             │
├─────────────────────────────────────────────────────────────┤
│  Core Services                                              │
│  ├── StagingArea      - Artifact storage management        │
│  ├── DeliverableManager - Declarations & closure checking  │
│  ├── ShippingService  - Ship & purge operations            │
│  └── ReceiptStore     - Event logging                      │
├─────────────────────────────────────────────────────────────┤
│  Storage Layer                                              │
│  ├── StorageBackend   - Pluggable artifact storage         │
│  │   └── FilesystemStorageBackend                          │
│  └── OutboundSink     - Pluggable shipping destinations    │
│      ├── FilesystemSink                                    │
│      └── HttpSink                                          │
├─────────────────────────────────────────────────────────────┤
│  Persistence                                                │
│  ├── PostgreSQL (metadata) - Artifacts, deliverables       │
│  └── PostgreSQL (receipts) - Event receipts                │
└─────────────────────────────────────────────────────────────┘
```

## Core Concepts

- **Artifact**: Opaque payload produced by work. DepotGate never inspects content.
- **Artifact Pointer**: Content-opaque reference with metadata only.
- **Staging Area**: Namespace where artifacts accumulate before shipment.
- **Deliverable**: Declared outbound unit with requirements and destination.
- **Closure**: Explicit verification that all declared requirements are met.
- **Receipt**: Immutable event record for auditability.

## Non-Goals (Hard Boundaries)

DepotGate **MUST NOT**:
- Inspect artifact contents
- Transform or modify artifacts
- Schedule work or spawn tasks
- Retry or repair failures
- Infer intent or completeness

## Testing

```bash
# Run tests
pytest

# With coverage
pytest --cov=depotgate

# Run only unit tests (no DB required)
pytest tests/test_models.py tests/test_storage.py tests/test_sinks.py
```

## License

MIT
