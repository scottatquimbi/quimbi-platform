"""add player behavior events table

Revision ID: player_events_001
Revises: unified_seg_001
Create Date: 2025-10-10 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'player_events_001'
down_revision = 'unified_seg_001'
branch_labels = None
depends_on = None


def upgrade():
    """Add player_behavior_events table for data ingestion."""

    op.create_table(
        'player_behavior_events',
        sa.Column('event_id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('player_id', sa.String(255), nullable=False, index=True),
        sa.Column('game_id', sa.String(255), nullable=False, index=True),

        # Event identification
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('event_date', sa.Date(), nullable=False, index=True),
        sa.Column('event_timestamp', sa.DateTime(timezone=True), nullable=False),

        # Engagement metrics
        sa.Column('session_count', sa.Integer(), nullable=True),
        sa.Column('total_session_duration_minutes', sa.Float(), nullable=True),
        sa.Column('avg_session_duration_minutes', sa.Float(), nullable=True),

        # Monetization metrics
        sa.Column('purchase_count', sa.Integer(), nullable=True),
        sa.Column('total_purchase_amount', sa.Numeric(10, 2), nullable=True),

        # Context
        sa.Column('is_weekend', sa.Boolean(), nullable=True),
        sa.Column('event_data', postgresql.JSONB, nullable=True),

        # Metadata
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),

        comment='Raw behavioral events for players - source data for taxonomy calibration'
    )

    # Create composite unique constraint to prevent duplicate events
    op.create_index(
        'idx_player_events_unique',
        'player_behavior_events',
        ['player_id', 'game_id', 'event_timestamp'],
        unique=True
    )

    # Create index for efficient game-level queries
    op.create_index(
        'idx_player_events_game_date',
        'player_behavior_events',
        ['game_id', 'event_date']
    )


def downgrade():
    """Drop player_behavior_events table."""
    op.drop_table('player_behavior_events')
