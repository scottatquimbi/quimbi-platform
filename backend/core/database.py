"""
Database connection management for Unified Segmentation System

Provides async database session management with optimized connection pooling.

Pool Configuration:
- Production defaults: 20 connections + 10 overflow = 30 max concurrent
- Development defaults: 5 connections + 5 overflow = 10 max concurrent
- Pool pre-ping enabled for connection health checks
- Automatic connection recycling every 30 minutes
"""

import os
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text, event
import logging

logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://segmentation:password@localhost:5432/segmentation")

# Convert postgresql:// to postgresql+asyncpg://
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# Determine environment (production has higher defaults)
is_production = os.getenv("RAILWAY_ENVIRONMENT") is not None

# Connection pool configuration with production-optimized defaults
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "20" if is_production else "5"))
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "10" if is_production else "5"))
DB_POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))  # Reduced from 60 for faster failure detection
DB_POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "1800"))  # 30 minutes
DB_POOL_PRE_PING = os.getenv("DB_POOL_PRE_PING", "true").lower() == "true"
DB_ECHO = os.getenv("DB_ECHO", "false").lower() == "true"

# Log pool configuration
logger.info(
    f"Database pool configuration: size={DB_POOL_SIZE}, max_overflow={DB_MAX_OVERFLOW}, "
    f"timeout={DB_POOL_TIMEOUT}s, recycle={DB_POOL_RECYCLE}s, pre_ping={DB_POOL_PRE_PING}, "
    f"environment={'production' if is_production else 'development'}"
)

# Database engine with optimized pool settings
engine = create_async_engine(
    DATABASE_URL,
    pool_size=DB_POOL_SIZE,
    max_overflow=DB_MAX_OVERFLOW,
    pool_timeout=DB_POOL_TIMEOUT,
    pool_recycle=DB_POOL_RECYCLE,
    pool_pre_ping=DB_POOL_PRE_PING,  # Test connections before using (slight overhead but prevents stale connections)
    echo=DB_ECHO,
    # Performance optimizations
    connect_args={
        "server_settings": {
            "application_name": "ecommerce_intelligence_api",
        }
    }
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Base for declarative models
Base = declarative_base()


async def init_db():
    """Initialize database connection."""
    logger.info("Initializing database connection")
    async with engine.begin() as conn:
        # Test connection
        await conn.execute(text("SELECT 1"))
    logger.info("Database connection initialized successfully")


async def close_db():
    """Close database connection."""
    logger.info("Closing database connection")
    await engine.dispose()
    logger.info("Database connection closed")


@asynccontextmanager
async def get_db_session():
    """Get async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_db():
    """
    FastAPI dependency for database session.

    Usage:
        @router.get("/endpoint")
        async def endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_pool_status():
    """
    Get current database connection pool status.

    Returns:
        dict: Pool statistics including size, checked out connections, overflow, etc.
    """
    pool = engine.pool

    return {
        "pool_size": pool.size(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
        "queue_size": pool.size() + pool.overflow() - pool.checkedout(),
        "total_connections": pool.size() + pool.overflow(),
        "configuration": {
            "pool_size": DB_POOL_SIZE,
            "max_overflow": DB_MAX_OVERFLOW,
            "max_total": DB_POOL_SIZE + DB_MAX_OVERFLOW,
            "timeout": DB_POOL_TIMEOUT,
            "recycle": DB_POOL_RECYCLE,
            "pre_ping": DB_POOL_PRE_PING
        }
    }


async def get_pool_statistics():
    """
    Get detailed pool statistics with health check.

    Returns:
        dict: Comprehensive pool stats including health status
    """
    pool_status = get_pool_status()

    # Test connection health
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        health = "healthy"
        health_error = None
    except Exception as e:
        health = "unhealthy"
        health_error = str(e)
        logger.error(f"Database health check failed: {e}")

    pool_status["health"] = health
    if health_error:
        pool_status["health_error"] = health_error

    # Calculate utilization percentage
    if pool_status["total_connections"] > 0:
        pool_status["utilization_percent"] = round(
            (pool_status["checked_out"] / pool_status["total_connections"]) * 100, 2
        )
    else:
        pool_status["utilization_percent"] = 0.0

    return pool_status
