"""Add e-commerce customer profiles with vector storage

Revision ID: ecommerce_vec_001
Revises:
Create Date: 2025-10-15

Tables:
- customer_profiles: Current state (vectors per axis)
- customer_profile_history: Historical snapshots (7/14/28 days ago)
- customer_metadata: Additional context for AI
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'ecommerce_vec_001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Create e-commerce customer profile tables with vector storage."""

    # Note: We use JSONB for vector storage (no pgvector extension needed)
    # This makes deployment simpler and works on any PostgreSQL 9.4+

    # Table 1: customer_profiles (current state)
    op.create_table(
        'customer_profiles',
        sa.Column('customer_id', sa.String(100), primary_key=True),
        sa.Column('store_id', sa.String(100), nullable=False, index=True,
                  server_default='linda_quilting'),

        # Archetype assignment
        sa.Column('archetype_id', sa.String(50), nullable=True, index=True),
        sa.Column('archetype_level', sa.String(20), nullable=True,
                  comment='dominant, strength, or fuzzy'),

        # Segment membership per axis (stored as vectors)
        # Format: {axis_name: {segment_name: membership_score}}
        sa.Column('segment_memberships', postgresql.JSONB, nullable=False,
                  server_default='{}',
                  comment='Fuzzy membership scores per axis'),

        # Dominant segments per axis
        sa.Column('dominant_segments', postgresql.JSONB, nullable=False,
                  server_default='{}',
                  comment='{axis_name: segment_name}'),

        # Membership strength per axis (strong/balanced/weak)
        sa.Column('membership_strengths', postgresql.JSONB, nullable=False,
                  server_default='{}',
                  comment='{axis_name: "strong"|"balanced"|"weak"}'),

        # Raw features per axis (for drift detection)
        sa.Column('feature_vectors', postgresql.JSONB, nullable=False,
                  server_default='{}',
                  comment='{axis_name: {feature_name: value}}'),

        # Business metrics (for quick queries)
        sa.Column('lifetime_value', sa.Float, nullable=True),
        sa.Column('total_orders', sa.Integer, nullable=True),
        sa.Column('avg_order_value', sa.Float, nullable=True),
        sa.Column('days_since_last_purchase', sa.Integer, nullable=True),
        sa.Column('customer_tenure_days', sa.Integer, nullable=True),
        sa.Column('churn_risk_score', sa.Float, nullable=True,
                  comment='0.0-1.0, higher = more at risk'),

        # Metadata
        sa.Column('last_updated', sa.DateTime(timezone=True),
                  server_default=sa.text('NOW()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('NOW()'), nullable=False),

        comment='Current customer behavioral profiles with segment vectors'
    )

    # Indexes for common queries
    op.create_index('ix_customer_profiles_store', 'customer_profiles', ['store_id'])
    op.create_index('ix_customer_profiles_archetype', 'customer_profiles', ['archetype_id'])
    op.create_index('ix_customer_profiles_ltv', 'customer_profiles', ['lifetime_value'])
    op.create_index('ix_customer_profiles_churn', 'customer_profiles', ['churn_risk_score'])

    # GIN index for JSONB queries
    op.execute("""
        CREATE INDEX ix_customer_profiles_segments_gin
        ON customer_profiles USING GIN (segment_memberships)
    """)
    op.execute("""
        CREATE INDEX ix_customer_profiles_dominant_gin
        ON customer_profiles USING GIN (dominant_segments)
    """)


    # Table 2: customer_profile_history (historical snapshots)
    op.create_table(
        'customer_profile_history',
        sa.Column('snapshot_id', postgresql.UUID(as_uuid=True),
                  primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('customer_id', sa.String(100), nullable=False, index=True),
        sa.Column('store_id', sa.String(100), nullable=False, index=True),

        # Snapshot metadata
        sa.Column('snapshot_date', sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column('days_ago', sa.Integer, nullable=False, index=True,
                  comment='7, 14, or 28 days ago'),

        # Same vector structure as current profiles
        sa.Column('archetype_id', sa.String(50), nullable=True),
        sa.Column('segment_memberships', postgresql.JSONB, nullable=False),
        sa.Column('dominant_segments', postgresql.JSONB, nullable=False),
        sa.Column('membership_strengths', postgresql.JSONB, nullable=False),
        sa.Column('feature_vectors', postgresql.JSONB, nullable=False),

        # Business metrics at that point in time
        sa.Column('lifetime_value', sa.Float, nullable=True),
        sa.Column('total_orders', sa.Integer, nullable=True),
        sa.Column('avg_order_value', sa.Float, nullable=True),

        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('NOW()'), nullable=False),

        comment='Historical customer profile snapshots for trend analysis'
    )

    # Composite index for time-series queries
    op.create_index('ix_history_customer_date', 'customer_profile_history',
                    ['customer_id', 'snapshot_date'])
    op.create_index('ix_history_days_ago', 'customer_profile_history',
                    ['days_ago', 'snapshot_date'])


    # Table 3: customer_metadata (additional context for AI)
    op.create_table(
        'customer_metadata',
        sa.Column('customer_id', sa.String(100), primary_key=True),
        sa.Column('store_id', sa.String(100), nullable=False),

        # Customer context
        sa.Column('primary_category', sa.String(100), nullable=True,
                  comment='Most purchased category'),
        sa.Column('preferred_brands', postgresql.ARRAY(sa.String), nullable=True),
        sa.Column('expertise_level', sa.String(50), nullable=True,
                  comment='beginner, intermediate, expert'),
        sa.Column('project_types', postgresql.ARRAY(sa.String), nullable=True,
                  comment='Types of projects they make'),

        # Communication preferences
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('prefers_email', sa.Boolean, server_default='true'),
        sa.Column('prefers_sms', sa.Boolean, server_default='false'),
        sa.Column('opted_out_marketing', sa.Boolean, server_default='false'),

        # AI context
        sa.Column('customer_notes', sa.Text, nullable=True,
                  comment='Free-form notes for AI context'),
        sa.Column('tags', postgresql.ARRAY(sa.String), nullable=True,
                  comment='Custom tags: VIP, at-risk, new, etc.'),

        sa.Column('last_updated', sa.DateTime(timezone=True),
                  server_default=sa.text('NOW()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('NOW()'), nullable=False),

        sa.ForeignKeyConstraint(['customer_id'], ['customer_profiles.customer_id'],
                                ondelete='CASCADE'),

        comment='Additional customer context for AI agents'
    )


    # Table 4: archetype_definitions (for AI to understand segments)
    op.create_table(
        'archetype_definitions',
        sa.Column('archetype_id', sa.String(50), primary_key=True),
        sa.Column('store_id', sa.String(100), nullable=False),
        sa.Column('archetype_level', sa.String(20), nullable=False),

        # Archetype characteristics
        sa.Column('dominant_segments', postgresql.JSONB, nullable=False,
                  comment='{axis: segment}'),
        sa.Column('member_count', sa.Integer, nullable=False),
        sa.Column('population_percentage', sa.Float, nullable=False),

        # Business characteristics
        sa.Column('avg_lifetime_value', sa.Float, nullable=True),
        sa.Column('avg_order_frequency', sa.Float, nullable=True),
        sa.Column('retention_rate', sa.Float, nullable=True),
        sa.Column('churn_rate', sa.Float, nullable=True),

        # AI-readable descriptions
        sa.Column('description', sa.Text, nullable=True,
                  comment='Human-readable archetype description'),
        sa.Column('behavioral_traits', postgresql.ARRAY(sa.String), nullable=True,
                  comment='Key traits: loyal, price-sensitive, etc.'),
        sa.Column('recommended_actions', postgresql.JSONB, nullable=True,
                  comment='Marketing/service recommendations'),

        sa.Column('last_calculated', sa.DateTime(timezone=True),
                  server_default=sa.text('NOW()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('NOW()'), nullable=False),

        comment='Archetype definitions with AI-readable context'
    )

    op.create_index('ix_archetypes_store', 'archetype_definitions', ['store_id'])
    op.create_index('ix_archetypes_level', 'archetype_definitions', ['archetype_level'])


def downgrade():
    """Drop all tables."""
    op.drop_table('archetype_definitions')
    op.drop_table('customer_metadata')
    op.drop_table('customer_profile_history')
    op.drop_table('customer_profiles')
