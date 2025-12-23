"""
Redis Caching Layer with Multi-Tenant Support

Provides:
- Customer profile caching (tenant-isolated)
- Archetype data caching (tenant-isolated)
- Query result caching (tenant-isolated)
- Cache invalidation strategies
- Automatic serialization/deserialization
- Automatic tenant namespacing

Configuration:
- REDIS_URL: Redis connection string (optional, defaults to localhost)
- CACHE_TTL: Default cache TTL in seconds (default: 3600 = 1 hour)
- ENABLE_CACHE: Enable/disable caching (default: true)

Multi-Tenant Isolation:
All cache keys are automatically prefixed with tenant:{tenant_id}:
to ensure complete data isolation between tenants.

Example cache keys:
- Single-tenant: customer:12345
- Multi-tenant: tenant:uuid-1234:customer:12345
"""

import redis.asyncio as redis
import json
import logging
from typing import Any, Dict, Optional, List
from datetime import timedelta
from uuid import UUID
import os
from functools import wraps
import hashlib

logger = logging.getLogger(__name__)

# ==================== Configuration ====================

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CACHE_TTL = int(os.getenv("CACHE_TTL", "3600"))  # 1 hour default
ENABLE_CACHE = os.getenv("ENABLE_CACHE", "true").lower() == "true"

# Cache key prefixes (will be prefixed with tenant: automatically)
PREFIX_CUSTOMER = "customer:"
PREFIX_ARCHETYPE = "archetype:"
PREFIX_CHURN = "churn:"
PREFIX_QUERY = "query:"
PREFIX_SEGMENT = "segment:"


def _get_tenant_key(base_key: str) -> str:
    """
    Prefix cache key with tenant ID from context.

    All cache operations should use this to ensure tenant isolation.

    Args:
        base_key: Base cache key (e.g., "customer:12345")

    Returns:
        Tenant-prefixed key (e.g., "tenant:uuid-1234:customer:12345")

    Raises:
        RuntimeError: If no tenant context is set

    Example:
        key = _get_tenant_key("customer:12345")
        # Returns: "tenant:abc-123:customer:12345"
    """
    from backend.middleware.tenant_context import get_current_tenant_id

    tenant_id = get_current_tenant_id()
    if not tenant_id:
        # For non-tenant contexts (admin, background tasks), use global namespace
        logger.warning(
            "cache_no_tenant_context",
            extra={"base_key": base_key}
        )
        return f"global:{base_key}"

    return f"tenant:{tenant_id}:{base_key}"

# ==================== Redis Client ====================

class RedisCache:
    """Redis cache client with automatic serialization."""

    def __init__(self, url: str = REDIS_URL):
        """Initialize Redis cache client."""
        self.url = url
        self.client: Optional[redis.Redis] = None
        self.enabled = ENABLE_CACHE

    async def connect(self):
        """Connect to Redis."""
        if not self.enabled:
            logger.info("cache_disabled", reason="ENABLE_CACHE=false")
            return

        try:
            self.client = await redis.from_url(
                self.url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # Test connection
            await self.client.ping()
            logger.info(f"Redis connected: {self.url}")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}, falling back to in-memory only")
            self.client = None
            self.enabled = False

    async def disconnect(self):
        """Disconnect from Redis."""
        if self.client:
            await self.client.close()
            logger.info("Redis disconnected")

    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value (deserialized from JSON) or None if not found
        """
        if not self.enabled or not self.client:
            return None

        try:
            value = await self.client.get(key)
            if value:
                # Track cache hit
                from backend.middleware.logging_config import get_logger
                cache_logger = get_logger("cache")
                cache_logger.debug("cache_hit", key=key)

                # Track metrics if enabled
                try:
                    from backend.middleware.metrics import track_cache_access
                    track_cache_access("redis", hit=True)
                except:
                    pass

                return json.loads(value)
            else:
                # Track cache miss
                try:
                    from backend.middleware.metrics import track_cache_access
                    track_cache_access("redis", hit=False)
                except:
                    pass

                return None
        except Exception as e:
            logger.error("cache_get_failed", key=key, error=str(e))
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache (will be serialized to JSON)
            ttl: Time-to-live in seconds (default: CACHE_TTL)

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled or not self.client:
            return False

        try:
            serialized = json.dumps(value)
            ttl = ttl or CACHE_TTL

            await self.client.setex(
                key,
                timedelta(seconds=ttl),
                serialized
            )

            logger.debug("cache_set", key=key, ttl=ttl)
            return True
        except Exception as e:
            logger.error("cache_set_failed", key=key, error=str(e))
            return False

    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if not self.enabled or not self.client:
            return False

        try:
            await self.client.delete(key)
            logger.debug("cache_deleted", key=key)
            return True
        except Exception as e:
            logger.error("cache_delete_failed", key=key, error=str(e))
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching pattern.

        Args:
            pattern: Key pattern (e.g., "customer:*")

        Returns:
            Number of keys deleted
        """
        if not self.enabled or not self.client:
            return 0

        try:
            keys = []
            async for key in self.client.scan_iter(match=pattern):
                keys.append(key)

            if keys:
                deleted = await self.client.delete(*keys)
                logger.info("cache_pattern_deleted", pattern=pattern, count=deleted)
                return deleted
            return 0
        except Exception as e:
            logger.error("cache_pattern_delete_failed", pattern=pattern, error=str(e))
            return 0

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        if not self.enabled or not self.client:
            return False

        try:
            return await self.client.exists(key) > 0
        except Exception as e:
            logger.error("cache_exists_failed", key=key, error=str(e))
            return False

    async def clear_all(self) -> bool:
        """Clear all cache (use with caution!)."""
        if not self.enabled or not self.client:
            return False

        try:
            await self.client.flushdb()
            logger.warning("cache_cleared_all")
            return True
        except Exception as e:
            logger.error("cache_clear_failed", error=str(e))
            return False


