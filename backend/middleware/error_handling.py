"""
Standardized Error Handling

Provides:
- Custom exception classes for different error types
- Consistent error response format
- Correlation ID tracking in errors
- Appropriate HTTP status codes
"""

from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import structlog
from typing import Any, Dict, Optional
import traceback

logger = structlog.get_logger(__name__)

# ==================== Custom Exceptions ====================

class APIError(Exception):
    """Base class for API errors."""
    def __init__(
        self,
        message: str,
        error_code: str = None,
        status_code: int = 500,
        details: Dict[str, Any] = None
    ):
        self.message = message
        self.error_code = error_code or "INTERNAL_ERROR"
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(APIError):
    """Input validation error (400)."""
    def __init__(self, message: str, field: str = None, **kwargs):
        details = {"field": field} if field else {}
        details.update(kwargs)
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=400,
            details=details
        )


class AuthenticationError(APIError):
    """Authentication failed (401)."""
    def __init__(self, message: str = "Authentication required", **kwargs):
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_ERROR",
            status_code=401,
            details=kwargs
        )


class AuthorizationError(APIError):
    """Authorization failed (403)."""
    def __init__(self, message: str = "Access denied", **kwargs):
        super().__init__(
            message=message,
            error_code="AUTHORIZATION_ERROR",
            status_code=403,
            details=kwargs
        )


class NotFoundError(APIError):
    """Resource not found (404)."""
    def __init__(self, resource: str, identifier: str = None, **kwargs):
        message = f"{resource} not found"
        if identifier:
            message += f": {identifier}"

        details = {"resource": resource}
        if identifier:
            details["identifier"] = identifier
        details.update(kwargs)

        super().__init__(
            message=message,
            error_code="NOT_FOUND",
            status_code=404,
            details=details
        )


class ConflictError(APIError):
    """Resource conflict (409)."""
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_code="CONFLICT",
            status_code=409,
            details=kwargs
        )


class RateLimitError(APIError):
    """Rate limit exceeded (429)."""
    def __init__(self, limit: str, retry_after: int = None, **kwargs):
        message = f"Rate limit exceeded: {limit}"
        details = {"limit": limit}
        if retry_after:
            details["retry_after_seconds"] = retry_after
        details.update(kwargs)

        super().__init__(
            message=message,
            error_code="RATE_LIMIT_EXCEEDED",
            status_code=429,
            details=details
        )


class ExternalServiceError(APIError):
    """External service error (502)."""
    def __init__(self, service: str, operation: str = None, **kwargs):
        message = f"External service error: {service}"
        if operation:
            message += f" ({operation})"

        details = {"service": service}
        if operation:
            details["operation"] = operation
        details.update(kwargs)

        super().__init__(
            message=message,
            error_code="EXTERNAL_SERVICE_ERROR",
            status_code=502,
            details=details
        )


class ServiceUnavailableError(APIError):
    """Service temporarily unavailable (503)."""
    def __init__(self, message: str = "Service temporarily unavailable", retry_after: int = None, **kwargs):
        details = kwargs.copy()
        if retry_after:
            details["retry_after_seconds"] = retry_after

        super().__init__(
            message=message,
            error_code="SERVICE_UNAVAILABLE",
            status_code=503,
            details=details
        )


# ==================== Error Response Format ====================

