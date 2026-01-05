"""
Prometheus Metrics Implementation

Uses prometheus-fastapi-instrumentator for automatic HTTP metrics.
Provides custom gauge/counter/histogram tracking.
"""
import os
import logging
from typing import Callable, Dict, Any

logger = logging.getLogger(__name__)

# Lazy imports - only load if metrics enabled
_instrumentator = None
_gauges: Dict[str, Any] = {}
_counters: Dict[str, Any] = {}
_histograms: Dict[str, Any] = {}

METRICS_PORT = int(os.getenv("METRICS_PORT", "9090"))


def instrument_app(app, service_name: str):
    """
    Instrument FastAPI app with Prometheus metrics.
    
    Adds automatic metrics:
    - http_requests_total
    - http_request_duration_seconds
    - http_requests_in_progress
    """
    global _instrumentator
    
    try:
        from prometheus_fastapi_instrumentator import Instrumentator
        
        _instrumentator = Instrumentator(
            should_group_status_codes=False,
            should_ignore_untemplated=True,
            should_respect_env_var=False,  # We control via ENABLE_METRICS
            should_instrument_requests_inprogress=True,
            excluded_handlers=["/metrics", "/health", "/ready"],
            env_var_name="ENABLE_METRICS",
            inprogress_name="http_requests_in_progress",
            inprogress_labels=True,
        )
        
        # Add service name label to all metrics
        _instrumentator.add(
            lambda metrics: metrics.labels(service=service_name)
        )
        
        # Instrument and expose
        _instrumentator.instrument(app).expose(
            app,
            endpoint="/metrics",
            include_in_schema=False,
        )
        
        logger.info(
            f"Metrics enabled for {service_name}",
            extra={"endpoint": "/metrics", "port": METRICS_PORT}
        )
        
    except ImportError:
        logger.warning(
            "ENABLE_METRICS=true but prometheus-fastapi-instrumentator not installed. "
            "Install with: pip install prometheus-fastapi-instrumentator"
        )
    except Exception as e:
        logger.error(f"Failed to setup metrics: {e}")


def register_gauge(name: str, description: str, value_func: Callable):
    """
    Register a gauge metric that tracks current value.
    
    Gauges are updated on-demand when /metrics endpoint is scraped.
    """
    global _gauges
    
    try:
        from prometheus_client import Gauge
        
        if name in _gauges:
            return
        
        gauge = Gauge(
            name,
            description,
            labelnames=['service'],
        )
        
        _gauges[name] = {
            'gauge': gauge,
            'value_func': value_func,
        }
        
        # Set initial value
        try:
            value = value_func()
            gauge.labels(service=os.getenv("SERVICE_NAME", "legivellum")).set(value)
        except Exception as e:
            logger.warning(f"Failed to set initial gauge value for {name}: {e}")
        
        logger.debug(f"Registered gauge: {name}")
        
    except ImportError:
        logger.warning("prometheus_client not installed")
    except Exception as e:
        logger.error(f"Failed to register gauge {name}: {e}")


def update_gauge(name: str, value: float):
    """Update a gauge metric with new value"""
    if name not in _gauges:
        return
    
    try:
        gauge_data = _gauges[name]
        service = os.getenv("SERVICE_NAME", "legivellum")
        gauge_data['gauge'].labels(service=service).set(value)
    except Exception as e:
        logger.error(f"Failed to update gauge {name}: {e}")


def increment_counter(name: str, description: str, labels: dict):
    """
    Increment a counter metric.
    
    Counters only go up (monotonic).
    """
    global _counters
    
    try:
        from prometheus_client import Counter
        
        if name not in _counters:
            label_names = ['service'] + list(labels.keys())
            counter = Counter(
                name,
                description,
                labelnames=label_names,
            )
            _counters[name] = counter
        
        service = os.getenv("SERVICE_NAME", "legivellum")
        label_values = {'service': service, **labels}
        _counters[name].labels(**label_values).inc()
        
    except ImportError:
        pass
    except Exception as e:
        logger.error(f"Failed to increment counter {name}: {e}")


def observe_histogram(name: str, description: str, value: float, labels: dict):
    """
    Record a histogram observation.
    
    Histograms track distributions (latency, sizes, etc.).
    """
    global _histograms
    
    try:
        from prometheus_client import Histogram
        
        if name not in _histograms:
            label_names = ['service'] + list(labels.keys())
            histogram = Histogram(
                name,
                description,
                labelnames=label_names,
            )
            _histograms[name] = histogram
        
        service = os.getenv("SERVICE_NAME", "legivellum")
        label_values = {'service': service, **labels}
        _histograms[name].labels(**label_values).observe(value)
        
    except ImportError:
        pass
    except Exception as e:
        logger.error(f"Failed to observe histogram {name}: {e}")


def update_all_gauges():
    """
    Update all registered gauges by calling their value functions.
    
    This can be called periodically or on /metrics requests.
    """
    for name, gauge_data in _gauges.items():
        try:
            value = gauge_data['value_func']()
            service = os.getenv("SERVICE_NAME", "legivellum")
            gauge_data['gauge'].labels(service=service).set(value)
        except Exception as e:
            logger.warning(f"Failed to update gauge {name}: {e}")
