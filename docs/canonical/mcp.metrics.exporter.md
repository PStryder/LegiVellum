# MCP Metrics Exporter (Canonical)

LegiVellum is MCP-only. Prometheus and similar systems expect HTTP `/metrics`,
so metrics must be bridged by an MCP-aware exporter that calls MCP tools and
re-exposes the payload for scraping.

This document defines the canonical contract for that exporter.

## Scope

- Bridge MCP metrics tools to Prometheus scrape endpoints.
- Support any LegiVellum component that exposes a `*.metrics` MCP tool.
- Preserve MCP auth and tenant isolation.

## Non-Goals

- Replace component health tools.
- Bypass MCP auth or policy.
- Standardize every metric name (components own their metrics).

## Required Behavior

1. **Poll via MCP only**
   - The exporter MUST call MCP tools (e.g., `cognigate.metrics`).
   - Direct component HTTP metrics endpoints MUST NOT be assumed.

2. **Auth-required by default**
   - The exporter MUST support MCP auth tokens (API key or OAuth).
   - Tokens MUST be stored in secrets and never logged.

3. **Bounded responses**
   - The exporter SHOULD pass `max_bytes` when supported.
   - The exporter MUST tolerate truncation and partial payloads.

4. **Fail-safe output**
   - If polling fails, the exporter SHOULD continue serving the last good
     payload and expose exporter health metrics.

## MCP Tool Contract (Recommended)

Components SHOULD expose a tool named `<component>.metrics` with:

- `format` (optional): `text` or `structured` (default: `text`)
- `max_bytes` (optional): integer size cap

Example tool call payload:
```json
{
  "tool": "cognigate.metrics",
  "arguments": {
    "format": "text",
    "max_bytes": 200000
  }
}
```

## Exporter Responsibilities

### Scrape Loop

- Poll each target at a fixed interval (default 15s).
- Record poll latency and errors in exporter metrics.
- Cache the last successful payload per target.

### Output Surface

Expose an HTTP endpoint (default `/metrics`) with:
- The latest successful payload from each target.
- Exporter self-metrics:
  - `mcp_exporter_up{target=...}` (0/1)
  - `mcp_exporter_last_success_timestamp{target=...}`
  - `mcp_exporter_poll_latency_seconds{target=...}`

### Multi-Target Behavior

If a target fails:
- Keep serving its last known payload (if any).
- Set `mcp_exporter_up{target}` to 0.
- Optionally include a comment line describing the error (Prometheus comment).

## Configuration (Reference)

```yaml
exporter:
  listen_addr: 0.0.0.0:9090
  scrape_path: /metrics
  poll_interval_seconds: 15
  request_timeout_seconds: 5

targets:
  - name: cognigate
    mcp_endpoint: http://cognigate:8000/mcp
    tool: cognigate.metrics
    format: text
    max_bytes: 200000
    auth:
      type: api_key
      value_env: COGNIGATE_API_KEY

  - name: asyncgate
    mcp_endpoint: http://asyncgate:8080/mcp
    tool: asyncgate.metrics
    format: text
    max_bytes: 200000
    auth:
      type: api_key
      value_env: ASYNCGATE_API_KEY
```

## Security Notes

- Treat exporter tokens as production secrets.
- Rotate tokens regularly and support reload without restart.
- Enforce per-tenant tokens if the target is multi-tenant.

## Validation Expectations

LegiVellum validation SHOULD accept an exporter-only `/metrics` endpoint as an
infrastructure concern, not a component contract. Components remain MCP-only.

