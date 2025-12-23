"""
Admin Endpoints Router

Provides administrative endpoints for system monitoring and management.
"""
import os
from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from backend.middleware.logging_config import get_logger
from backend.cache.redis_cache import cache, get_cache_stats
from backend.core.database import get_pool_statistics

logger = get_logger(__name__)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

# Router
router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    responses={404: {"description": "Not found"}},
)


@router.get("/sync-status")
async def sync_status():
    """
    Check sales sync scheduler status.

    Returns information about:
    - Whether scheduler is enabled
    - Next scheduled run time
    - Last sync status (if available)
    - Configuration
    """
    return {
        "scheduler_enabled": os.getenv("ENABLE_SALES_SYNC", "true").lower() == "true",
        "sync_hour_utc": int(os.getenv("SALES_SYNC_HOUR", "2")),
        "sync_on_startup": os.getenv("SYNC_ON_STARTUP", "false").lower() == "true",
        "azure_sql_configured": bool(os.getenv("AZURE_SQL_USERNAME")),
        "postgres_configured": bool(os.getenv("DATABASE_URL")),
        "note": "Check Railway logs for actual scheduler activity and sync results"
    }


@router.get("/cache/stats")
async def cache_stats():
    """
    Get Redis cache statistics.

    Returns:
    - Cache enabled status
    - Total keys in cache
    - Cache hit/miss counts
    - Hit rate percentage
    - Memory usage
    """
    try:
        stats = await get_cache_stats()
        return stats
    except Exception as e:
        logger.error("cache_stats_failed", error=str(e))
        return {
            "enabled": cache.enabled,
            "error": str(e)
        }


@router.get("/db/pool")
async def db_pool_stats():
    """
    Get database connection pool statistics.

    Returns:
    - Current pool size and utilization
    - Checked out connections
    - Overflow connections
    - Pool configuration
    - Health status
    """
    try:
        stats = await get_pool_statistics()
        return stats
    except Exception as e:
        logger.error("db_pool_stats_failed", error=str(e))
        return {
            "error": str(e)
        }


@router.post("/sync-sales")
@limiter.limit("10/hour")  # Very restrictive for admin endpoints
async def trigger_sales_sync(
    request: Request,
    mode: str = "dry-run",
    limit: Optional[int] = None,
    admin_key: str = ""
):
    """
    Manually trigger Azure SQL sales sync (async version).

    Args:
        mode: "dry-run", "incremental", or "full"
        limit: Optional row limit for testing
        admin_key: Admin authentication key

    Usage:
        POST /admin/sync-sales?mode=dry-run&limit=100&admin_key=YOUR_KEY
        POST /admin/sync-sales?mode=incremental&admin_key=YOUR_KEY
        POST /admin/sync-sales?mode=full&admin_key=YOUR_KEY
    """
    import asyncio

    # Check admin key
    expected_key = os.getenv("ADMIN_KEY")
    if not expected_key:
        raise HTTPException(status_code=500, detail="Server misconfiguration: ADMIN_KEY not set")

    if admin_key != expected_key:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Validate mode
    if mode not in ["dry-run", "incremental", "full"]:
        raise HTTPException(status_code=400, detail="Mode must be: dry-run, incremental, or full")

    # Build command
    cmd = ["python", "scripts/sync_combined_sales_simple.py"]

    # Add mode flag
    if mode == "full":
        cmd.append("--full")
    elif mode == "incremental":
        cmd.append("--incremental")
    elif mode == "dry-run":
        cmd.append("--dry-run")
        if limit:
            cmd.extend(["--limit", str(limit)])

    # Check if sync script exists
    import os.path
    if not os.path.exists("scripts/sync_combined_sales_simple.py"):
        raise HTTPException(
            status_code=503,
            detail="Sync script not found. Ensure scripts/ folder is included in deployment."
        )

    logger.info(f"Admin triggered sync: mode={mode}, limit={limit}, command={' '.join(cmd)}")

    try:
        # Run sync command asynchronously
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # Wait for completion (with timeout)
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=600.0  # 10 minute timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            raise HTTPException(
                status_code=504,
                detail="Sync operation timed out after 10 minutes"
            )

        # Check exit code
        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            logger.error(f"Sync failed: {error_msg}")
            raise HTTPException(
                status_code=500,
                detail=f"Sync failed with exit code {process.returncode}: {error_msg}"
            )

        # Parse output
        output = stdout.decode() if stdout else ""

        # Extract summary from output
        lines = output.strip().split("\n")
        summary = lines[-1] if lines else "Sync completed"

        return {
            "success": True,
            "mode": mode,
            "limit": limit,
            "summary": summary,
            "full_output": output
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Sync error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
