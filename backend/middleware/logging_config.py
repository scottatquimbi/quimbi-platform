"""
Structured Logging Configuration

Uses structlog for JSON-formatted logs with correlation IDs.
Makes production debugging much easier.

Features:
- Request correlation IDs (track requests across services)
- JSON output (easily parseable by log aggregators)
- Automatic context injection (user_id, endpoint, method)
- Performance tracking (request duration)
- Compatible with Railway logs
"""

import logging
import structlog
import uuid
from typing import Any, Dict
from fastapi import Request
import time

# ==================== Configuration ====================

def configure_logging(log_level: str = "INFO", json_logs: bool = True):
    """
    Configure structured logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_logs: If True, output JSON format. If False, use console format.
    """

    # Determine processors based on output format
    if json_logs:
        # JSON format for production (Railway, CloudWatch, etc.)
        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer()
        ]
    else:
        # Console format for local development
        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
            structlog.dev.ConsoleRenderer()
        ]

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Also configure standard library logging (for third-party libs)
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, log_level.upper()),
        force=True,
    )


# ==================== Correlation ID Middleware ====================

async def correlation_id_middleware(request: Request, call_next):
    """
    Middleware to add correlation IDs to all requests.

    Correlation IDs help track requests across services and logs.
    Format: UUID4 (e.g., "a1b2c3d4-e5f6-7890-abcd-ef1234567890")

    Also tracks request duration and logs request/response.
    """
    # Generate or extract correlation ID
    correlation_id = request.headers.get("X-Correlation-ID") or request.headers.get("X-Request-ID") or str(uuid.uuid4())

    # Add to structlog context (will appear in all logs during this request)
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        correlation_id=correlation_id,
        method=request.method,
        path=request.url.path,
        client_ip=request.client.host if request.client else "unknown"
    )

    # Get logger
    logger = structlog.get_logger()

    # Log request
    start_time = time.time()
    logger.info(
        "request_started",
        query_params=dict(request.query_params) if request.query_params else None,
        user_agent=request.headers.get("user-agent", "unknown")
    )

    # Process request
    try:
        response = await call_next(request)

        # Calculate duration
        duration = time.time() - start_time

        # Add correlation ID to response headers
        response.headers["X-Correlation-ID"] = correlation_id

        # Log response
        logger.info(
            "request_completed",
            status_code=response.status_code,
            duration_seconds=round(duration, 3)
        )

        return response

    except Exception as e:
        # Calculate duration
        duration = time.time() - start_time

        # Log error
        logger.error(
            "request_failed",
            error=str(e),
            error_type=type(e).__name__,
            duration_seconds=round(duration, 3),
            exc_info=True
        )

        raise

    finally:
        # Clear context after request
        structlog.contextvars.clear_contextvars()


# ==================== Helper Functions ====================

def get_logger(name: str = None):
    """
    Get a structured logger instance.

    Usage:
        logger = get_logger(__name__)
        logger.info("user_logged_in", user_id=123, email="user@example.com")

    Args:
        name: Logger name (usually __name__ of the module)

    Returns:
        Structured logger instance
    """
    return structlog.get_logger(name)


def log_with_context(**context):
    """
    Add context to current logger that persists for the request.

    Usage:
        log_with_context(user_id=123, customer_id="5971333382399")
        # All subsequent logs will include user_id and customer_id

    Args:
        **context: Key-value pairs to add to logging context
    """
    structlog.contextvars.bind_contextvars(**context)


def log_function_call(func_name: str, **kwargs):
    """
    Log a function call with arguments.

    Usage:
        log_function_call("calculate_churn_risk", customer_id="123", model="v2")
    """
    logger = structlog.get_logger()
    logger.debug("function_called", function=func_name, **kwargs)


def log_database_query(query_type: str, duration: float, row_count: int = None, error: str = None):
    """
    Log a database query with performance metrics.

    Usage:
        log_database_query("get_customer", duration=0.043, row_count=1)
    """
    logger = structlog.get_logger()

    if error:
        logger.error(
            "database_query_failed",
            query_type=query_type,
            duration_seconds=round(duration, 3),
            error=error
        )
    else:
        logger.info(
            "database_query_completed",
            query_type=query_type,
            duration_seconds=round(duration, 3),
            row_count=row_count
        )


def log_integration_call(integration: str, operation: str, duration: float, success: bool = True, error: str = None):
    """
    Log an external integration call.

    Usage:
        log_integration_call("slack", "post_message", duration=0.234, success=True)
    """
    logger = structlog.get_logger()

    if success:
        logger.info(
            "integration_call_completed",
            integration=integration,
            operation=operation,
            duration_seconds=round(duration, 3)
        )
    else:
        logger.error(
            "integration_call_failed",
            integration=integration,
            operation=operation,
            duration_seconds=round(duration, 3),
            error=error
        )


def log_ai_query(model: str, tool: str, duration: float, input_tokens: int = 0, output_tokens: int = 0, cost: float = None, error: str = None):
    """
    Log an AI query with token usage and cost.

    Usage:
        log_ai_query("claude-3-5-haiku", "query_customers", duration=1.2, input_tokens=500, output_tokens=300)
    """
    logger = structlog.get_logger()

    if error:
        logger.error(
            "ai_query_failed",
            model=model,
            tool=tool,
            duration_seconds=round(duration, 3),
            error=error
        )
    else:
        logger.info(
            "ai_query_completed",
            model=model,
            tool=tool,
            duration_seconds=round(duration, 3),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=round(cost, 6) if cost else None
        )


def log_business_event(event_type: str, **details):
    """
    Log a business-relevant event.

    Usage:
        log_business_event("customer_at_churn_risk", customer_id="123", churn_risk=0.85, ltv=5000)
    """
    logger = structlog.get_logger()
    logger.info("business_event", event_type=event_type, **details)


def log_security_event(event_type: str, severity: str = "info", **details):
    """
    Log a security-relevant event.

    Usage:
        log_security_event("api_key_invalid", severity="warning", ip="1.2.3.4")
    """
    logger = structlog.get_logger()

    log_func = getattr(logger, severity.lower(), logger.info)
    log_func("security_event", event_type=event_type, **details)


# ==================== Example Log Output ====================

"""
JSON Format (Production):
{
    "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "timestamp": "2025-10-28T10:30:45.123456Z",
    "level": "info",
    "event": "request_completed",
    "method": "POST",
    "path": "/api/mcp/query/natural-language",
    "client_ip": "192.168.1.100",
    "status_code": 200,
    "duration_seconds": 0.234
}

Console Format (Development):
2025-10-28 10:30:45 [info] request_completed correlation_id=a1b2c3d4... method=POST path=/api/mcp/query status_code=200 duration_seconds=0.234
"""
