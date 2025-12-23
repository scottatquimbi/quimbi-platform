"""
Tenant Context Management

Provides thread-safe context storage for the current tenant ID.
Uses Python's contextvars for async-safe tenant tracking across requests.

Usage:
    from backend.middleware.tenant_context import set_current_tenant_id, get_current_tenant_id

    # In middleware
    set_current_tenant_id(tenant.id)

    # In business logic
    tenant_id = get_current_tenant_id()
    if not tenant_id:
        raise ValueError("No tenant context set")

    # Query with tenant filter
    query = select(Customer).where(Customer.tenant_id == tenant_id)
"""
from contextvars import ContextVar
from typing import Optional
from uuid import UUID
import logging

logger = logging.getLogger(__name__)

# Global context variable for current tenant ID
# This is async-safe and isolated per request
_tenant_context: ContextVar[Optional[UUID]] = ContextVar('tenant_id', default=None)


def get_current_tenant_id() -> Optional[UUID]:
    """
    Get the current tenant ID from context.

    Returns:
        Current tenant UUID if set, None otherwise

    Example:
        tenant_id = get_current_tenant_id()
        if tenant_id:
            query = query.where(Model.tenant_id == tenant_id)
    """
    return _tenant_context.get()


def set_current_tenant_id(tenant_id: UUID) -> None:
    """
    Set the current tenant ID in context.

    This should be called by the tenant routing middleware after
    identifying the tenant from the request.

    Args:
        tenant_id: Tenant UUID to set

    Example:
        # In middleware
        tenant = await identify_tenant(request)
        set_current_tenant_id(tenant.id)
    """
    _tenant_context.set(tenant_id)
    logger.debug(f"tenant_context_set", extra={"tenant_id": str(tenant_id)})


def clear_tenant_context() -> None:
    """
    Clear the tenant context.

    This should be called after request processing is complete
    to ensure no tenant data leaks between requests.

    Example:
        # In middleware (cleanup)
        try:
            response = await call_next(request)
        finally:
            clear_tenant_context()
    """
    _tenant_context.set(None)
    logger.debug("tenant_context_cleared")


def require_tenant_context() -> UUID:
    """
    Get current tenant ID, raising error if not set.

    Returns:
        Current tenant UUID

    Raises:
        RuntimeError: If no tenant context is set

    Example:
        # In business logic that requires tenant
        tenant_id = require_tenant_context()
        # Guaranteed to have a tenant_id here
    """
    tenant_id = get_current_tenant_id()
    if not tenant_id:
        raise RuntimeError(
            "No tenant context set. Ensure tenant routing middleware is enabled "
            "and the request includes tenant identification (subdomain, API key, or webhook)."
        )
    return tenant_id


class TenantContext:
    """
    Context manager for temporarily setting tenant context.

    Useful for background tasks or testing.

    Example:
        from backend.models.tenant import Tenant

        tenant = await Tenant.get_by_slug(db, "quiltco1")

        with TenantContext(tenant.id):
            # All queries inside this block will use this tenant
            customers = await get_customers(db)
    """

    def __init__(self, tenant_id: UUID):
        """
        Initialize context manager.

        Args:
            tenant_id: Tenant UUID to use in this context
        """
        self.tenant_id = tenant_id
        self.previous_tenant_id: Optional[UUID] = None

    def __enter__(self):
        """Set tenant context."""
        self.previous_tenant_id = get_current_tenant_id()
        set_current_tenant_id(self.tenant_id)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Restore previous tenant context."""
        if self.previous_tenant_id:
            set_current_tenant_id(self.previous_tenant_id)
        else:
            clear_tenant_context()


async def get_current_tenant_or_none(db) -> Optional["Tenant"]:
    """
    Get current tenant model from context.

    Args:
        db: Database session

    Returns:
        Tenant model if context is set, None otherwise

    Example:
        tenant = await get_current_tenant_or_none(db)
        if tenant:
            print(f"Current tenant: {tenant.name}")
    """
    tenant_id = get_current_tenant_id()
    if not tenant_id:
        return None

    from backend.models.tenant import Tenant
    return await Tenant.get_by_id(db, tenant_id)


async def get_current_tenant(db) -> "Tenant":
    """
    Get current tenant model from context, raising error if not set.

    Args:
        db: Database session

    Returns:
        Tenant model

    Raises:
        RuntimeError: If no tenant context is set
        ValueError: If tenant ID is set but tenant not found

    Example:
        tenant = await get_current_tenant(db)
        print(f"Current tenant: {tenant.name}")
    """
    tenant_id = require_tenant_context()

    from backend.models.tenant import Tenant
    tenant = await Tenant.get_by_id(db, tenant_id)

    if not tenant:
        raise ValueError(f"Tenant {tenant_id} not found in database")

    return tenant
