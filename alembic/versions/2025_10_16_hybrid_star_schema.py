"""Hybrid star schema for multi-level archetypes

Revision ID: hybrid_star_001
Revises: 2025_10_15_ecommerce_vectors
Create Date: 2025-10-16 19:10:00.000000

This migration transforms the schema into a hybrid star schema:
- Dimension tables for L1/L2/L3 archetypes (deduplication)
- Fact table for current customer state
- Fact table for historical snapshots (flexible time periods)

Benefits:
- Fast current state queries
- Flexible time periods (7d, 14d, 28d, 60d, etc.)
- Archetype reuse (869 archetypes vs 27K customer rows)
- BI-friendly star schema
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'hybrid_star_001'
down_revision: Union[str, None] = 'ecommerce_vec_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ========================================
    # DIMENSION TABLES
    # ========================================

    # Dimension: Level 1 Archetypes (dominant-only)
    op.create_table(
        'dim_archetype_l1',
        sa.Column('archetype_id', sa.String(50), primary_key=True),
        sa.Column('store_id', sa.String(100), nullable=False),
        sa.Column('dominant_segments', postgresql.JSONB(), nullable=False,
                  comment='Dominant segment per axis: {axis: segment_name}'),
        sa.Column('description', sa.Text(), nullable=True,
                  comment='Human-readable archetype description'),
        sa.Column('behavioral_traits', postgresql.ARRAY(sa.String()), nullable=True,
                  comment='Array of traits like ["purchase_frequency:regular", ...]'),
        sa.Column('member_count', sa.Integer(), nullable=False, default=0),
        sa.Column('population_percentage', sa.Float(), nullable=False, default=0.0),
        sa.Column('avg_lifetime_value', sa.Float(), nullable=True),
        sa.Column('avg_order_frequency', sa.Float(), nullable=True),
        sa.Column('last_calculated', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
    )
    op.create_index('idx_dim_l1_store', 'dim_archetype_l1', ['store_id'])

    # Dimension: Level 2 Archetypes (strength binning)
    op.create_table(
        'dim_archetype_l2',
        sa.Column('archetype_id', sa.String(50), primary_key=True),
        sa.Column('store_id', sa.String(100), nullable=False),
        sa.Column('dominant_segments', postgresql.JSONB(), nullable=False,
                  comment='Dominant segment per axis: {axis: segment_name}'),
        sa.Column('membership_strengths', postgresql.JSONB(), nullable=False,
                  comment='Strength bins per axis: {axis: "weak"|"balanced"|"strong"}'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('behavioral_traits', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('member_count', sa.Integer(), nullable=False, default=0),
        sa.Column('population_percentage', sa.Float(), nullable=False, default=0.0),
        sa.Column('avg_lifetime_value', sa.Float(), nullable=True),
        sa.Column('avg_order_frequency', sa.Float(), nullable=True),
        sa.Column('last_calculated', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
    )
    op.create_index('idx_dim_l2_store', 'dim_archetype_l2', ['store_id'])

    # Dimension: Level 3 Archetypes (fuzzy top-2)
    op.create_table(
        'dim_archetype_l3',
        sa.Column('archetype_id', sa.String(50), primary_key=True),
        sa.Column('store_id', sa.String(100), nullable=False),
        sa.Column('fuzzy_memberships', postgresql.JSONB(), nullable=False,
                  comment='Top-2 segments per axis with scores: {axis: {seg1: 0.8, seg2: 0.2}}'),
        sa.Column('dominant_segments', postgresql.JSONB(), nullable=False,
                  comment='Dominant segment per axis for readability'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('behavioral_traits', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('member_count', sa.Integer(), nullable=False, default=0),
        sa.Column('population_percentage', sa.Float(), nullable=False, default=0.0),
        sa.Column('avg_lifetime_value', sa.Float(), nullable=True),
        sa.Column('avg_order_frequency', sa.Float(), nullable=True),
        sa.Column('last_calculated', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
    )
    op.create_index('idx_dim_l3_store', 'dim_archetype_l3', ['store_id'])

    # ========================================
    # FACT TABLES
    # ========================================

    # Fact: Current customer state
    op.create_table(
        'fact_customer_current',
        sa.Column('customer_id', sa.String(100), primary_key=True),
        sa.Column('store_id', sa.String(100), nullable=False),

        # Foreign keys to dimension tables
        sa.Column('archetype_l1_id', sa.String(50), nullable=True),
        sa.Column('archetype_l2_id', sa.String(50), nullable=True),
        sa.Column('archetype_l3_id', sa.String(50), nullable=True),

        # Business metrics
        sa.Column('lifetime_value', sa.Float(), nullable=True),
        sa.Column('total_orders', sa.Integer(), nullable=True),
        sa.Column('avg_order_value', sa.Float(), nullable=True),
        sa.Column('days_since_last_purchase', sa.Integer(), nullable=True),
        sa.Column('customer_tenure_days', sa.Integer(), nullable=True),
        sa.Column('churn_risk_score', sa.Float(), nullable=True),

        # Timestamps
        sa.Column('last_updated', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),

        # Foreign key constraints
        sa.ForeignKeyConstraint(['archetype_l1_id'], ['dim_archetype_l1.archetype_id'],
                                ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['archetype_l2_id'], ['dim_archetype_l2.archetype_id'],
                                ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['archetype_l3_id'], ['dim_archetype_l3.archetype_id'],
                                ondelete='SET NULL'),
    )
    op.create_index('idx_fact_current_store', 'fact_customer_current', ['store_id'])
    op.create_index('idx_fact_current_l1', 'fact_customer_current', ['archetype_l1_id'])
    op.create_index('idx_fact_current_l2', 'fact_customer_current', ['archetype_l2_id'])
    op.create_index('idx_fact_current_l3', 'fact_customer_current', ['archetype_l3_id'])

    # Fact: Historical customer snapshots
    op.create_table(
        'fact_customer_history',
        sa.Column('snapshot_id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('customer_id', sa.String(100), nullable=False),
        sa.Column('store_id', sa.String(100), nullable=False),
        sa.Column('snapshot_date', sa.DateTime(timezone=True), nullable=False,
                  comment='When this snapshot was taken'),
        sa.Column('days_ago', sa.Integer(), nullable=False,
                  comment='7, 14, 28, 60, 90, etc.'),

        # Foreign keys to dimension tables
        sa.Column('archetype_l1_id', sa.String(50), nullable=True),
        sa.Column('archetype_l2_id', sa.String(50), nullable=True),
        sa.Column('archetype_l3_id', sa.String(50), nullable=True),

        # Optional: store key metrics at time of snapshot
        sa.Column('lifetime_value', sa.Float(), nullable=True),
        sa.Column('total_orders', sa.Integer(), nullable=True),

        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),

        # Foreign key constraints
        sa.ForeignKeyConstraint(['archetype_l1_id'], ['dim_archetype_l1.archetype_id'],
                                ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['archetype_l2_id'], ['dim_archetype_l2.archetype_id'],
                                ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['archetype_l3_id'], ['dim_archetype_l3.archetype_id'],
                                ondelete='SET NULL'),
    )
    op.create_index('idx_fact_history_customer', 'fact_customer_history', ['customer_id'])
    op.create_index('idx_fact_history_customer_days', 'fact_customer_history',
                    ['customer_id', 'days_ago'])
    op.create_index('idx_fact_history_snapshot_date', 'fact_customer_history', ['snapshot_date'])
    op.create_index('idx_fact_history_store', 'fact_customer_history', ['store_id'])

    # ========================================
    # MIGRATE EXISTING DATA
    # ========================================

    # Step 1: Migrate L2 archetypes from archetype_definitions to dim_archetype_l2
    op.execute("""
        INSERT INTO dim_archetype_l2 (
            archetype_id, store_id, dominant_segments, membership_strengths,
            behavioral_traits, member_count, population_percentage,
            avg_lifetime_value, avg_order_frequency, last_calculated, created_at, updated_at
        )
        SELECT
            archetype_id, store_id, dominant_segments,
            '{}' as membership_strengths,  -- Will be populated later
            behavioral_traits, member_count, population_percentage,
            avg_lifetime_value, avg_order_frequency, last_calculated, created_at, now()
        FROM archetype_definitions
        WHERE archetype_level = 'strength'
        ON CONFLICT (archetype_id) DO NOTHING
    """)

    # Step 2: Migrate customer profiles to fact_customer_current
    op.execute("""
        INSERT INTO fact_customer_current (
            customer_id, store_id,
            archetype_l2_id,  -- Only L2 exists currently
            lifetime_value, total_orders, avg_order_value,
            days_since_last_purchase, customer_tenure_days, churn_risk_score,
            last_updated, created_at
        )
        SELECT
            customer_id, store_id,
            archetype_id as archetype_l2_id,
            lifetime_value, total_orders, avg_order_value,
            days_since_last_purchase, customer_tenure_days, churn_risk_score,
            last_updated, created_at
        FROM customer_profiles
        WHERE archetype_level = 'strength'
        ON CONFLICT (customer_id) DO NOTHING
    """)

    # Step 3: Migrate customer_profile_history to fact_customer_history
    op.execute("""
        INSERT INTO fact_customer_history (
            snapshot_id, customer_id, store_id, snapshot_date, days_ago,
            archetype_l2_id,
            lifetime_value, total_orders, created_at
        )
        SELECT
            gen_random_uuid() as snapshot_id,
            customer_id, store_id, snapshot_date, days_ago,
            archetype_id as archetype_l2_id,
            lifetime_value, total_orders, created_at
        FROM customer_profile_history
    """)

    print("✅ Star schema created and data migrated")
    print(f"   - Dimension tables: dim_archetype_l1, dim_archetype_l2, dim_archetype_l3")
    print(f"   - Fact tables: fact_customer_current, fact_customer_history")
    print(f"   - Old tables preserved for backup")


def downgrade() -> None:
    """Revert to old schema"""
    op.drop_table('fact_customer_history')
    op.drop_table('fact_customer_current')
    op.drop_table('dim_archetype_l3')
    op.drop_table('dim_archetype_l2')
    op.drop_table('dim_archetype_l1')

    print("⚠️  Reverted to old schema - star schema tables dropped")
