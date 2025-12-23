"""
Customer Profile Endpoint Alias

Provides `/api/customers/{id}` endpoint as an alias to `/api/mcp/customer/{id}`.
This maintains backward compatibility with frontend expecting `/api/customers` path.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional

# Import MCP server
from mcp_server.segmentation_server import handle_mcp_call

# Import caching
from backend.cache.redis_cache import get_cached_customer, cache_customer

# Import authentication
from backend.api.dependencies import require_api_key

# Import logging
from backend.middleware.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/customers",
    tags=["customers"],
    dependencies=[Depends(require_api_key)],
    responses={404: {"description": "Customer not found"}},
)


@router.get("/{customer_id}")
async def get_customer(customer_id: str):
    """
    Get customer behavioral profile with Redis caching.

    Returns customer intelligence including:
    - Archetype and behavioral segments
    - Business metrics (LTV, total orders, AOV)
    - Churn risk assessment
    - Segment memberships and fuzzy scores

    This is an alias for `/api/mcp/customer/{customer_id}` to support
    frontend compatibility.
    """
    try:
        # Try cache first
        cached_result = await get_cached_customer(customer_id)
        if cached_result:
            logger.debug("cache_hit", resource="customer_profile", customer_id=customer_id)
            return cached_result

        # Cache miss - fetch from data store
        logger.debug("cache_miss", resource="customer_profile", customer_id=customer_id)
        result = handle_mcp_call("get_customer_profile", {"customer_id": customer_id})

        # Cache the result (1 hour TTL)
        await cache_customer(customer_id, result, ttl=3600)

        return result
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")
    except Exception as e:
        logger.error(f"Failed to get customer profile: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
