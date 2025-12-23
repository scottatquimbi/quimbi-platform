"""
Railway PostgreSQL test fixtures.

This file provides fixtures for testing against the Railway production database.
Use with caution - tests will interact with real data.

Usage:
    pytest tests/ --conftest=tests/conftest_railway.py
"""
import os
import pytest
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

from backend.core.pii_tokenization import PIITokenizationService
from backend.api.auth import APIKeyManager
from backend.core.multi_axis_clustering_engine import MultiAxisClusteringEngine
from backend.models.behavioral_models import PlayerEvent


# Railway database URL
RAILWAY_DATABASE_URL = "postgresql+asyncpg://postgres:CCPbURisCkvxKMZVkuzOlQpsKJTRYBpQ@caboose.proxy.rlwy.net:52901/railway"


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def railway_engine():
    """
    Create Railway PostgreSQL engine.

    Uses NullPool to avoid connection pool issues with production database.
    """
    engine = create_async_engine(
        RAILWAY_DATABASE_URL,
        poolclass=NullPool,  # No connection pooling for tests
        echo=False
    )

    yield engine

    await engine.dispose()


@pytest.fixture
async def railway_session(railway_engine):
    """
    Create Railway database session.

    Note: This connects to PRODUCTION database.
    Tests should clean up after themselves.
    """
    async_session = async_sessionmaker(
        railway_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with async_session() as session:
        # Start transaction
        async with session.begin():
            yield session
            # Rollback all changes after test
            await session.rollback()


@pytest.fixture
def pii_service():
    """Provide PII tokenization service"""
    return PIITokenizationService()


@pytest.fixture
def api_key_manager():
    """Provide API key manager"""
    return APIKeyManager()


@pytest.fixture
async def clustering_engine():
    """Provide multi-axis clustering engine"""
    return MultiAxisClusteringEngine()


# Sample data for testing (read-only)
@pytest.fixture
def sample_player_ids():
    """Sample player IDs for testing (won't be stored in prod DB)"""
    return [
        f"railway_test_{i}@example.com"
        for i in range(1, 11)
    ]


# Assertion helpers
def assert_fuzzy_memberships_valid(memberships: dict):
    """Assert fuzzy membership values are valid"""
    total = sum(memberships.values())
    assert abs(total - 1.0) < 0.01, f"Memberships should sum to 1.0, got {total}"

    for segment, membership in memberships.items():
        assert 0.0 <= membership <= 1.0, \
            f"Membership for {segment} must be in [0,1], got {membership}"


def assert_token_format_valid(token: str):
    """Assert PII token format is valid"""
    assert token.startswith("tok_"), "Token should start with 'tok_'"
    assert len(token) > 20, "Token should be at least 20 chars"
    assert token.replace("tok_", "").replace("-", "").replace("_", "").isalnum(), \
        "Token should only contain alphanumeric, dash, and underscore"


def assert_api_key_format_valid(api_key: str):
    """Assert API key format is valid"""
    assert api_key.startswith("sk_live_"), "API key should start with 'sk_live_'"
    assert len(api_key) == 56, f"API key should be 56 chars, got {len(api_key)}"
