"""
LegiVellum Observability Module

Optional observability layer for operational metrics.
Completely disabled unless ENABLE_METRICS=true in environment.

Zero-cost abstraction when disabled (all calls no-op).
"""
import os

# Feature flag - controls entire module behavior
ENABLED = os.getenv("ENABLE_METRICS", "false").lower() == "true"


def setup_metrics(app, service_name: str = "legivellum"):
    """
    Setup metrics for a FastAPI application.
    
    Automatically instruments:
    - HTTP request count per endpoint
    - Response latency (P50, P95, P99)
    - Error rates by status code
    - In-flight requests
    
    Args:
        app: FastAPI application instance
        service_name: Service identifier for metrics labels
    
    No-op if ENABLE_METRICS != true
    """
    if not ENABLED:
        return
    
    from .prometheus import instrument_app
    instrument_app(app, service_name)


def track_gauge(name: str, description: str, value_func):
    """
    Track a gauge metric (current value of something).
    
    Examples:
        track_gauge("queue_depth", "Tasks in queue", get_queue_size)
        track_gauge("retry_queue", "Failed receipts queued", lambda: len(queue))
    
    Args:
        name: Metric name (will be prefixed with service name)
        description: Human-readable description
        value_func: Callable that returns current value
    
    No-op if ENABLE_METRICS != true
    """
    if not ENABLED:
        return
    
    from .prometheus import register_gauge
    register_gauge(name, description, value_func)


def track_counter(name: str, description: str, labels: dict = None):
    """
    Increment a counter metric.
    
    Examples:
        track_counter("receipts_stored", "Total receipts stored", {"phase": "accepted"})
        track_counter("tasks_completed", "Tasks completed", {"status": "success"})
    
    Args:
        name: Metric name (will be prefixed with service name)
        description: Human-readable description
        labels: Optional label dict for metric dimensions
    
    No-op if ENABLE_METRICS != true
    """
    if not ENABLED:
        return
    
    from .prometheus import increment_counter
    increment_counter(name, description, labels or {})


def track_histogram(name: str, description: str, value: float, labels: dict = None):
    """
    Record a histogram observation (for timing, sizes, etc.).
    
    Examples:
        track_histogram("receipt_size", "Receipt size in bytes", len(data))
        track_histogram("query_duration", "Query time", elapsed_seconds)
    
    Args:
        name: Metric name
        description: Human-readable description
        value: Observed value
        labels: Optional label dict
    
    No-op if ENABLE_METRICS != true
    """
    if not ENABLED:
        return
    
    from .prometheus import observe_histogram
    observe_histogram(name, description, value, labels or {})


def observability_enabled() -> bool:
    """Check if observability is enabled"""
    return ENABLED


__all__ = [
    "setup_metrics",
    "track_gauge",
    "track_counter",
    "track_histogram",
    "observability_enabled",
    "ENABLED",
]
