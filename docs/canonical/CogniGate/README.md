# CogniGate

CogniGate is a leased cognitive execution worker.

It performs bounded, tool-mediated AI cognition on behalf of other systems, materializes durable artifacts, and reports lifecycle state through receipts.

CogniGate does not think for itself.
It executes cognition under lease, with explicit constraints, explicit tools, and explicit outputs.

## Canonical Alignment (LegiVellum)

- Bootstraps from MetaGate for resolved config, secrets, and routing.
- Accepts leases from AsyncGate, emits receipts to ReceiptGate (canonical ledger; may be MemoryGate profile).
- Writes artifacts to DepotGate; receipts carry artifact pointers.
- MetaGate instantiates only validated problemata (validation by LegiVellum platform).

## What CogniGate Does

- Accepts leased work from AsyncGate
- Constructs prompts from static instruction profiles and job-scoped payloads
- Produces a machine-readable plan (advisory, not authoritative)
- Executes cognition step-by-step using a minimal, advertised tool surface
- Delivers outputs to explicitly defined sinks (DepotGate by default)
- Reports progress and completion via receipts, not logs

All cognition is:
- Job-scoped
- Stateless
- Externally materialized
- Receipted at every state transition

## What CogniGate Is Not

CogniGate intentionally does not:
- Maintain conversation or memory
- Own goals or intent
- Decide where outputs go
- Expose third-party APIs directly to models
- Store or emit full reasoning chains
- Operate as a chatbot or assistant

These exclusions are design constraints, not omissions.

## Quick Start

### Prerequisites

- Python 3.11+
- Docker (for deployment)
- AsyncGate instance (for work leasing)
- AI provider credentials (e.g., OpenRouter)

### Installation

```bash
pip install -e ".[dev]"
```

### Configuration

In LegiVellum mode, CogniGate bootstraps from MetaGate and receives resolved
endpoints, auth, and profiles. Environment variables remain the standalone
configuration surface and are used when MetaGate is not present.

Environment variables (prefix `COGNIGATE_`):

| Variable | Default | Description |
|----------|---------|-------------|
| `STANDALONE_MODE` | true | Run without AsyncGate (default for GP use) |
| `RECEIPT_STORAGE_DIR` | ./receipts | Directory for receipt storage |
| `ASYNCGATE_ENDPOINT` | http://localhost:8080 | AsyncGate MCP endpoint |
| `ASYNCGATE_AUTH_TOKEN` | - | Authentication token for AsyncGate |
| `RECEIPTGATE_ENDPOINT` | - | ReceiptGate MCP endpoint (canonical receipt ledger) |
| `RECEIPTGATE_AUTH_TOKEN` | - | Authentication token for ReceiptGate |
| `RECEIPTGATE_TENANT_ID` | - | Tenant ID for receipt writes (server-validated) |
| `RECEIPTGATE_EMIT_RECEIPTS` | true | Enable receipt emission to ReceiptGate |
| `AI_ENDPOINT` | https://openrouter.ai/api/v1 | AI provider endpoint |
| `AI_API_KEY` | - | API key for AI provider |
| `AI_MODEL` | anthropic/claude-3-opus | AI model to use |
| `AI_MAX_TOKENS` | 4096 | Maximum tokens for AI responses |
| `POLLING_INTERVAL` | 5.0 | Polling interval in seconds |
| `MAX_CONCURRENT_JOBS` | 1 | Maximum concurrent job executions |
| `JOB_TIMEOUT` | 300 | Job timeout in seconds |
| `MAX_RETRIES` | 3 | Maximum retries for failed tool calls |
| `CONFIG_DIR` | /etc/cognigate | Configuration directory |
| `PLUGINS_DIR` | /etc/cognigate/plugins | Plugins directory |
| `PROFILES_DIR` | /etc/cognigate/profiles | Instruction profiles directory |
| `HOST` | 0.0.0.0 | Server host |
| `PORT` | 8000 | Server port |
| `WORKER_ID` | cognigate-worker-1 | Worker identifier |

### Running

```bash
# Start the server
uvicorn cognigate.api:app --host 0.0.0.0 --port 8000
```

Note: CogniGate is MCP-only. The only HTTP route is `/mcp`, and all
health/metrics access is via MCP tools.

## Standalone Mode

CogniGate can run in standalone mode as a general-purpose cognitive worker without requiring AsyncGate for job leasing. In this mode, jobs are submitted via MCP tools and receipts are stored locally.

