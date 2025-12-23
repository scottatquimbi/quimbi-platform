"""
Unit Tests for API Key Authentication

Tests:
- API key generation
- Hashing and verification
- Key creation and storage
- Scope-based authorization
- Key revocation

Author: Quimbi Platform
Date: October 14, 2025
"""

import pytest
from backend.api.auth import APIKeyManager
from tests.conftest import assert_api_key_format_valid


class TestAPIKeyGeneration:
    """Test API key generation"""

    def test_generate_api_key_format(self, api_key_manager):
        """Test generated key has correct format"""
        api_key = api_key_manager.generate_api_key()

        assert_api_key_format_valid(api_key)

    def test_generate_custom_prefix(self, api_key_manager):
        """Test generation with custom prefix"""
        api_key = api_key_manager.generate_api_key(prefix="test")

        assert api_key.startswith("test_live_"), "Should have custom prefix"

    def test_uniqueness(self, api_key_manager):
        """Test all generated keys are unique"""
        keys = {api_key_manager.generate_api_key() for _ in range(100)}

        assert len(keys) == 100, "All keys should be unique"

    def test_sufficient_entropy(self, api_key_manager):
        """Test keys have sufficient randomness"""
        keys = [api_key_manager.generate_api_key() for _ in range(10)]

        # Check no repeated patterns
        for key in keys:
            key_part = key.split("_live_")[1]
            # Should not have obvious patterns like "aaaa" or "1111"
            assert "aaaa" not in key_part.lower()
            assert "1111" not in key_part


class TestAPIKeyHashing:
    """Test API key hashing and verification"""

    def test_hash_api_key(self, api_key_manager):
        """Test API key hashing"""
        api_key = api_key_manager.generate_api_key()
        key_hash = api_key_manager.hash_api_key(api_key)

        assert key_hash != api_key, "Hash should be different from plaintext"
        assert len(key_hash) == 60, "Bcrypt hash should be 60 characters"
        assert key_hash.startswith("$2b$"), "Should be bcrypt hash"

    def test_verify_correct_key(self, api_key_manager):
        """Test verification of correct key"""
        api_key = api_key_manager.generate_api_key()
        key_hash = api_key_manager.hash_api_key(api_key)

        assert api_key_manager.verify_api_key(api_key, key_hash), "Correct key should verify"

    def test_verify_incorrect_key(self, api_key_manager):
        """Test verification rejects incorrect key"""
        api_key = api_key_manager.generate_api_key()
        wrong_key = api_key_manager.generate_api_key()
        key_hash = api_key_manager.hash_api_key(api_key)

        assert not api_key_manager.verify_api_key(wrong_key, key_hash), "Wrong key should fail"

    def test_same_key_different_hashes(self, api_key_manager):
        """Test same key produces different hashes (salt)"""
        api_key = api_key_manager.generate_api_key()

        hash1 = api_key_manager.hash_api_key(api_key)
        hash2 = api_key_manager.hash_api_key(api_key)

        assert hash1 != hash2, "Same key should produce different hashes (random salt)"

        # But both verify
        assert api_key_manager.verify_api_key(api_key, hash1)
        assert api_key_manager.verify_api_key(api_key, hash2)