# ==================== Global Cache Instance ====================

cache = RedisCache()


# ==================== Cache Decorators ====================

def cached(
    key_prefix: str,
    ttl: Optional[int] = None,
    key_builder: Optional[callable] = None
):
    """
    Decorator to cache function results.

    Args:
        key_prefix: Prefix for cache key
        ttl: Time-to-live in seconds
        key_builder: Function to build cache key from arguments

    Usage:
        @cached("customer", ttl=3600)
        async def get_customer(customer_id: str):
            ...

        @cached("query", key_builder=lambda q: hashlib.md5(q.encode()).hexdigest())
        async def process_query(query: str):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Build cache key
            if key_builder:
                key_suffix = key_builder(*args, **kwargs)
            else:
                # Use first argument as key
                key_suffix = str(args[0]) if args else "default"

            cache_key = f"{key_prefix}:{key_suffix}"

            # Try to get from cache
            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Execute function
            result = await func(*args, **kwargs)

            # Cache result
            await cache.set(cache_key, result, ttl=ttl)

            return result

        return wrapper
    return decorator


# ==================== Helper Functions (Tenant-Aware) ====================

async def cache_customer(customer_id: str, data: Dict[str, Any], ttl: int = CACHE_TTL):
    """
    Cache customer data with automatic tenant isolation.

    Args:
        customer_id: Customer identifier
        data: Customer data to cache
        ttl: Time-to-live in seconds

    Example:
        await cache_customer("12345", {"name": "John", "ltv": 1000})
        # Cached as: tenant:{uuid}:customer:12345
    """
    base_key = f"{PREFIX_CUSTOMER}{customer_id}"
    tenant_key = _get_tenant_key(base_key)
    await cache.set(tenant_key, data, ttl=ttl)


async def get_cached_customer(customer_id: str) -> Optional[Dict[str, Any]]:
    """
    Get cached customer data with automatic tenant isolation.

    Args:
        customer_id: Customer identifier

    Returns:
        Cached customer data if found and belongs to current tenant, None otherwise

    Example:
        customer = await get_cached_customer("12345")
        if customer:
            print(customer["name"])
    """
    base_key = f"{PREFIX_CUSTOMER}{customer_id}"
    tenant_key = _get_tenant_key(base_key)
    return await cache.get(tenant_key)


async def invalidate_customer(customer_id: str):
    """
    Invalidate customer cache with automatic tenant isolation.

    Args:
        customer_id: Customer identifier
    """
    base_key = f"{PREFIX_CUSTOMER}{customer_id}"
    tenant_key = _get_tenant_key(base_key)
    await cache.delete(tenant_key)


async def cache_archetype(archetype_id: str, data: Dict[str, Any], ttl: int = CACHE_TTL):
    """
    Cache archetype data with automatic tenant isolation.

    Args:
        archetype_id: Archetype identifier
        data: Archetype data to cache
        ttl: Time-to-live in seconds
    """
    base_key = f"{PREFIX_ARCHETYPE}{archetype_id}"
    tenant_key = _get_tenant_key(base_key)
    await cache.set(tenant_key, data, ttl=ttl)


async def get_cached_archetype(archetype_id: str) -> Optional[Dict[str, Any]]:
    """Get cached archetype data with automatic tenant isolation."""
    base_key = f"{PREFIX_ARCHETYPE}{archetype_id}"
    tenant_key = _get_tenant_key(base_key)
    return await cache.get(tenant_key)


async def cache_churn_prediction(customer_id: str, prediction: Dict[str, Any], ttl: int = 1800):
    """Cache churn prediction (30 min default) with automatic tenant isolation."""
    base_key = f"{PREFIX_CHURN}{customer_id}"
    tenant_key = _get_tenant_key(base_key)
    await cache.set(tenant_key, prediction, ttl=ttl)


async def get_cached_churn_prediction(customer_id: str) -> Optional[Dict[str, Any]]:
    """Get cached churn prediction with automatic tenant isolation."""
    base_key = f"{PREFIX_CHURN}{customer_id}"
    tenant_key = _get_tenant_key(base_key)
    return await cache.get(tenant_key)


async def cache_query_result(query_hash: str, result: Any, ttl: int = 600):
    """
    Cache query result (10 min default) with automatic tenant isolation.

    Args:
        query_hash: MD5 hash of query
        result: Query result
        ttl: Time-to-live
    """
    base_key = f"{PREFIX_QUERY}{query_hash}"
    tenant_key = _get_tenant_key(base_key)
    await cache.set(tenant_key, result, ttl=ttl)


async def get_cached_query_result(query_hash: str) -> Optional[Any]:
    """Get cached query result with automatic tenant isolation."""
    base_key = f"{PREFIX_QUERY}{query_hash}"
    tenant_key = _get_tenant_key(base_key)
    return await cache.get(tenant_key)


def hash_query(query: str) -> str:
    """Create MD5 hash of query for cache key."""
    return hashlib.md5(query.encode(), usedforsecurity=False).hexdigest()


async def invalidate_all_customers():
    """
    Invalidate all customer caches for current tenant.

    Only deletes cache keys for the current tenant to maintain isolation.
    """
    from backend.middleware.tenant_context import get_current_tenant_id

    tenant_id = get_current_tenant_id()
    if tenant_id:
        pattern = f"tenant:{tenant_id}:{PREFIX_CUSTOMER}*"
    else:
        pattern = f"global:{PREFIX_CUSTOMER}*"

    await cache.delete_pattern(pattern)


async def invalidate_all_archetypes():
    """
    Invalidate all archetype caches for current tenant.

    Only deletes cache keys for the current tenant to maintain isolation.
    """
    from backend.middleware.tenant_context import get_current_tenant_id

    tenant_id = get_current_tenant_id()
    if tenant_id:
        pattern = f"tenant:{tenant_id}:{PREFIX_ARCHETYPE}*"
    else:
        pattern = f"global:{PREFIX_ARCHETYPE}*"

    await cache.delete_pattern(pattern)


async def invalidate_all_queries():
    """
    Invalidate all query result caches for current tenant.

    Only deletes cache keys for the current tenant to maintain isolation.
    """
    from backend.middleware.tenant_context import get_current_tenant_id

    tenant_id = get_current_tenant_id()
    if tenant_id:
        pattern = f"tenant:{tenant_id}:{PREFIX_QUERY}*"
    else:
        pattern = f"global:{PREFIX_QUERY}*"

    await cache.delete_pattern(pattern)


async def invalidate_tenant_cache(tenant_id: str):
    """
    Invalidate ALL cache for a specific tenant.

    Use with caution - clears all cached data for the tenant.

    Args:
        tenant_id: Tenant UUID to invalidate

    Example:
        # Clear all cache when tenant data is reimported
        await invalidate_tenant_cache(tenant.id)
    """
    pattern = f"tenant:{tenant_id}:*"
    deleted = await cache.delete_pattern(pattern)
    logger.info(f"Invalidated {deleted} cache keys for tenant {tenant_id}")


# ==================== Cache Statistics ====================

async def get_cache_stats() -> Dict[str, Any]:
    """
    Get cache statistics.

    Returns:
        Dict with cache info (keys count, memory usage, hit rate)
    """
    if not cache.enabled or not cache.client:
        return {
            "enabled": False,
            "reason": "Cache disabled or not connected"
        }

    try:
        info = await cache.client.info("stats")
        keyspace = await cache.client.info("keyspace")

        # Calculate total keys
        total_keys = 0
        if "db0" in keyspace:
            db_info = keyspace["db0"]
            total_keys = db_info.get("keys", 0)

        return {
            "enabled": True,
            "total_keys": total_keys,
            "hits": info.get("keyspace_hits", 0),
            "misses": info.get("keyspace_misses", 0),
            "hit_rate": round(
                info.get("keyspace_hits", 0) /
                (info.get("keyspace_hits", 0) + info.get("keyspace_misses", 1)) * 100,
                2
            ),
            "memory_used_mb": round(info.get("used_memory", 0) / 1024 / 1024, 2)
        }
    except Exception as e:
        logger.error("cache_stats_failed", error=str(e))
        return {"enabled": True, "error": str(e)}


# ==================== Example Usage ====================

"""
# In startup:
await cache.connect()

# Cache customer data:
await cache_customer("5971333382399", customer_data)

# Get cached customer:
customer = await get_cached_customer("5971333382399")
if customer:
    return customer  # Cache hit
else:
    # Cache miss, fetch from DB
    customer = fetch_from_db("5971333382399")
    await cache_customer("5971333382399", customer)
    return customer

# Invalidate when data changes:
await invalidate_customer("5971333382399")

# Using decorator:
@cached("customer", ttl=3600)
async def get_customer_profile(customer_id: str):
    return fetch_from_db(customer_id)

# Shutdown:
await cache.disconnect()
"""
