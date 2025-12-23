"""
Redis Cache Manager for Multi-Axis Segmentation

Provides high-performance caching for:
- Discovered segments (24-hour TTL)
- Player profiles (1-hour TTL)
- Feature vectors (30-minute TTL)

Author: Quimbi Platform
Version: 4.0.0
Date: October 14, 2025
"""

import json
import pickle
import logging
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Async Redis cache manager with automatic fallback to no-cache mode.

    Features:
    - Automatic serialization (pickle for complex objects, JSON for simple data)
    - TTL-based expiration
    - Graceful degradation if Redis unavailable
    - Cache invalidation by pattern
    """

    def __init__(self, redis_url: Optional[str] = None, enabled: bool = True):
        """
        Initialize cache manager.

        Args:
            redis_url: Redis connection URL (e.g., "redis://localhost:6379/0")
            enabled: If False, cache is disabled (useful for testing)
        """
        self.enabled = enabled and REDIS_AVAILABLE
        self.redis_client: Optional[redis.Redis] = None
        self.redis_url = redis_url

        if not REDIS_AVAILABLE and enabled:
            logger.warning("redis.asyncio not available - caching disabled")
            self.enabled = False

        if self.enabled and redis_url:
            try:
                self.redis_client = redis.from_url(
                    redis_url,
                    encoding="utf-8",
                    decode_responses=False  # We handle encoding ourselves
                )
                logger.info(f"Redis cache initialized: {redis_url}")
            except Exception as e:
                logger.error(f"Failed to initialize Redis: {e}")
                self.enabled = False


    async def get(self, key: str, use_pickle: bool = True) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key
            use_pickle: If True, deserialize with pickle; if False, use JSON

        Returns:
            Cached value or None if not found/expired/error
        """
        if not self.enabled or not self.redis_client:
            return None

        try:
            value = await self.redis_client.get(key)

            if value is None:
                return None

            # Deserialize
            if use_pickle:
                return pickle.loads(value)
            else:
                return json.loads(value)

        except Exception as e:
            logger.warning(f"Cache get error for key '{key}': {e}")
            return None


    async def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None,
        use_pickle: bool = True
    ) -> bool:
        """
        Set value in cache with optional TTL.

        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Time-to-live in seconds (None = no expiration)
            use_pickle: If True, serialize with pickle; if False, use JSON

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled or not self.redis_client:
            return False

        try:
            # Serialize
            if use_pickle:
                serialized = pickle.dumps(value)
            else:
                serialized = json.dumps(value)

            # Store with optional TTL
            if ttl_seconds:
                await self.redis_client.setex(key, ttl_seconds, serialized)
            else:
                await self.redis_client.set(key, serialized)

            return True

        except Exception as e:
            logger.warning(f"Cache set error for key '{key}': {e}")
            return False


    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if not self.enabled or not self.redis_client:
            return False

        try:
            await self.redis_client.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Cache delete error for key '{key}': {e}")
            return False


    async def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching pattern.

        Args:
            pattern: Redis pattern (e.g., "multi_axis:segments:*")

        Returns:
            Number of keys deleted
        """
        if not self.enabled or not self.redis_client:
            return 0

        try:
            # Find matching keys
            keys = []
            async for key in self.redis_client.scan_iter(match=pattern):
                keys.append(key)

            # Delete in batch
            if keys:
                await self.redis_client.delete(*keys)
                logger.info(f"Deleted {len(keys)} keys matching pattern '{pattern}'")
                return len(keys)

            return 0

        except Exception as e:
            logger.warning(f"Cache delete_pattern error for pattern '{pattern}': {e}")
            return 0


    async def invalidate_segments(self, game_id: str) -> bool:
        """Invalidate cached segments for a game."""
        pattern = f"multi_axis:segments:{game_id}"
        deleted = await self.delete(pattern)
        logger.info(f"Invalidated segment cache for game '{game_id}'")
        return deleted


    async def invalidate_profile(self, player_id: str, game_id: str) -> bool:
        """Invalidate cached profile for a player."""
        key = f"multi_axis:profile:{player_id}:{game_id}"
        deleted = await self.delete(key)
        logger.info(f"Invalidated profile cache for player '{player_id}'")
        return deleted


    async def invalidate_all_profiles(self, game_id: str) -> int:
        """Invalidate all cached profiles for a game."""
        pattern = f"multi_axis:profile:*:{game_id}"
        count = await self.delete_pattern(pattern)
        logger.info(f"Invalidated {count} profile caches for game '{game_id}'")
        return count


    async def health_check(self) -> Dict[str, Any]:
        """
        Check cache health and return stats.

        Returns:
            Dict with status, connected, and optional stats
        """
        if not self.enabled:
            return {
                "status": "disabled",
                "connected": False,
                "reason": "Redis not available or disabled"
            }

        if not self.redis_client:
            return {
                "status": "error",
                "connected": False,
                "reason": "Redis client not initialized"
            }

        try:
            # Ping Redis
            await self.redis_client.ping()

            # Get info
            info = await self.redis_client.info()

            return {
                "status": "healthy",
                "connected": True,
                "redis_version": info.get("redis_version"),
                "used_memory_human": info.get("used_memory_human"),
                "connected_clients": info.get("connected_clients"),
                "total_commands_processed": info.get("total_commands_processed")
            }

        except Exception as e:
            return {
                "status": "error",
                "connected": False,
                "error": str(e)
            }


    async def close(self):
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Redis connection closed")


# Singleton instance (initialized in main.py)
cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> Optional[CacheManager]:
    """Get global cache manager instance."""
    return cache_manager


def init_cache_manager(redis_url: Optional[str] = None, enabled: bool = True) -> CacheManager:
    """
    Initialize global cache manager.

    Args:
        redis_url: Redis connection URL
        enabled: Enable caching

    Returns:
        CacheManager instance
    """
    global cache_manager
    cache_manager = CacheManager(redis_url=redis_url, enabled=enabled)
    return cache_manager
