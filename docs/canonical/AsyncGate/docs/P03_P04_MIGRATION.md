# P0.3 + P0.4: MCP Transport Security Migration Guide

**Date:** 2026-01-26  
**Priority:** P0 (Production Blocker)  
**Status:** COMPLETE

---

## What Changed

### P0.3: CORS Removed (MCP-Only Transport)
AsyncGate no longer exposes browser-facing endpoints, so CORS no longer applies. Access control now relies on MCP authentication and MetaGate bindings.

**Changes:**
- Removed CORS configuration from the runtime surface
- MCP-only transport for all tool calls
- Access governed by auth + MetaGate profile/binding

### P0.4: Rate Limiting Enabled by Default
AsyncGate is protected against DoS and cost spikes by default.

**Changes:**
- `rate_limit_enabled` defaults to `True`
- `rate_limit_active` forces ON in staging/production
- Development can still disable if needed

---

## Migration Steps

### 1. Remove CORS Environment Variables
Delete any `ASYNCGATE_CORS_*` entries from `.env` or deployment secrets. They are ignored in MCP-only mode.

### 2. Verify MCP Access Control
Ensure your MCP clients authenticate and are bound via MetaGate:
- Valid API key or JWT
- Correct principal -> profile -> manifest binding
- Tool access enforced by profile policy

### 3. Verify Rate Limiting
**Check Configuration:**
```python
from asyncgate.config import settings

print(f"Rate limiting enabled: {settings.rate_limit_enabled}")
print(f"Rate limiting active: {settings.rate_limit_active}")
print(f"Calls per window: {settings.rate_limit_default_calls}")
print(f"Window: {settings.rate_limit_default_window_seconds}s")
```

**Test Rate Limiting (MCP):**
Call a cheap tool repeatedly (e.g., 110 times). Last calls should return a rate-limit error.

```json
{
  "tool": "asyncgate.health",
  "arguments": {}
}
```

---

## Configuration Reference

### Rate Limiting Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `rate_limit_enabled` | `true` | Enable rate limiting |
| `rate_limit_backend` | `"memory"` | Backend (`memory` or `redis`) |
| `rate_limit_default_calls` | `100` | Calls per window |
| `rate_limit_default_window_seconds` | `60` | Window size in seconds |

### Environment-Based Overrides

| Environment | Rate Limiting | Notes |
|-------------|---------------|-------|
| `production` | FORCED ON | Cannot disable |
| `staging` | FORCED ON | Cannot disable |
| `development` | Configurable | Can disable for testing |

---

## Breaking Changes

### CORS Configuration Removed
Browser-origin CORS no longer applies. Any front-end access must go through an MCP relay or server-side MCP client.

### Rate Limiting Now Active
High-volume clients may hit limits. Adjust limits for known heavy users if needed.

---

## Testing Checklist

- [ ] MCP client auth succeeds
- [ ] MetaGate binding resolves correct profile/manifest
- [ ] Rate limiting returns structured tool errors when exceeded
- [ ] `asyncgate.health` returns OK under normal load
