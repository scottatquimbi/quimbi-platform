"""
Pytest Configuration and Fixtures

Shared fixtures for all tests:
- Database sessions
- Mock data generators
- Test utilities

Author: Quimbi Platform
Date: October 14, 2025
"""

import pytest
import pytest_asyncio
import asyncio
from typing import AsyncGenerator, Dict, List, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import text
import numpy as np

# from backend.core.pii_tokenization import PIITokenizationService  # Not needed for security tests
# from backend.api.auth import APIKeyManager  # Import conditionally
from backend.core.multi_axis_clustering_engine import DiscoveredSegment


# Configure event loop for async tests
@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


# Configure pytest-asyncio
@pytest.fixture(scope="session")
def event_loop_policy():
    """Use the default event loop policy"""
    return asyncio.DefaultEventLoopPolicy()


# Database fixtures

@pytest_asyncio.fixture
async def test_db_engine():
    """Create test database engine (in-memory SQLite for speed)"""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False
    )

    # Create tables once
    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS pii_token_vault (
                id TEXT PRIMARY KEY,
                token TEXT UNIQUE NOT NULL,
                encrypted_pii BLOB,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                access_count INTEGER DEFAULT 0,
                last_accessed_at TIMESTAMP,
                deleted_at TIMESTAMP,
                deletion_reason TEXT
            )
        """))

        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS pii_access_audit (
                id TEXT PRIMARY KEY,
                token TEXT NOT NULL,
                accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                access_reason TEXT NOT NULL,
                service TEXT NOT NULL,
                user_id TEXT,
                ip_address TEXT
            )
        """))

        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_hash TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                scopes TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                last_used_at TIMESTAMP,
                usage_count INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                revoked_at TIMESTAMP,
                revocation_reason TEXT,
                rate_limit_per_hour INTEGER DEFAULT 1000,
                rate_limit_remaining INTEGER DEFAULT 1000,
                rate_limit_reset_at TIMESTAMP
            )
        """))

    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_db_engine):
    """
    Provide clean database session for each test.

    Automatically rolls back after each test.
    """
    async_session = async_sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with async_session() as session:
        yield session
        await session.rollback()


# Service fixtures

@pytest.fixture
def pii_service():
    """Provide PII tokenization service"""
    try:
        from backend.core.pii_tokenization import PIITokenizationService
        return PIITokenizationService()
    except ImportError:
        pytest.skip("PII tokenization service not available")


@pytest.fixture
def api_key_manager():
    """Provide API key manager"""
    try:
        from backend.api.auth import APIKeyManager
        return APIKeyManager()
    except ImportError:
        pytest.skip("API key manager not available")


@pytest.fixture
def client():
    """Provide FastAPI test client (for sync tests only)"""
    from fastapi.testclient import TestClient
    from backend.main import app

    return TestClient(app)


@pytest_asyncio.fixture
async def async_client():
    """Provide async FastAPI test client"""
    from httpx import AsyncClient
    from backend.main import app

    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def valid_api_key(api_key_manager, test_db_engine):
    """Create and return a valid API key for testing"""
    async_session = async_sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with async_session() as session:
        plain_key, _ = await api_key_manager.create_api_key(
            session,
            name="Test API Key",
            scopes=["read", "write"],
            expires_days=365
        )
        await session.commit()
        return plain_key


# Mock data generators

@pytest.fixture
def mock_player_events() -> List[Dict[str, Any]]:
    """Generate mock player events for testing"""
    base_time = datetime.utcnow() - timedelta(days=30)

    events = []
    for i in range(100):
        events.append({
            'player_id': 'test_player_001',
            'event_type': np.random.choice([
                'level_complete', 'item_purchase', 'combat_victory',
                'quest_start', 'achievement_unlock'
            ]),
            'timestamp': base_time + timedelta(hours=i),
            'properties': {
                'level': np.random.randint(1, 50),
                'score': np.random.randint(100, 1000)
            }
        })

    return events


@pytest.fixture
def mock_segments() -> List[DiscoveredSegment]:
    """Generate mock discovered segments for testing"""
    segments = []

    # Create 3 mock segments for temporal_patterns axis
    for i, (name, interpretation) in enumerate([
        ('weekend_warrior', 'Plays primarily on weekends'),
        ('weekday_regular', 'Consistent weekday engagement'),
        ('daily_player', 'Plays every day')
    ]):
        segment = DiscoveredSegment(
            segment_id=f"test_game_temporal_{name}",
            axis_name="temporal_patterns",
            segment_name=name,
            cluster_center=np.array([float(i), float(i*2)]),  # Mock scaled centers
            feature_names=['weekend_ratio', 'session_consistency'],
            scaler_params={
                'mean': [0.5, 0.5],
                'scale': [0.2, 0.3],
                'feature_names': ['weekend_ratio', 'session_consistency']
            },
            population_percentage=1.0 / 3,
            player_count=100,
            interpretation=interpretation
        )
        segments.append(segment)

    return segments


@pytest.fixture
def mock_player_features() -> Dict[str, float]:
    """Generate mock player features"""
    return {
        'weekend_ratio': 0.7,
        'session_consistency': 0.8,
        'avg_session_length': 45.0,
        'total_sessions': 25
    }


# Utility fixtures

@pytest.fixture
def sample_player_ids() -> List[str]:
    """Sample player IDs for testing"""
    return [
        f"player_{i:03d}@example.com"
        for i in range(1, 11)
    ]


@pytest.fixture
def sample_game_ids() -> List[str]:
    """Sample game IDs for testing"""
    return [
        "mass_effect_3",
        "dragon_age_origins",
        "test_game_001"
    ]


# Assertion helpers

def assert_fuzzy_memberships_valid(memberships: Dict[str, float]):
    """Assert fuzzy memberships are valid (sum to 1.0, all 0-1)"""
    total = sum(memberships.values())
    assert abs(total - 1.0) < 0.001, f"Memberships should sum to 1.0, got {total}"

    for segment, strength in memberships.items():
        assert 0.0 <= strength <= 1.0, f"Membership for {segment} should be 0-1, got {strength}"


def assert_token_format_valid(token: str):
    """Assert token has correct format"""
    assert token.startswith("tok_"), f"Token should start with 'tok_', got {token}"
    assert len(token) >= 20, f"Token should be at least 20 chars, got {len(token)}"
    assert token.isalnum() or '_' in token, "Token should be alphanumeric with underscores"


def assert_api_key_format_valid(api_key: str):
    """Assert API key has correct format"""
    assert api_key.startswith("sk_live_"), f"API key should start with 'sk_live_', got {api_key}"
    assert len(api_key) == 56, f"API key should be 56 chars, got {len(api_key)}"


# Performance helpers

@pytest.fixture
def timer():
    """Simple timer for performance testing"""
    import time

    class Timer:
        def __enter__(self):
            self.start = time.time()
            return self

        def __exit__(self, *args):
            self.end = time.time()
            self.duration = self.end - self.start

    return Timer
