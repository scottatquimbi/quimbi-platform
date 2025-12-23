"""
Tenant Model for Multi-Tenancy

Represents a customer/client using the Quimbi platform.
Each tenant has their own CRM configuration (Gorgias, Zendesk, Salesforce, etc.)
and isolated customer data.
"""
from sqlalchemy import Column, String, Boolean, DateTime, JSON, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional
import uuid
import logging

from backend.core.database import Base

logger = logging.getLogger(__name__)


class Tenant(Base):
    """
    Tenant model with CRM-agnostic configuration.

    Each tenant represents a company using Quimbi and can use any
    supported CRM provider (Gorgias, Zendesk, Salesforce, etc.).

    Attributes:
        id: Unique tenant identifier (UUID)
        slug: URL-safe identifier (e.g., "quiltco1")
        name: Human-readable name
        store_id: Legacy store identifier (for migration)
        crm_provider: CRM provider name (gorgias, zendesk, salesforce, etc.)
        crm_config: Encrypted CRM configuration (JSONB)
        webhook_identifiers: Routing identifiers for webhooks (JSONB)
        api_key_hash: SHA256 hash of tenant API key
        features: Enabled feature flags (JSONB)
        settings: Tenant-specific settings (JSONB)
        is_active: Whether tenant is active
        environment: production, staging, or development
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """

    __tablename__ = "tenants"
    __table_args__ = {"schema": "shared"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    store_id = Column(String(100), unique=True)

    # CRM configuration (agnostic!)
    crm_provider = Column(String(50), nullable=False, index=True)
    crm_config = Column(JSON, nullable=False)  # Encrypted at application layer
    webhook_identifiers = Column(JSON, default={})

    # API access
    api_key_hash = Column(String(255), unique=True, index=True)

    # Configuration
    features = Column(JSON, default={})
    settings = Column(JSON, default={})

    # Status
    is_active = Column(Boolean, default=True)
    environment = Column(String(20), default='production')

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<Tenant(slug='{self.slug}', crm_provider='{self.crm_provider}', active={self.is_active})>"

    # ==================== Query Helpers ====================

    @classmethod
    async def get_by_id(cls, db: AsyncSession, tenant_id: uuid.UUID) -> Optional["Tenant"]:
        """
        Get tenant by ID.

        Args:
            db: Database session
            tenant_id: Tenant UUID

        Returns:
            Tenant if found, None otherwise
        """
        result = await db.execute(
            select(cls).where(cls.id == tenant_id)
        )
        return result.scalar_one_or_none()

    @classmethod
    async def get_by_slug(cls, db: AsyncSession, slug: str) -> Optional["Tenant"]:
        """
        Get tenant by slug.

        Args:
            db: Database session
            slug: Tenant slug (e.g., "quiltco1")

        Returns:
            Tenant if found, None otherwise
        """
        result = await db.execute(
            select(cls).where(cls.slug == slug)
        )
        return result.scalar_one_or_none()

    @classmethod
    async def get_by_api_key_hash(cls, db: AsyncSession, api_key_hash: str) -> Optional["Tenant"]:
        """
        Get tenant by API key hash.

        Args:
            db: Database session
            api_key_hash: SHA256 hash of API key

        Returns:
            Tenant if found, None otherwise
        """
        result = await db.execute(
            select(cls).where(cls.api_key_hash == api_key_hash)
        )
        return result.scalar_one_or_none()

    @classmethod
    async def find_by_webhook_identifier(
        cls,
        db: AsyncSession,
        identifier_key: str,
        identifier_value: str
    ) -> Optional["Tenant"]:
        """
        Find tenant by webhook identifier.

        Used to route incoming webhooks to the correct tenant based on
        provider-specific identifiers (e.g., gorgias_domain, zendesk_subdomain).

        Args:
            db: Database session
            identifier_key: Key in webhook_identifiers JSON (e.g., "gorgias_domain")
            identifier_value: Value to match (e.g., "quiltco")

        Returns:
            Tenant if found, None otherwise

        Example:
            # Find tenant by Gorgias domain
            tenant = await Tenant.find_by_webhook_identifier(
                db,
                "gorgias_domain",
                "quiltco"
            )

            # Find tenant by Zendesk subdomain
            tenant = await Tenant.find_by_webhook_identifier(
                db,
                "zendesk_subdomain",
                "fabricshop"
            )
        """
        result = await db.execute(
            select(cls).where(
                cls.webhook_identifiers[identifier_key].astext == identifier_value
            )
        )
        return result.scalar_one_or_none()

    @classmethod
    async def list_active(cls, db: AsyncSession, environment: Optional[str] = None) -> list["Tenant"]:
        """
        List all active tenants.

        Args:
            db: Database session
            environment: Optional filter by environment (production, staging, etc.)

        Returns:
            List of active tenants
        """
        query = select(cls).where(cls.is_active == True)

        if environment:
            query = query.where(cls.environment == environment)

        result = await db.execute(query)
        return result.scalars().all()

    # ==================== CRM Config Helpers ====================

    def get_decrypted_crm_config(self) -> Dict[str, Any]:
        """
        Get decrypted CRM configuration.

        Returns:
            Decrypted CRM configuration dictionary

        Raises:
            ValueError: If decryption fails

        Example:
            tenant = await Tenant.get_by_slug(db, "quiltco1")
            config = tenant.get_decrypted_crm_config()
            print(config["domain"])  # "quiltco"
        """
        from backend.core.encryption import decrypt_config

        try:
            return decrypt_config(self.crm_config)
        except Exception as e:
            logger.error(f"Failed to decrypt CRM config for tenant {self.slug}: {e}")
            raise ValueError(f"Failed to decrypt CRM configuration: {e}")

    def set_crm_config(self, config: Dict[str, Any]) -> None:
        """
        Set CRM configuration (encrypts before storing).

        Args:
            config: Plain CRM configuration dictionary

        Example:
            tenant.set_crm_config({
                "domain": "quiltco",
                "username": "support@quiltco.com",
                "api_key": "secret123"
            })
        """
        from backend.core.encryption import encrypt_config

        try:
            self.crm_config = encrypt_config(config)
        except Exception as e:
            logger.error(f"Failed to encrypt CRM config for tenant {self.slug}: {e}")
            raise ValueError(f"Failed to encrypt CRM configuration: {e}")

    def get_webhook_identifier(self, key: str) -> Optional[str]:
        """
        Get a specific webhook identifier value.

        Args:
            key: Identifier key (e.g., "gorgias_domain")

        Returns:
            Identifier value if exists, None otherwise

        Example:
            gorgias_domain = tenant.get_webhook_identifier("gorgias_domain")
        """
        if not self.webhook_identifiers:
            return None
        return self.webhook_identifiers.get(key)

    def set_webhook_identifier(self, key: str, value: str) -> None:
        """
        Set a webhook identifier.

        Args:
            key: Identifier key
            value: Identifier value

        Example:
            tenant.set_webhook_identifier("gorgias_domain", "quiltco")
        """
        if self.webhook_identifiers is None:
            self.webhook_identifiers = {}
        self.webhook_identifiers[key] = value

    # ==================== Feature Flags ====================

    def has_feature(self, feature_name: str) -> bool:
        """
        Check if a feature is enabled for this tenant.

        Args:
            feature_name: Feature flag name

        Returns:
            True if enabled, False otherwise

        Example:
            if tenant.has_feature("advanced_analytics"):
                # Show advanced analytics
        """
        if not self.features:
            return False
        return self.features.get(feature_name, False)

    def enable_feature(self, feature_name: str) -> None:
        """Enable a feature for this tenant."""
        if self.features is None:
            self.features = {}
        self.features[feature_name] = True

    def disable_feature(self, feature_name: str) -> None:
        """Disable a feature for this tenant."""
        if self.features is None:
            self.features = {}
        self.features[feature_name] = False

    # ==================== Settings ====================

    def get_setting(self, key: str, default: Any = None) -> Any:
        """
        Get a tenant setting.

        Args:
            key: Setting key
            default: Default value if not set

        Returns:
            Setting value or default

        Example:
            timezone = tenant.get_setting("timezone", "UTC")
        """
        if not self.settings:
            return default
        return self.settings.get(key, default)

    def set_setting(self, key: str, value: Any) -> None:
        """
        Set a tenant setting.

        Args:
            key: Setting key
            value: Setting value

        Example:
            tenant.set_setting("timezone", "America/New_York")
        """
        if self.settings is None:
            self.settings = {}
        self.settings[key] = value
