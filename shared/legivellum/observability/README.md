# LegiVellum Observability Module

Optional metrics and monitoring for LegiVellum services.

## Quick Start

### Enable Metrics

```bash
# In .env
ENABLE_METRICS=true
METRICS_PORT=9090
```

That's it. All services automatically expose metrics at `/metrics`.

### View Metrics

```bash
# MemoryGate
curl http://localhost:8001/metrics

# AsyncGate  
curl http://localhost:8002/metrics

# DeleGate
curl http://localhost:8003/metrics
```

### Disable Metrics

```bash
# In .env
ENABLE_METRICS=false
```

Or simply don't set it (defaults to false). Zero performance impact when disabled.

---

## What You Get

### Automatic HTTP Metrics

Every service automatically tracks:

- **http_requests_total** - Request count per endpoint
- **http_request_duration_seconds** - Response latency (P50, P95, P99)
- **http_requests_in_progress** - Current in-flight requests

Example output:
```
http_requests_total{endpoint="/tasks",method="POST",service="asyncgate",status="201"} 1547
http_request_duration_seconds{endpoint="/tasks",quantile="0.95",service="asyncgate"} 0.123
http_requests_in_progress{service="asyncgate"} 3
```

### Custom Business Metrics

**AsyncGate:**
- `asyncgate_queue_depth` - Tasks waiting in queue
- `asyncgate_retry_queue_depth` - Failed receipts pending retry

**MemoryGate:**
- `memorygate_total_receipts` - Total receipts stored
- `memorygate_active_inbox` - Active obligations (accepted, not archived)

**DeleGate:**
- `delegate_plans_executing` - Plans currently running
- `delegate_total_plans` - Total plans created
- `delegate_retry_queue_depth` - Failed receipts pending retry

---

## Integration with Monitoring Tools

### Prometheus

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'legivellum'
    static_configs:
      - targets:
          - 'memorygate:9090'
          - 'asyncgate:9090'
          - 'delegate:9090'
    scrape_interval: 15s
```

### Grafana

Import the metrics and create dashboards:

**Request Rate:**
```promql
rate(http_requests_total[5m])
```

**Error Rate:**
```promql
rate(http_requests_total{status=~"5.."}[5m])
```

**Queue Depth:**
```promql
asyncgate_queue_depth
```

**P95 Latency:**
```promql
http_request_duration_seconds{quantile="0.95"}
```

### Docker Compose

```yaml
services:
  memorygate:
    environment:
      - ENABLE_METRICS=true
      - METRICS_PORT=9090
  
  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"
  
  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
```

---

## Architecture

### Zero-Cost Abstraction

When `ENABLE_METRICS=false`:
- All metric calls are no-ops
- Zero runtime overhead
- No dependencies loaded
- No network ports opened

### Feature Flag Pattern

```python
from legivellum.observability import observability_enabled, track_gauge

if observability_enabled():
    track_gauge("my_metric", "Description", get_value_func)
```

### Module Structure

```
shared/legivellum/observability/
├── __init__.py         # Public API + feature flag
└── prometheus.py       # Prometheus implementation
```

### Dependencies

```bash
pip install prometheus-client
pip install prometheus-fastapi-instrumentator
```

Added automatically when you install the shared library.

---

## Custom Metrics

### Gauges (Current Value)

```python
from legivellum.observability import track_gauge

# Simple value
track_gauge("queue_size", "Items in queue", lambda: len(my_queue))

# Async value
async def get_count():
    async with get_session() as session:
        result = await session.execute(text("SELECT COUNT(*) FROM table"))
        return result.scalar() or 0

track_gauge("db_count", "Records in DB", lambda: asyncio.run(get_count()))
```

### Counters (Monotonic)

```python
from legivellum.observability import track_counter

# Increment with labels
track_counter("receipts_stored", "Receipts stored", {"phase": "accepted"})
track_counter("tasks_completed", "Tasks completed", {"status": "success"})
```

### Histograms (Distributions)

```python
from legivellum.observability import track_histogram

# Track timing
start = time.time()
# ... do work ...
elapsed = time.time() - start
track_histogram("operation_duration", "Operation time", elapsed, {"op": "process"})
```

---

## Performance Notes

- Metrics collection adds ~1-2ms per request
- Gauge functions called on `/metrics` scrape (not per request)
- No metrics stored in-memory when disabled
- Thread-safe and async-safe

---

## Production Recommendations

1. **Enable in production** - Essential for operational visibility
2. **Use Prometheus** - Industry standard, excellent tooling
3. **Set alerts** - Queue depth, error rate, latency P99
4. **Dashboard templates** - Create reusable Grafana dashboards

---

## Future: OpenTelemetry

The module is designed to support OpenTelemetry tracing in the future:

```python
# Future enhancement
from legivellum.observability import trace_span

@trace_span("process_task")
async def process_task(task_id):
    # Automatic distributed tracing
    ...
```

But for now, Prometheus metrics provide 90% of what you need.

---

## Troubleshooting

**Metrics not appearing:**
1. Check `ENABLE_METRICS=true` in environment
2. Verify dependencies installed: `pip list | grep prometheus`
3. Check logs for "Metrics enabled" message
4. Confirm `/metrics` endpoint accessible

**High memory usage:**
- Metrics are lightweight (<1MB per service)
- If concerned, reduce scrape interval in Prometheus

**Want to remove entirely:**
```bash
# Delete the module
rm -rf shared/legivellum/observability

# Remove from services
grep -l "from legivellum.observability" */src/*.py | xargs sed -i '/observability/d'
```

The module is designed to be completely optional and removable.
