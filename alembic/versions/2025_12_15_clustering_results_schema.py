"""Clustering results schema for 3-tier system

Revision ID: clustering_results_001
Revises: hybrid_star_001
Create Date: 2025-12-15 00:00:00.000000

This migration creates tables to store the full 3-tier clustering results:
- Tier 1 Segments: K-means segments per axis with AI-generated names
- Tier 2 Archetypes: Unique combinations of Tier 1 segments across all axes
- Tier 3 Customer Vectors: Individual customer fuzzy membership profiles

Data Source: run_full_clustering.py output from combined_sales table
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'clustering_results_001'
down_revision: Union[str, None] = 'hybrid_star_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ========================================
    # TIER 1: SEGMENT MASTER TABLE
    # ========================================

    op.create_table(
        'dim_segment_master',
        sa.Column('segment_id', sa.String(50), primary_key=True,
                  comment='Unique segment identifier (UUID)'),
        sa.Column('store_id', sa.String(100), nullable=False,
                  comment='Store/tenant identifier'),
        sa.Column('axis_name', sa.String(100), nullable=False,
                  comment='Behavioral axis (e.g., purchase_frequency, purchase_value)'),
        sa.Column('segment_name', sa.String(200), nullable=False,
                  comment='AI-generated segment name (e.g., high_frequency_loyalists)'),

        # Clustering metadata
        sa.Column('cluster_center', postgresql.JSONB(), nullable=False,
                  comment='Normalized cluster centroid: {feature: value}'),
        sa.Column('feature_names', postgresql.ARRAY(sa.String()), nullable=False,
                  comment='Feature names used for clustering'),
        sa.Column('scaler_params', postgresql.JSONB(), nullable=False,
                  comment='StandardScaler parameters: {mean: [...], scale: [...]}'),

        # Population statistics
        sa.Column('customer_count', sa.Integer(), nullable=False,
                  comment='Number of customers in this segment'),
        sa.Column('population_percentage', sa.Float(), nullable=False,
                  comment='Percentage of total population (0.0-1.0)'),

        # Quality metrics
        sa.Column('silhouette_score', sa.Float(), nullable=True,
                  comment='Cluster quality metric (0.0-1.0, higher is better)'),

        # Interpretation
        sa.Column('interpretation', sa.Text(), nullable=False,
                  comment='AI-generated interpretation of segment behavior'),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('last_clustered', sa.DateTime(timezone=True), nullable=False,
                  comment='When this segment was last discovered via clustering'),
    )

    op.create_index('idx_segment_master_store', 'dim_segment_master', ['store_id'])
    op.create_index('idx_segment_master_axis', 'dim_segment_master', ['axis_name'])
    op.create_index('idx_segment_master_store_axis', 'dim_segment_master', ['store_id', 'axis_name'])

    # ========================================
    # TIER 2: ARCHETYPE DEFINITIONS
    # ========================================

    # Note: Uses existing dim_archetype_l1 from hybrid_star_001
    # But we'll add a view for archetype combinations

    op.create_table(
        'dim_archetype_combination',
        sa.Column('archetype_id', sa.String(50), primary_key=True,
                  comment='Unique archetype identifier'),
        sa.Column('store_id', sa.String(100), nullable=False),

        # Archetype signature
        sa.Column('dominant_segments', postgresql.JSONB(), nullable=False,
                  comment='Dominant segment per axis: {axis: segment_name}'),
        sa.Column('archetype_signature', sa.Text(), nullable=False,
                  comment='Full signature string for matching'),

        # Fuzzy membership distribution (optional, for L3 archetypes)
        sa.Column('fuzzy_memberships', postgresql.JSONB(), nullable=True,
                  comment='Top-2 memberships per axis: {axis: {seg1: 0.8, seg2: 0.2}}'),

        # Population statistics
        sa.Column('customer_count', sa.Integer(), nullable=False, default=0),
        sa.Column('population_percentage', sa.Float(), nullable=False, default=0.0),

        # Business metrics (populated later from customer data)
        sa.Column('avg_lifetime_value', sa.Float(), nullable=True),
        sa.Column('avg_order_frequency', sa.Float(), nullable=True),
        sa.Column('avg_order_value', sa.Float(), nullable=True),

        # Description
        sa.Column('description', sa.Text(), nullable=True,
                  comment='AI-generated archetype description'),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('last_calculated', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_index('idx_archetype_combo_store', 'dim_archetype_combination', ['store_id'])
    op.create_index('idx_archetype_combo_count', 'dim_archetype_combination', ['customer_count'])

    # ========================================
    # TIER 3: CUSTOMER FUZZY MEMBERSHIPS
    # ========================================

    op.create_table(
        'fact_customer_fuzzy_memberships',
        sa.Column('customer_id', sa.String(100), nullable=False,
                  comment='Customer identifier'),
        sa.Column('store_id', sa.String(100), nullable=False),
        sa.Column('axis_name', sa.String(100), nullable=False,
                  comment='Behavioral axis'),

        # Fuzzy memberships for this axis
        sa.Column('segment_memberships', postgresql.JSONB(), nullable=False,
                  comment='All segment memberships for this axis: {segment_name: membership_score}'),
        sa.Column('dominant_segment', sa.String(200), nullable=False,
                  comment='Highest-scoring segment for this axis'),
        sa.Column('dominant_membership_score', sa.Float(), nullable=False,
                  comment='Membership score for dominant segment (0.0-1.0)'),

        # Features used for clustering (for explainability)
        sa.Column('features', postgresql.JSONB(), nullable=True,
                  comment='Customer features for this axis: {feature: value}'),

        # Timestamps
        sa.Column('calculated_at', sa.DateTime(timezone=True), nullable=False,
                  comment='When this membership was calculated'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),

        # Composite primary key
        sa.PrimaryKeyConstraint('customer_id', 'axis_name', 'store_id'),
    )

    op.create_index('idx_fuzzy_customer', 'fact_customer_fuzzy_memberships', ['customer_id'])
    op.create_index('idx_fuzzy_store', 'fact_customer_fuzzy_memberships', ['store_id'])
    op.create_index('idx_fuzzy_axis', 'fact_customer_fuzzy_memberships', ['axis_name'])
    op.create_index('idx_fuzzy_dominant', 'fact_customer_fuzzy_memberships', ['dominant_segment'])

    # ========================================
    # TIER 3: CUSTOMER ARCHETYPE ASSIGNMENT
    # ========================================

    op.create_table(
        'fact_customer_archetype',
        sa.Column('customer_id', sa.String(100), primary_key=True),
        sa.Column('store_id', sa.String(100), nullable=False),

        # Archetype assignment
        sa.Column('archetype_id', sa.String(50), nullable=False,
                  comment='FK to dim_archetype_combination'),
        sa.Column('archetype_signature', sa.Text(), nullable=False,
                  comment='Full archetype signature for display'),

        # Dominant segments summary (denormalized for quick access)
        sa.Column('dominant_segments', postgresql.JSONB(), nullable=False,
                  comment='Dominant segment per axis: {axis: segment_name}'),

        # Business metrics (denormalized)
        sa.Column('lifetime_value', sa.Float(), nullable=True),
        sa.Column('total_orders', sa.Integer(), nullable=True),
        sa.Column('avg_order_value', sa.Float(), nullable=True),
        sa.Column('days_since_last_purchase', sa.Integer(), nullable=True),
        sa.Column('customer_tenure_days', sa.Integer(), nullable=True),

        # Timestamps
        sa.Column('calculated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),

        # Foreign key
        sa.ForeignKeyConstraint(['archetype_id'], ['dim_archetype_combination.archetype_id'],
                                ondelete='CASCADE'),
    )

    op.create_index('idx_customer_archetype_store', 'fact_customer_archetype', ['store_id'])
    op.create_index('idx_customer_archetype_id', 'fact_customer_archetype', ['archetype_id'])

    # ========================================
    # CLUSTERING RUN METADATA
    # ========================================

    op.create_table(
        'clustering_run_metadata',
        sa.Column('run_id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('store_id', sa.String(100), nullable=False),
        sa.Column('run_started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('run_completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(50), nullable=False,
                  comment='running, completed, failed'),

        # Configuration
        sa.Column('config', postgresql.JSONB(), nullable=False,
                  comment='Clustering parameters: {min_k, max_k, min_silhouette, etc.}'),

        # Results summary
        sa.Column('total_customers', sa.Integer(), nullable=True),
        sa.Column('axes_clustered', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('total_segments', sa.Integer(), nullable=True,
                  comment='Total Tier 1 segments discovered'),
        sa.Column('total_archetypes', sa.Integer(), nullable=True,
                  comment='Total Tier 2 archetypes created'),

        # Quality metrics
        sa.Column('avg_silhouette_score', sa.Float(), nullable=True),
        sa.Column('min_silhouette_score', sa.Float(), nullable=True),
        sa.Column('max_silhouette_score', sa.Float(), nullable=True),

        # Errors
        sa.Column('error_message', sa.Text(), nullable=True),

        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
    )

    op.create_index('idx_clustering_run_store', 'clustering_run_metadata', ['store_id'])
    op.create_index('idx_clustering_run_status', 'clustering_run_metadata', ['status'])
    op.create_index('idx_clustering_run_completed', 'clustering_run_metadata', ['run_completed_at'])

    print("✅ Clustering results schema created")
    print("   - Tier 1: dim_segment_master (segments per axis)")
    print("   - Tier 2: dim_archetype_combination (archetype definitions)")
    print("   - Tier 3: fact_customer_fuzzy_memberships (fuzzy membership vectors)")
    print("   - Tier 3: fact_customer_archetype (customer → archetype assignments)")
    print("   - Metadata: clustering_run_metadata (run tracking)")


def downgrade() -> None:
    """Revert clustering results schema"""
    op.drop_table('clustering_run_metadata')
    op.drop_table('fact_customer_archetype')
    op.drop_table('fact_customer_fuzzy_memberships')
    op.drop_table('dim_archetype_combination')
    op.drop_table('dim_segment_master')

    print("⚠️  Clustering results schema dropped")
