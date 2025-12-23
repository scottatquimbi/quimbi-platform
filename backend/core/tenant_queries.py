"""
Tenant-Aware Database Query Helpers

Provides utilities for automatically filtering queries by current tenant.
All queries should use these helpers to ensure proper tenant isolation.

Usage:
    from backend.core.tenant_queries import add_tenant_filter, require_tenant_id

    # Add tenant filter to query
    query = select(Customer).where(Customer.id == customer_id)
    query = add_tenant_filter(query, Customer)
    result = await db.execute(query)

    # Or get tenant ID directly
    tenant_id = require_tenant_id()
    query = select(Customer).where(
        Customer.id == customer_id,
        Customer.tenant_id == tenant_id
    )
"""
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import TypeVar, Type, Optional, List
from uuid import UUID
import logging

from backend.middleware.tenant_context import get_current_tenant_id, require_tenant_context

logger = logging.getLogger(__name__)

T = TypeVar('T')


def require_tenant_id() -> UUID:
    """
    Get current tenant ID, raising error if not set.

    Returns:
        Current tenant UUID

    Raises:
        RuntimeError: If no tenant context is set

    Example:
        tenant_id = require_tenant_id()
        query = select(Customer).where(Customer.tenant_id == tenant_id)
    """
    return require_tenant_context()


def get_tenant_id_or_none() -> Optional[UUID]:
    """
    Get current tenant ID without raising error.

    Returns:
        Current tenant UUID if set, None otherwise

    Example:
        tenant_id = get_tenant_id_or_none()
        if tenant_id:
            query = query.where(Model.tenant_id == tenant_id)
    """
    return get_current_tenant_id()


def add_tenant_filter(query: Select, model: Type[T]) -> Select:
    """
    Add tenant filter to SQLAlchemy query.

    Automatically filters by current tenant ID from context.

    Args:
        query: SQLAlchemy select query
        model: SQLAlchemy model class (must have tenant_id column)

    Returns:
        Query with tenant filter added

    Raises:
        RuntimeError: If no tenant context is set
        AttributeError: If model doesn't have tenant_id column

    Example:
        from backend.core.tenant_queries import add_tenant_filter

        # Query customers for current tenant
        query = select(Customer).where(Customer.email == "test@example.com")
        query = add_tenant_filter(query, Customer)
        result = await db.execute(query)

        # Equivalent to:
        tenant_id = require_tenant_id()
        query = select(Customer).where(
            Customer.email == "test@example.com",
            Customer.tenant_id == tenant_id
        )
    """
    tenant_id = require_tenant_id()

    # Verify model has tenant_id column
    if not hasattr(model, 'tenant_id'):
        raise AttributeError(
            f"Model {model.__name__} does not have tenant_id column. "
            f"Cannot apply tenant filter."
        )

    return query.where(model.tenant_id == tenant_id)


def add_tenant_filter_optional(query: Select, model: Type[T]) -> Select:
    """
    Add tenant filter only if tenant context is set.

    Useful for queries that should work both with and without tenant context
    (e.g., admin endpoints, background tasks).

    Args:
        query: SQLAlchemy select query
        model: SQLAlchemy model class

    Returns:
        Query with tenant filter added if context exists, otherwise unchanged

    Example:
        # Works with or without tenant context
        query = select(Customer)
        query = add_tenant_filter_optional(query, Customer)
    """
    tenant_id = get_tenant_id_or_none()

    if tenant_id and hasattr(model, 'tenant_id'):
        return query.where(model.tenant_id == tenant_id)

    return query


# ==================== Convenience Query Functions ====================

async def get_by_id_with_tenant(
    db: AsyncSession,
    model: Type[T],
    record_id: any,
    id_column: str = "id"
) -> Optional[T]:
    """
    Get a single record by ID with automatic tenant filtering.

    Args:
        db: Database session
        model: SQLAlchemy model class
        record_id: Record ID to fetch
        id_column: Name of ID column (default: "id")

    Returns:
        Record if found and belongs to current tenant, None otherwise

    Example:
        from backend.models.customer import Customer

        customer = await get_by_id_with_tenant(db, Customer, "12345")
        if customer:
            print(customer.name)
    """
    tenant_id = require_tenant_id()

    query = select(model).where(
        getattr(model, id_column) == record_id,
        model.tenant_id == tenant_id
    )

    result = await db.execute(query)
    return result.scalar_one_or_none()


