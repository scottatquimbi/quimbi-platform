"""Add multi-tenant support with CRM-agnostic configuration

Revision ID: multi_tenant_001
Revises: hybrid_star_001
Create Date: 2025-11-03 12:00:00.000000

This migration adds multi-tenant support to the system:
1. Creates tenants table with CRM-agnostic configuration
2. Adds tenant_id to all dimension and fact tables
3. Creates indexes for tenant filtering
4. Supports multiple CRM providers (Gorgias, Zendesk, Salesforce, etc.)

Migration Strategy:
- Step 1: Create tenants table
- Step 2: Add tenant_id columns (nullable initially)
- Step 3: Create indexes
- Step 4: Backfill tenant_id from existing store_id (manual step)
- Step 5: Add NOT NULL constraints (separate migration after backfill)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'multi_tenant_001'
down_revision: Union[str, None] = 'hybrid_star_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ========================================
    # STEP 1: CREATE TENANTS TABLE
    # ========================================

    op.create_table(
        'tenants',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('slug', sa.String(50), unique=True, nullable=False,
                  comment='URL-safe tenant identifier (e.g., "quiltco1")'),
        sa.Column('name', sa.String(255), nullable=False,
                  comment='Human-readable tenant name'),

        # Legacy store_id mapping (for backfilling existing data)
        sa.Column('store_id', sa.String(100), unique=True,
                  comment='Legacy store ID for data migration'),

        # CRM configuration (agnostic!)
        sa.Column('crm_provider', sa.String(50), nullable=False,
                  comment='CRM provider: gorgias, zendesk, salesforce, helpshift, intercom, freshdesk'),
        sa.Column('crm_config', postgresql.JSONB(), nullable=False,
                  comment='Encrypted CRM-specific configuration (domain, credentials, etc.)'),
        sa.Column('webhook_identifiers', postgresql.JSONB(), nullable=True, server_default='{}',
                  comment='Identifiers for routing webhooks to correct tenant'),

        # API access (for tenant API authentication)
        sa.Column('api_key_hash', sa.String(255), unique=True,
                  comment='SHA256 hash of tenant API key'),

        # Configuration
        sa.Column('features', postgresql.JSONB(), nullable=True, server_default='{}',
                  comment='Feature flags enabled for this tenant'),
        sa.Column('settings', postgresql.JSONB(), nullable=True, server_default='{}',
                  comment='Tenant-specific settings'),

        # Status
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true',
                  comment='Whether tenant is active'),
        sa.Column('environment', sa.String(20), nullable=False, server_default='production',
                  comment='Environment: production, staging, development'),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
    )

    # Indexes for tenants table
    op.create_index('idx_tenants_slug', 'tenants', ['slug'])
    op.create_index('idx_tenants_store_id', 'tenants', ['store_id'])
    op.create_index('idx_tenants_api_key_hash', 'tenants', ['api_key_hash'])
    op.create_index('idx_tenants_crm_provider', 'tenants', ['crm_provider'])

    # GIN index for webhook_identifiers JSONB queries
    op.create_index(
        'idx_tenants_webhook_identifiers',
        'tenants',
        ['webhook_identifiers'],
        postgresql_using='gin'
    )

    # ========================================
    # STEP 2: ADD TENANT_ID TO EXISTING TABLES
    # ========================================

    # Add tenant_id to dimension tables (nullable for now)
    op.add_column('dim_archetype_l1',
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=True,
                  comment='References tenants.id'))

    op.add_column('dim_archetype_l2',
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=True,
                  comment='References tenants.id'))

    op.add_column('dim_archetype_l3',
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=True,
                  comment='References tenants.id'))

    # Add tenant_id to fact tables (nullable for now)
    op.add_column('fact_customer_current',
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=True,
                  comment='References tenants.id'))

    op.add_column('fact_customer_history',
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=True,
                  comment='References tenants.id'))

    # ========================================
    # STEP 3: CREATE INDEXES FOR TENANT FILTERING
    # ========================================

    # Single-column indexes on tenant_id (for basic filtering)
    op.create_index('idx_dim_l1_tenant', 'dim_archetype_l1', ['tenant_id'])
    op.create_index('idx_dim_l2_tenant', 'dim_archetype_l2', ['tenant_id'])
    op.create_index('idx_dim_l3_tenant', 'dim_archetype_l3', ['tenant_id'])
    op.create_index('idx_fact_current_tenant', 'fact_customer_current', ['tenant_id'])
    op.create_index('idx_fact_history_tenant', 'fact_customer_history', ['tenant_id'])

    # Composite indexes for common query patterns
    op.create_index(
        'idx_fact_current_tenant_customer',
        'fact_customer_current',
        ['tenant_id', 'customer_id']
    )

    op.create_index(
        'idx_dim_l2_tenant_archetype',
        'dim_archetype_l2',
        ['tenant_id', 'archetype_id']
    )

    op.create_index(
        'idx_fact_history_tenant_customer_days',
        'fact_customer_history',
        ['tenant_id', 'customer_id', 'days_ago']
    )

    # ========================================
    # STEP 4: ADD FOREIGN KEY CONSTRAINTS
    # ========================================
    # Note: NOT NULL constraints will be added in a separate migration
    # after backfilling tenant_id values

    op.create_foreign_key(
        'fk_dim_l1_tenant',
        'dim_archetype_l1',
        'tenants',
        ['tenant_id'],
        ['id'],
        ondelete='CASCADE'  # Delete archetypes if tenant is deleted
    )

    op.create_foreign_key(
        'fk_dim_l2_tenant',
        'dim_archetype_l2',
        'tenants',
        ['tenant_id'],
        ['id'],
        ondelete='CASCADE'
    )

    op.create_foreign_key(
        'fk_dim_l3_tenant',
        'dim_archetype_l3',
        'tenants',
        ['tenant_id'],
        ['id'],
        ondelete='CASCADE'
    )

    op.create_foreign_key(
        'fk_fact_current_tenant',
        'fact_customer_current',
        'tenants',
        ['tenant_id'],
        ['id'],
        ondelete='CASCADE'  # Delete customer data if tenant is deleted
    )

    op.create_foreign_key(
        'fk_fact_history_tenant',
        'fact_customer_history',
        'tenants',
        ['tenant_id'],
        ['id'],
        ondelete='CASCADE'
    )

    # ========================================
    # MANUAL STEP AFTER MIGRATION
    # ========================================
    print("""
    ✅ Multi-tenant schema created successfully!

    📋 NEXT STEPS (Manual):

    1. Create your first tenant:
       python scripts/create_tenant.py \\
           --slug your-company \\
           --name "Your Company" \\
           --crm-provider gorgias \\
           --crm-config '{"domain":"...", "username":"...", "api_key":"..."}'

    2. Backfill tenant_id for existing data:
       UPDATE dim_archetype_l1 SET tenant_id = (SELECT id FROM tenants WHERE store_id = dim_archetype_l1.store_id);
       UPDATE dim_archetype_l2 SET tenant_id = (SELECT id FROM tenants WHERE store_id = dim_archetype_l2.store_id);
       UPDATE dim_archetype_l3 SET tenant_id = (SELECT id FROM tenants WHERE store_id = dim_archetype_l3.store_id);
       UPDATE fact_customer_current SET tenant_id = (SELECT id FROM tenants WHERE store_id = fact_customer_current.store_id);
       UPDATE fact_customer_history SET tenant_id = (SELECT id FROM tenants WHERE store_id = fact_customer_history.store_id);

    3. Verify all rows have tenant_id:
       SELECT COUNT(*) FROM fact_customer_current WHERE tenant_id IS NULL;

    4. Run follow-up migration to add NOT NULL constraints:
       alembic upgrade head

    See MULTI_TENANT_MIGRATION_PLAN.md for full details.
    """)


def downgrade() -> None:
    """Rollback multi-tenant support."""

    # Drop foreign key constraints
    op.drop_constraint('fk_fact_history_tenant', 'fact_customer_history', type_='foreignkey')
    op.drop_constraint('fk_fact_current_tenant', 'fact_customer_current', type_='foreignkey')
    op.drop_constraint('fk_dim_l3_tenant', 'dim_archetype_l3', type_='foreignkey')
    op.drop_constraint('fk_dim_l2_tenant', 'dim_archetype_l2', type_='foreignkey')
    op.drop_constraint('fk_dim_l1_tenant', 'dim_archetype_l1', type_='foreignkey')

    # Drop indexes
    op.drop_index('idx_fact_history_tenant_customer_days', 'fact_customer_history')
    op.drop_index('idx_dim_l2_tenant_archetype', 'dim_archetype_l2')
    op.drop_index('idx_fact_current_tenant_customer', 'fact_customer_current')

    op.drop_index('idx_fact_history_tenant', 'fact_customer_history')
    op.drop_index('idx_fact_current_tenant', 'fact_customer_current')
    op.drop_index('idx_dim_l3_tenant', 'dim_archetype_l3')
    op.drop_index('idx_dim_l2_tenant', 'dim_archetype_l2')
    op.drop_index('idx_dim_l1_tenant', 'dim_archetype_l1')

    # Drop tenant_id columns
    op.drop_column('fact_customer_history', 'tenant_id')
    op.drop_column('fact_customer_current', 'tenant_id')
    op.drop_column('dim_archetype_l3', 'tenant_id')
    op.drop_column('dim_archetype_l2', 'tenant_id')
    op.drop_column('dim_archetype_l1', 'tenant_id')

    # Drop tenants table indexes
    op.drop_index('idx_tenants_webhook_identifiers', 'tenants')
    op.drop_index('idx_tenants_crm_provider', 'tenants')
    op.drop_index('idx_tenants_api_key_hash', 'tenants')
    op.drop_index('idx_tenants_store_id', 'tenants')
    op.drop_index('idx_tenants_slug', 'tenants')

    # Drop tenants table
    op.drop_table('tenants')
