"""
API Dependencies

Shared dependencies for FastAPI endpoints including authentication.
"""
import os
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

from backend.middleware.logging_config import get_logger

logger = get_logger(__name__)

# API Key header scheme
api_key_header_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(api_key: Optional[str] = Depends(api_key_header_scheme)):
    """
    Dependency that requires valid API key authentication.

    For MVP/development: Checks against ADMIN_KEY environment variable.
    For production: Should be replaced with database-backed API key system.

    Usage:
        @router.get("/protected", dependencies=[Depends(require_api_key)])
        async def protected_endpoint():
            return {"message": "Authenticated!"}

    Args:
        api_key: API key from X-API-Key header

    Raises:
        HTTPException: 401 if missing or invalid API key
    """
    # Get expected API key from environment
    expected_key = os.getenv("ADMIN_KEY") or os.getenv("API_KEY")

    if not expected_key:
        # No API key configured - log warning but allow (for backward compatibility)
        logger.warning("no_api_key_configured",
                      message="ADMIN_KEY not set - authentication disabled")
        return None

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Provide X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if api_key != expected_key:
        logger.warning("invalid_api_key_attempted",
                      key_prefix=api_key[:10] if api_key else "")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    logger.debug("api_key_validated")
    return {"authenticated": True}


async def optional_api_key(api_key: Optional[str] = Depends(api_key_header_scheme)):
    """
    Dependency for optional API key authentication.

    Allows unauthenticated access but validates if key is provided.
    Useful for endpoints that have different behavior for authenticated users.

    Args:
        api_key: API key from X-API-Key header (optional)

    Returns:
        dict with authentication status
    """
    if not api_key:
        return {"authenticated": False}

    expected_key = os.getenv("ADMIN_KEY") or os.getenv("API_KEY")

    if not expected_key:
        return {"authenticated": False}

    if api_key == expected_key:
        return {"authenticated": True}

    # Invalid key provided
    logger.warning("invalid_api_key_provided", key_prefix=api_key[:10])
    return {"authenticated": False, "error": "invalid_key"}