### When to Use Standalone Mode

- Direct integration with other systems via MCP tools
- Development and testing without AsyncGate
- Standalone deployment scenarios
- Simple single-worker setups

### Configuration

1. Copy the standalone example configuration:
   ```bash
   cp .env.standalone.example .env
   ```

2. Configure your AI provider credentials:
   ```bash
   COGNIGATE_AI_API_KEY=your-openrouter-api-key
   COGNIGATE_API_KEY=cg_your-secret-api-key
   ```

3. Start in standalone mode:
   ```bash
   COGNIGATE_STANDALONE_MODE=true uvicorn cognigate.api:app --host 0.0.0.0 --port 8000
   ```

### Usage

Submit a job and get the result synchronously (MCP tool):

```json
{
  "tool": "cognigate.execute_job",
  "arguments": {
    "task_id": "example-001",
    "payload": {
      "instruction": "Summarize the key points of this text",
      "context": "Your input text here..."
    },
    "profile": "default"
  }
}
```

Receipts are queried via MCP tools:
- `cognigate.list_receipts`
- `cognigate.get_receipt`

### Docker Standalone

```bash
docker-compose -f docker-compose.standalone.yml up
```

## MCP Tool Surface

### Health and Status
- `cognigate.health` - Health check
- `cognigate.health_detailed` - Detailed health with component status
- `cognigate.ready` - Readiness check
- `cognigate.live` - Liveness check
- `cognigate.metrics` - Metrics snapshot (text or structured)

#### `cognigate.metrics` arguments
- `format` (optional): `text` (default) or `structured`
- `max_bytes` (optional): Upper bound on response size

Example (structured snapshot):
```json
{
  "tool": "cognigate.metrics",
  "arguments": {
    "format": "structured",
    "max_bytes": 200000
  }
}
```

### Job Execution (Standalone)
- `cognigate.execute_job` - Execute job synchronously
- `cognigate.submit_job` - Submit a job for background execution
- `cognigate.cancel_job` - Cancel a running job

### Receipts
- `cognigate.list_receipts` - List recent receipts
- `cognigate.get_receipt` - Get a specific receipt

### AsyncGate Polling
- `cognigate.polling_start` - Start polling AsyncGate for work
- `cognigate.polling_stop` - Stop polling AsyncGate

### Configuration Discovery
- `cognigate.list_profiles` - List available instruction profiles
- `cognigate.list_sinks` - List available output sinks
- `cognigate.list_mcp_adapters` - List available MCP adapters

## Model Tool Surface

CogniGate advertises a minimal tool surface to the AI model:

### `mcp_call`

Call a method on an MCP (Model Context Protocol) server.

Parameters:
- `server` (required): Name of the MCP server to call
- `method` (required): MCP method to invoke (e.g., 'resources/read', 'tools/call')
- `params` (optional): Parameters for the MCP method

### `artifact_write`

Write an artifact to the configured output sink.

Parameters:
- `content` (required): Content to write to the artifact
- `metadata` (optional): Additional metadata for the artifact

## Bootstrap Configuration

On startup, CogniGate loads configuration from the filesystem:

### Instruction Profiles

YAML files in `PROFILES_DIR` defining:
- `name`: Profile identifier
- `system_instructions`: System prompt instructions
- `formatting_constraints`: Output formatting rules
- `planning_schema`: Planning output schema
- `tool_usage_rules`: Rules for tool usage

### MCP Endpoints

YAML configuration in `CONFIG_DIR/mcp.yaml`:
```yaml
mcp_endpoints:
  - name: github
    endpoint: https://mcp.example.com/github
    auth_token: optional-token
    read_only: true
    enabled: true
```

## Plugin Architecture

### Sink Plugins

Output sinks can be added by:
1. Dropping a Python module into the plugins directory
2. Restarting the service

Sinks self-register with:
- `sink_id`
- `config_schema`
- `deliver()` handler

### MCP Adapters

MCP adapters connect to upstream MCP servers with:
- Configurable endpoints
- Optional authentication
- Read-only mode support

## Design Principles

- Cognition under lease
- Artifacts over messages
- Receipts over logs
- Execution over intent
- Boring in the right places

CogniGate exists to make AI cognition interruptible, auditable, recoverable, and safe to embed in real systems—without pretending it's a mind.

## License

MIT
