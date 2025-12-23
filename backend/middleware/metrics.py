"""
Prometheus Metrics for E-Commerce Customer Intelligence API

OPTIONAL: Enable with environment variable ENABLE_PROMETHEUS_METRICS=true

Tracks:
- Request duration by endpoint
- Request count by status code
- Error rates
- Database query performance
- Cache hit/miss rates
- Integration call performance (Slack, Gorgias, Anthropic)

Note: Railway provides built-in infrastructure monitoring (CPU, memory, network).
      This adds application-level metrics for production observability.
"""

import os
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Request, Response
from fastapi.responses import Response as FastAPIResponse
import time
from typing import Callable
import logging

logger = logging.getLogger(__name__)

# Check if metrics are enabled
METRICS_ENABLED = os.getenv('ENABLE_PROMETHEUS_METRICS', 'false').lower() == 'true'

if METRICS_ENABLED:
    logger.info("✅ Prometheus metrics enabled - /metrics endpoint will be available")
else:
    logger.info("ℹ️  Prometheus metrics disabled - using Railway's built-in monitoring only")

# ==================== Metrics Definitions ====================

# HTTP Request Metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
)

http_requests_in_progress = Gauge(
    'http_requests_in_progress',
    'Number of HTTP requests currently being processed',
    ['method', 'endpoint']
)

# Database Metrics
db_query_duration_seconds = Histogram(
    'db_query_duration_seconds',
    'Database query duration in seconds',
    ['query_type'],
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0)
)

db_connections_total = Gauge(
    'db_connections_total',
    'Number of active database connections'
)

db_query_errors_total = Counter(
    'db_query_errors_total',
    'Total database query errors',
    ['query_type', 'error_type']
)

# Cache Metrics
cache_hits_total = Counter(
    'cache_hits_total',
    'Total cache hits',
    ['cache_type']
)

cache_misses_total = Counter(
    'cache_misses_total',
    'Total cache misses',
    ['cache_type']
)

cache_hit_rate = Gauge(
    'cache_hit_rate',
    'Cache hit rate (percentage)',
    ['cache_type']
)

# AI/NLP Metrics
ai_query_duration_seconds = Histogram(
    'ai_query_duration_seconds',
    'AI query processing duration in seconds',
    ['model', 'tool'],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0)
)

ai_tokens_used_total = Counter(
    'ai_tokens_used_total',
    'Total tokens consumed by AI queries',
    ['model', 'type']  # type: input or output
)

ai_query_errors_total = Counter(
    'ai_query_errors_total',
    'Total AI query errors',
    ['model', 'error_type']
)

# Integration Metrics
integration_call_duration_seconds = Histogram(
    'integration_call_duration_seconds',
    'External integration call duration in seconds',
    ['integration', 'operation'],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0)
)

integration_errors_total = Counter(
    'integration_errors_total',
    'Total integration errors',
    ['integration', 'error_type']
)

# MCP Tool Metrics
mcp_tool_calls_total = Counter(
    'mcp_tool_calls_total',
    'Total MCP tool calls',
    ['tool_name', 'status']  # status: success or error
)

mcp_tool_duration_seconds = Histogram(
    'mcp_tool_duration_seconds',
    'MCP tool execution duration in seconds',
    ['tool_name'],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0)
)

# Data Metrics
customers_loaded_total = Gauge(
    'customers_loaded_total',
    'Total number of customers loaded in memory'
)

archetypes_loaded_total = Gauge(
    'archetypes_loaded_total',
    'Total number of archetypes loaded in memory'
)

# Business Metrics
churn_predictions_high_risk = Gauge(
    'churn_predictions_high_risk',
    'Number of customers at high churn risk (>0.7)'
)

churn_predictions_medium_risk = Gauge(
    'churn_predictions_medium_risk',
    'Number of customers at medium churn risk (0.5-0.7)'
)

customer_ltv_p95 = Gauge(
    'customer_ltv_p95',
    '95th percentile customer LTV'
)


# ==================== Middleware ====================

