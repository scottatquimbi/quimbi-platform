"""
Health Check Endpoints Router

Provides health check endpoints for monitoring and load balancers.
"""
from datetime import datetime
from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from backend.middleware.logging_config import get_logger
from backend.core.database import engine

logger = get_logger(__name__)

# Import data_store for checking data loaded status
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from mcp_server.segmentation_server import data_store

# Import metrics endpoint if enabled
try:
    from backend.middleware.metrics import metrics_endpoint, METRICS_ENABLED
except ImportError:
    METRICS_ENABLED = False

# Router
router = APIRouter(
    tags=["health"],
    responses={404: {"description": "Not found"}},
)


@router.get("/health")
async def health_check():
    """
    Basic health check endpoint.

    Returns 200 if service is running.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/health/ready")
async def readiness_probe():
    """
    Kubernetes readiness probe.

    Checks:
    - Database connectivity
    - Data loaded status

    Returns 200 if ready to serve traffic, 503 if not ready.
    """
    # Check database connection
    database_healthy = False
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        database_healthy = True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")

    # Check if customer data is loaded
    data_loaded = data_store.loaded and len(data_store.customers) > 0
    customer_count = len(data_store.customers)

    # Service is ready if database is healthy AND data is loaded
    if database_healthy and data_loaded:
        return {
            "status": "ready",
            "database": "healthy",
            "data_loaded": True,
            "customers": customer_count,
            "timestamp": datetime.utcnow().isoformat()
        }
    else:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "not_ready",
                "database_healthy": database_healthy,
                "data_loaded": data_loaded,
                "customers": customer_count,
                "timestamp": datetime.utcnow().isoformat()
            }
        )


@router.get("/health/live")
async def liveness_probe():
    """Kubernetes liveness probe."""
    return {"status": "alive"}


@router.get("/metrics")
async def prometheus_metrics():
    """
    Prometheus metrics endpoint (optional - only if ENABLE_PROMETHEUS_METRICS=true).

    Returns application metrics in Prometheus exposition format.
    """
    if not METRICS_ENABLED:
        raise HTTPException(
            status_code=404,
            detail="Metrics disabled. Set ENABLE_PROMETHEUS_METRICS=true to enable."
        )
    return await metrics_endpoint()