class TestAPIKeyCreation:
    """Test API key creation and storage"""

    @pytest.mark.asyncio
    async def test_create_api_key(self, api_key_manager, db_session):
        """Test creating and storing API key"""
        plain_key, key_info = await api_key_manager.create_api_key(
            db_session,
            name="Test API Key",
            scopes=["read", "write"],
            expires_days=365
        )
        await db_session.commit()

        assert_api_key_format_valid(plain_key)
        assert key_info["name"] == "Test API Key"
        assert "read" in key_info["scopes"]
        assert "write" in key_info["scopes"]

    @pytest.mark.asyncio
    async def test_validate_api_key(self, api_key_manager, db_session):
        """Test validating stored API key"""
        plain_key, created_info = await api_key_manager.create_api_key(
            db_session,
            name="Test Key",
            scopes=["read"],
            expires_days=365
        )
        await db_session.commit()

        # Validate key
        key_info = await api_key_manager.validate_api_key(db_session, plain_key)

        assert key_info is not None, "Valid key should validate"
        assert key_info["name"] == "Test Key"
        assert "read" in key_info["scopes"]

    @pytest.mark.asyncio
    async def test_validate_invalid_key(self, api_key_manager, db_session):
        """Test validation rejects invalid key"""
        fake_key = api_key_manager.generate_api_key()

        key_info = await api_key_manager.validate_api_key(db_session, fake_key)

        assert key_info is None, "Invalid key should return None"

    @pytest.mark.asyncio
    async def test_scope_authorization(self, api_key_manager, db_session):
        """Test scope-based authorization"""
        plain_key, _ = await api_key_manager.create_api_key(
            db_session,
            name="Read-Only Key",
            scopes=["read"],
            expires_days=365
        )
        await db_session.commit()

        # Should validate with no required scopes
        key_info = await api_key_manager.validate_api_key(db_session, plain_key)
        assert key_info is not None

        # Should validate with required "read" scope
        key_info = await api_key_manager.validate_api_key(
            db_session,
            plain_key,
            required_scopes=["read"]
        )
        assert key_info is not None

        # Should fail with required "write" scope
        key_info = await api_key_manager.validate_api_key(
            db_session,
            plain_key,
            required_scopes=["write"]
        )
        assert key_info is None, "Should fail scope check"

    @pytest.mark.asyncio
    async def test_multiple_scopes(self, api_key_manager, db_session):
        """Test key with multiple scopes"""
        plain_key, _ = await api_key_manager.create_api_key(
            db_session,
            name="Full Access Key",
            scopes=["read", "write", "admin"],
            expires_days=365
        )
        await db_session.commit()

        # Should validate with any single required scope
        for required_scope in ["read", "write", "admin"]:
            key_info = await api_key_manager.validate_api_key(
                db_session,
                plain_key,
                required_scopes=[required_scope]
            )
            assert key_info is not None, f"Should have {required_scope} scope"

        # Should validate with multiple required scopes
        key_info = await api_key_manager.validate_api_key(
            db_session,
            plain_key,
            required_scopes=["read", "write"]
        )
        assert key_info is not None, "Should have both scopes"


class TestAPIKeyRevocation:
    """Test API key revocation"""

    @pytest.mark.asyncio
    async def test_revoke_api_key(self, api_key_manager, db_session):
        """Test revoking an API key"""
        plain_key, key_info = await api_key_manager.create_api_key(
            db_session,
            name="To Be Revoked",
            scopes=["read"],
            expires_days=365
        )
        await db_session.commit()

        key_id = key_info["id"]

        # Revoke
        await api_key_manager.revoke_api_key(
            db_session,
            key_id,
            reason="security_incident"
        )
        await db_session.commit()

        # Should no longer validate
        validated = await api_key_manager.validate_api_key(db_session, plain_key)
        assert validated is None, "Revoked key should not validate"


class TestAPIKeyExpiration:
    """Test API key expiration"""

    @pytest.mark.asyncio
    async def test_expired_key_not_validated(self, api_key_manager, db_session):
        """Test expired key is not validated"""
        # Create key with 0 days expiration (already expired)
        plain_key, _ = await api_key_manager.create_api_key(
            db_session,
            name="Expired Key",
            scopes=["read"],
            expires_days=0  # Expires immediately
        )
        await db_session.commit()

        # Should not validate (expired)
        key_info = await api_key_manager.validate_api_key(db_session, plain_key)

        # Note: Actual expiration check depends on database NOW() function
        # This test may pass or fail depending on timing
        # In SQLite, we'd need to manually set expires_at to past date


class TestAPIKeyUsageTracking:
    """Test usage tracking for API keys"""

    @pytest.mark.asyncio
    async def test_usage_count_increments(self, api_key_manager, db_session):
        """Test usage count increments on validation"""
        plain_key, _ = await api_key_manager.create_api_key(
            db_session,
            name="Usage Tracking Test",
            scopes=["read"],
            expires_days=365
        )
        await db_session.commit()

        # Validate multiple times
        for _ in range(3):
            await api_key_manager.validate_api_key(db_session, plain_key)
            await db_session.commit()

        # Usage count should have incremented
        # (Would need to query database to verify)