def create_error_response(
    error: Exception,
    correlation_id: str = None,
    include_traceback: bool = False
) -> Dict[str, Any]:
    """
    Create standardized error response.

    Format:
    {
        "error": {
            "code": "ERROR_CODE",
            "message": "Human-readable message",
            "details": {...},
            "correlation_id": "uuid"
        },
        "timestamp": "2025-10-28T10:30:45Z"
    }
    """
    from datetime import datetime

    # Determine error attributes
    if isinstance(error, APIError):
        error_code = error.error_code
        message = error.message
        details = error.details
        status_code = error.status_code
    elif isinstance(error, StarletteHTTPException):
        error_code = "HTTP_ERROR"
        message = error.detail
        details = {}
        status_code = error.status_code
    else:
        error_code = "INTERNAL_ERROR"
        message = str(error) if str(error) else "An unexpected error occurred"
        details = {"error_type": type(error).__name__}
        status_code = 500

    # Build response
    response = {
        "error": {
            "code": error_code,
            "message": message,
            "details": details
        },
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

    # Add correlation ID if available
    if correlation_id:
        response["error"]["correlation_id"] = correlation_id

    # Add traceback in development (not production)
    if include_traceback and status_code >= 500:
        response["error"]["traceback"] = traceback.format_exc()

    return response, status_code


# ==================== Exception Handlers ====================

async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """Handle custom API errors."""
    # Get correlation ID from request state if available
    correlation_id = getattr(request.state, "correlation_id", None)
    if not correlation_id:
        try:
            from structlog.contextvars import get_contextvars
            context = get_contextvars()
            correlation_id = context.get("correlation_id")
        except:
            correlation_id = None

    # Log error
    logger.error(
        "api_error",
        error_code=exc.error_code,
        error_message=exc.message,
        status_code=exc.status_code,
        details=exc.details
    )

    # Send Slack alert for 5xx errors
    if exc.status_code >= 500:
        try:
            from backend.middleware.slack_alerts import send_error_alert
            await send_error_alert(
                error_type=exc.error_code,
                error_message=exc.message,
                correlation_id=correlation_id,
                endpoint=str(request.url.path)
            )
        except Exception as e:
            logger.warning("failed_to_send_slack_alert", error=str(e))

    # Create response
    response_data, status_code = create_error_response(
        exc,
        correlation_id=correlation_id,
        include_traceback=False
    )

    return JSONResponse(
        status_code=status_code,
        content=response_data
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handle standard HTTP exceptions."""
    correlation_id = getattr(request.state, "correlation_id", None)

    logger.warning(
        "http_exception",
        status_code=exc.status_code,
        detail=exc.detail,
        path=request.url.path
    )

    response_data, status_code = create_error_response(
        exc,
        correlation_id=correlation_id
    )

    return JSONResponse(
        status_code=status_code,
        content=response_data
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle request validation errors (422)."""
    correlation_id = getattr(request.state, "correlation_id", None)

    # Extract validation errors
    validation_errors = []
    for error in exc.errors():
        validation_errors.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })

    logger.warning(
        "validation_error",
        path=request.url.path,
        errors=validation_errors
    )

    response_data = {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "details": {
                "validation_errors": validation_errors
            }
        },
        "timestamp": __import__('datetime').datetime.utcnow().isoformat() + "Z"
    }

    if correlation_id:
        response_data["error"]["correlation_id"] = correlation_id

    return JSONResponse(
        status_code=422,
        content=response_data
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions (500)."""
    correlation_id = getattr(request.state, "correlation_id", None)

    # Log with full traceback
    logger.error(
        "unexpected_error",
        error_type=type(exc).__name__,
        error_message=str(exc),
        path=request.url.path,
        exc_info=True
    )

    # Send Slack alert for unexpected errors
    try:
        from backend.middleware.slack_alerts import send_error_alert
        await send_error_alert(
            error_type=type(exc).__name__,
            error_message=str(exc),
            correlation_id=correlation_id,
            endpoint=str(request.url.path)
        )
    except Exception as e:
        logger.warning("failed_to_send_slack_alert", error=str(e))

    # Don't expose internal details to client
    response_data = {
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred. Please try again later.",
            "details": {}
        },
        "timestamp": __import__('datetime').datetime.utcnow().isoformat() + "Z"
    }

    if correlation_id:
        response_data["error"]["correlation_id"] = correlation_id
        # Include correlation ID in message for support
        response_data["error"]["message"] += f" Reference: {correlation_id}"

    return JSONResponse(
        status_code=500,
        content=response_data
    )


# ==================== Helper Functions ====================

def raise_not_found(resource: str, identifier: str = None):
    """Convenience function to raise NotFoundError."""
    raise NotFoundError(resource=resource, identifier=identifier)


def raise_validation_error(message: str, field: str = None, **kwargs):
    """Convenience function to raise ValidationError."""
    raise ValidationError(message=message, field=field, **kwargs)


def raise_authentication_error(message: str = None):
    """Convenience function to raise AuthenticationError."""
    raise AuthenticationError(message=message or "Authentication required")


def raise_authorization_error(message: str = None):
    """Convenience function to raise AuthorizationError."""
    raise AuthorizationError(message=message or "Access denied")


# ==================== Example Usage ====================

"""
# In your endpoint:

from backend.middleware.error_handling import NotFoundError, ValidationError

@app.get("/customers/{customer_id}")
async def get_customer(customer_id: str):
    customer = data_store.customers.get(customer_id)

    if not customer:
        raise NotFoundError(resource="Customer", identifier=customer_id)

    return customer


@app.post("/query")
async def query(query: str):
    if len(query) < 3:
        raise ValidationError(
            message="Query must be at least 3 characters",
            field="query",
            min_length=3,
            actual_length=len(query)
        )

    # Process query...


# Error response format:
{
    "error": {
        "code": "NOT_FOUND",
        "message": "Customer not found: 12345",
        "details": {
            "resource": "Customer",
            "identifier": "12345"
        },
        "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    },
    "timestamp": "2025-10-28T10:30:45.123456Z"
}
"""
