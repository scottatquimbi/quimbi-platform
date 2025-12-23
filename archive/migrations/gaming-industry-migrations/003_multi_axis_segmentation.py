"""Multi-axis segmentation tables

Revision ID: 003
Revises: 002
Create Date: 2025-10-14

Tables for multi-axis behavioral segmentation:
- multi_axis_segments: Discovered segments per axis
- player_axis_memberships: Player fuzzy memberships
- player_drift_history: Temporal membership snapshots
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
import uuid


# revision identifiers
revision = 'multi_axis_001'
down_revision = 'player_events_001'
branch_labels = None
depends_on = None


def upgrade():
    # Multi-Axis Segments Table
    op.create_table(
        'multi_axis_segments',
        sa.Column('segment_id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('game_id', sa.String(255), nullable=False, index=True),
        sa.Column('axis_name', sa.String(100), nullable=False, index=True),
        sa.Column('segment_name', sa.String(100), nullable=False),
        sa.Column('cluster_center', JSONB, nullable=False, comment='Scaled feature vector for cluster center'),
        sa.Column('feature_names', JSONB, nullable=False, comment='List of feature names in cluster_center'),
        sa.Column('population_percentage', sa.Float, nullable=False),
        sa.Column('player_count', sa.Integer, nullable=False),
        sa.Column('interpretation', sa.Text, nullable=False),
        sa.Column('silhouette_score', sa.Float, nullable=True, comment='Quality metric for this axis'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),

        # Composite index for lookups
        sa.Index('idx_multi_axis_segments_game_axis', 'game_id', 'axis_name'),

        # Unique constraint: one segment name per axis per game per discovery
        sa.UniqueConstraint('game_id', 'axis_name', 'segment_name', name='uq_game_axis_segment'),

        comment='Discovered behavioral segments across multiple independent axes'
    )

    # Player Axis Memberships Table (Current State)
    op.create_table(
        'player_axis_memberships',
        sa.Column('membership_id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('player_id', sa.String(255), nullable=False, index=True),
        sa.Column('game_id', sa.String(255), nullable=False, index=True),
        sa.Column('axis_name', sa.String(100), nullable=False, index=True),
        sa.Column('memberships', JSONB, nullable=False, comment='Fuzzy memberships: {segment_name: membership_strength}'),
        sa.Column('dominant_segment', sa.String(100), nullable=False, comment='Segment with highest membership'),
        sa.Column('features', JSONB, nullable=True, comment='Raw features used for clustering (for debugging)'),
        sa.Column('calculated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),

        # Composite index for player profile lookups
        sa.Index('idx_player_axis_memberships_player_game', 'player_id', 'game_id'),
        sa.Index('idx_player_axis_memberships_player_axis', 'player_id', 'axis_name'),

        # Unique constraint: one membership per player per axis
        sa.UniqueConstraint('player_id', 'game_id', 'axis_name', name='uq_player_game_axis'),

        comment='Current fuzzy membership state for each player across all axes'
    )

    # Player Drift History Table (Temporal Snapshots)
    op.create_table(
        'player_drift_history',
        sa.Column('snapshot_id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('player_id', sa.String(255), nullable=False, index=True),
        sa.Column('game_id', sa.String(255), nullable=False, index=True),
        sa.Column('axis_name', sa.String(100), nullable=False, index=True),
        sa.Column('memberships', JSONB, nullable=False, comment='Fuzzy memberships snapshot: {segment_name: strength}'),
        sa.Column('dominant_segment', sa.String(100), nullable=False),
        sa.Column('snapshot_date', sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column('drift_from_baseline', sa.Float, nullable=True, comment='Cosine distance from baseline'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),

        # Composite indexes for drift queries
        sa.Index('idx_player_drift_history_player_axis_date', 'player_id', 'axis_name', 'snapshot_date'),
        sa.Index('idx_player_drift_history_game_axis', 'game_id', 'axis_name'),

        comment='Historical snapshots of player membership vectors for drift detection'
    )

    # Player Drift Alerts Table (Significant Changes)
    op.create_table(
        'player_drift_alerts',
        sa.Column('alert_id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('player_id', sa.String(255), nullable=False, index=True),
        sa.Column('game_id', sa.String(255), nullable=False, index=True),
        sa.Column('axis_name', sa.String(100), nullable=False),
        sa.Column('drift_magnitude', sa.Float, nullable=False, comment='Magnitude of drift (0.0-1.0)'),
        sa.Column('primary_shift_segment', sa.String(100), nullable=True, comment='Segment with biggest change'),
        sa.Column('primary_shift_change', sa.Float, nullable=True, comment='Change amount for primary segment'),
        sa.Column('interpretation', sa.Text, nullable=False),
        sa.Column('alert_type', sa.String(50), nullable=False, comment='e.g., churn_risk, engagement_increase'),
        sa.Column('severity', sa.String(20), nullable=False, comment='low, medium, high, critical'),
        sa.Column('detected_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('resolved', sa.Boolean, default=False, nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolution_notes', sa.Text, nullable=True),

        # Indexes for alert management
        sa.Index('idx_player_drift_alerts_player_game', 'player_id', 'game_id'),
        sa.Index('idx_player_drift_alerts_unresolved', 'resolved', 'detected_at'),
        sa.Index('idx_player_drift_alerts_severity', 'severity', 'detected_at'),

        comment='Alerts for significant behavioral drift detected (churn risk, etc.)'
    )

    # Discovery Metadata Table (Track discovery runs)
    op.create_table(
        'multi_axis_discovery_runs',
        sa.Column('run_id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('game_id', sa.String(255), nullable=False, index=True),
        sa.Column('player_count', sa.Integer, nullable=False),
        sa.Column('event_count', sa.Integer, nullable=False),
        sa.Column('axes_discovered', sa.Integer, nullable=False),
        sa.Column('total_segments', sa.Integer, nullable=False),
        sa.Column('avg_silhouette_score', sa.Float, nullable=True),
        sa.Column('game_launch_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('discovery_started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('discovery_completed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('processing_time_seconds', sa.Float, nullable=False),
        sa.Column('status', sa.String(20), nullable=False, comment='success, failed, partial'),
        sa.Column('error_message', sa.Text, nullable=True),

        sa.Index('idx_discovery_runs_game_date', 'game_id', 'discovery_completed_at'),

        comment='Metadata about discovery runs for auditing and performance tracking'
    )


def downgrade():
    op.drop_table('player_drift_alerts')
    op.drop_table('player_drift_history')
    op.drop_table('player_axis_memberships')
    op.drop_table('multi_axis_segments')
    op.drop_table('multi_axis_discovery_runs')