async def list_with_tenant(
    db: AsyncSession,
    model: Type[T],
    limit: int = 100,
    offset: int = 0
) -> List[T]:
    """
    List records with automatic tenant filtering.

    Args:
        db: Database session
        model: SQLAlchemy model class
        limit: Maximum records to return
        offset: Number of records to skip

    Returns:
        List of records for current tenant

    Example:
        from backend.models.customer import Customer

        customers = await list_with_tenant(db, Customer, limit=50)
        print(f"Found {len(customers)} customers")
    """
    tenant_id = require_tenant_id()

    query = select(model).where(
        model.tenant_id == tenant_id
    ).limit(limit).offset(offset)

    result = await db.execute(query)
    return result.scalars().all()


async def count_with_tenant(
    db: AsyncSession,
    model: Type[T]
) -> int:
    """
    Count records with automatic tenant filtering.

    Args:
        db: Database session
        model: SQLAlchemy model class

    Returns:
        Count of records for current tenant

    Example:
        from backend.models.customer import Customer

        count = await count_with_tenant(db, Customer)
        print(f"Total customers: {count}")
    """
    from sqlalchemy import func

    tenant_id = require_tenant_id()

    query = select(func.count()).select_from(model).where(
        model.tenant_id == tenant_id
    )

    result = await db.execute(query)
    return result.scalar_one()


async def exists_with_tenant(
    db: AsyncSession,
    model: Type[T],
    record_id: any,
    id_column: str = "id"
) -> bool:
    """
    Check if a record exists for current tenant.

    Args:
        db: Database session
        model: SQLAlchemy model class
        record_id: Record ID to check
        id_column: Name of ID column (default: "id")

    Returns:
        True if record exists and belongs to current tenant, False otherwise

    Example:
        from backend.models.customer import Customer

        if await exists_with_tenant(db, Customer, "12345"):
            print("Customer exists")
    """
    from sqlalchemy import exists as sql_exists

    tenant_id = require_tenant_id()

    query = select(sql_exists().where(
        getattr(model, id_column) == record_id,
        model.tenant_id == tenant_id
    ))

    result = await db.execute(query)
    return result.scalar_one()


# ==================== Bulk Operations ====================

async def delete_by_id_with_tenant(
    db: AsyncSession,
    model: Type[T],
    record_id: any,
    id_column: str = "id"
) -> bool:
    """
    Delete a record by ID with tenant verification.

    Args:
        db: Database session
        model: SQLAlchemy model class
        record_id: Record ID to delete
        id_column: Name of ID column (default: "id")

    Returns:
        True if record was deleted, False if not found

    Example:
        from backend.models.customer import Customer

        deleted = await delete_by_id_with_tenant(db, Customer, "12345")
        if deleted:
            await db.commit()
            print("Customer deleted")
    """
    from sqlalchemy import delete

    tenant_id = require_tenant_id()

    stmt = delete(model).where(
        getattr(model, id_column) == record_id,
        model.tenant_id == tenant_id
    )

    result = await db.execute(stmt)
    return result.rowcount > 0


# ==================== Validation Helpers ====================

def ensure_tenant_ownership(record: T) -> None:
    """
    Verify that a record belongs to the current tenant.

    Args:
        record: SQLAlchemy model instance with tenant_id

    Raises:
        RuntimeError: If no tenant context is set
        ValueError: If record doesn't belong to current tenant

    Example:
        customer = await db.get(Customer, customer_id)
        ensure_tenant_ownership(customer)  # Raises if wrong tenant
        # Safe to proceed with customer
    """
    tenant_id = require_tenant_id()

    if not hasattr(record, 'tenant_id'):
        raise AttributeError(
            f"Record {record.__class__.__name__} does not have tenant_id attribute"
        )

    if record.tenant_id != tenant_id:
        raise ValueError(
            f"Record {record.__class__.__name__} belongs to different tenant. "
            f"Expected {tenant_id}, got {record.tenant_id}"
        )


def verify_tenant_access(record_tenant_id: UUID) -> None:
    """
    Verify that current tenant can access a record.

    Args:
        record_tenant_id: Tenant ID of the record to access

    Raises:
        RuntimeError: If no tenant context is set
        ValueError: If record belongs to different tenant

    Example:
        # Before processing a record
        verify_tenant_access(customer.tenant_id)
        # Raises if wrong tenant
    """
    current_tenant_id = require_tenant_id()

    if record_tenant_id != current_tenant_id:
        logger.warning(
            "tenant_access_denied",
            extra={
                "current_tenant": str(current_tenant_id),
                "record_tenant": str(record_tenant_id)
            }
        )
        raise ValueError(
            f"Access denied: Record belongs to different tenant"
        )