async def metrics_middleware(request: Request, call_next: Callable) -> Response:
    """
    Middleware to track HTTP request metrics.

    Tracks:
    - Request duration
    - Status codes
    - In-progress requests

    Note: Only active if ENABLE_PROMETHEUS_METRICS=true
    """
    # Skip if metrics disabled
    if not METRICS_ENABLED:
        return await call_next(request)

    # Skip metrics endpoint itself to avoid recursion
    if request.url.path == "/metrics":
        return await call_next(request)

    # Extract endpoint and method
    method = request.method
    endpoint = request.url.path

    # Track in-progress requests
    http_requests_in_progress.labels(method=method, endpoint=endpoint).inc()

    # Track request duration
    start_time = time.time()

    try:
        # Process request
        response = await call_next(request)
        status_code = response.status_code

        # Record metrics
        duration = time.time() - start_time
        http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)
        http_requests_total.labels(method=method, endpoint=endpoint, status_code=status_code).inc()

        return response

    except Exception as e:
        # Record error
        duration = time.time() - start_time
        http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)
        http_requests_total.labels(method=method, endpoint=endpoint, status_code=500).inc()

        logger.error(f"Request error: {e}", exc_info=True)
        raise

    finally:
        # Decrement in-progress counter
        http_requests_in_progress.labels(method=method, endpoint=endpoint).dec()


# ==================== Helper Functions ====================

def track_db_query(query_type: str, duration: float, success: bool = True, error_type: str = None):
    """Track database query metrics. No-op if metrics disabled."""
    if not METRICS_ENABLED:
        return

    db_query_duration_seconds.labels(query_type=query_type).observe(duration)

    if not success and error_type:
        db_query_errors_total.labels(query_type=query_type, error_type=error_type).inc()


def track_cache_access(cache_type: str, hit: bool):
    """Track cache hit/miss. No-op if metrics disabled."""
    if not METRICS_ENABLED:
        return

    if hit:
        cache_hits_total.labels(cache_type=cache_type).inc()
    else:
        cache_misses_total.labels(cache_type=cache_type).inc()

    # Update hit rate (calculate from counters)
    hits = cache_hits_total.labels(cache_type=cache_type)._value.get()
    misses = cache_misses_total.labels(cache_type=cache_type)._value.get()
    total = hits + misses

    if total > 0:
        hit_rate = (hits / total) * 100
        cache_hit_rate.labels(cache_type=cache_type).set(hit_rate)


def track_ai_query(model: str, tool: str, duration: float, input_tokens: int = 0, output_tokens: int = 0, success: bool = True, error_type: str = None):
    """Track AI query metrics. No-op if metrics disabled."""
    if not METRICS_ENABLED:
        return

    ai_query_duration_seconds.labels(model=model, tool=tool).observe(duration)

    if input_tokens > 0:
        ai_tokens_used_total.labels(model=model, type='input').inc(input_tokens)

    if output_tokens > 0:
        ai_tokens_used_total.labels(model=model, type='output').inc(output_tokens)

    if not success and error_type:
        ai_query_errors_total.labels(model=model, error_type=error_type).inc()


def track_integration_call(integration: str, operation: str, duration: float, success: bool = True, error_type: str = None):
    """Track external integration call metrics. No-op if metrics disabled."""
    if not METRICS_ENABLED:
        return

    integration_call_duration_seconds.labels(integration=integration, operation=operation).observe(duration)

    if not success and error_type:
        integration_errors_total.labels(integration=integration, error_type=error_type).inc()


def track_mcp_tool(tool_name: str, duration: float, success: bool = True):
    """Track MCP tool call metrics. No-op if metrics disabled."""
    if not METRICS_ENABLED:
        return

    status = 'success' if success else 'error'
    mcp_tool_calls_total.labels(tool_name=tool_name, status=status).inc()
    mcp_tool_duration_seconds.labels(tool_name=tool_name).observe(duration)


def update_data_metrics(customers: int, archetypes: int):
    """Update data load metrics. No-op if metrics disabled."""
    if not METRICS_ENABLED:
        return

    customers_loaded_total.set(customers)
    archetypes_loaded_total.set(archetypes)


def update_business_metrics(high_risk_count: int, medium_risk_count: int, ltv_p95: float):
    """Update business metrics. No-op if metrics disabled."""
    if not METRICS_ENABLED:
        return

    churn_predictions_high_risk.set(high_risk_count)
    churn_predictions_medium_risk.set(medium_risk_count)
    customer_ltv_p95.set(ltv_p95)


# ==================== Metrics Endpoint ====================

async def metrics_endpoint() -> FastAPIResponse:
    """
    Prometheus metrics endpoint.

    Returns metrics in Prometheus exposition format.
    """
    metrics_data = generate_latest()
    return FastAPIResponse(content=metrics_data, media_type=CONTENT_TYPE_LATEST)
