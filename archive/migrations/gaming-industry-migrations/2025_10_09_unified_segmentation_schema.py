"""unified segmentation schema

Revision ID: unified_seg_001
Revises: [previous_revision]
Create Date: 2025-10-09 18:00:00.000000

Description:
    Creates unified segmentation architecture with distance-from-center approach.

    New Tables:
    - game_behavioral_taxonomy: Game-specific axis definitions
    - behavioral_axes: Axes and segments per game
    - segment_definitions: Segment centers, covariance, contextual patterns
    - player_segment_memberships: Fuzzy membership with position tracking

    Preserves existing tables for backward compatibility during migration.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'unified_seg_001'
down_revision = None  # Update this to the latest revision
branch_labels = None
depends_on = None


def upgrade():
    """Create unified segmentation schema"""

    # Table 1: Game Behavioral Taxonomy
    op.create_table(
        'game_behavioral_taxonomy',
        sa.Column('taxonomy_id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('game_id', sa.String(100), nullable=False, unique=True, index=True),
        sa.Column('genre', sa.String(50), nullable=True),

        # Axis configuration
        sa.Column('universal_axes', postgresql.JSONB, nullable=False,
                  server_default=sa.text("'[]'::jsonb"),
                  comment='["monetization", "engagement", "temporal", "social"]'),
        sa.Column('game_specific_axes', postgresql.JSONB, nullable=False,
                  server_default=sa.text("'[]'::jsonb"),
                  comment='Game-discovered axes like ["progression_style", "combat_preference"]'),

        # Validation metrics
        sa.Column('total_axes', sa.Integer, nullable=False, server_default='0'),
        sa.Column('variance_explained', sa.Float, nullable=True,
                  comment='Should be >0.70 - percentage of population variance captured'),

        # Metadata
        sa.Column('population_size', sa.Integer, nullable=True,
                  comment='Number of players used for calibration'),
        sa.Column('last_calibration', sa.DateTime(timezone=True), nullable=True),
        sa.Column('confidence_score', sa.Float, nullable=True,
                  comment='Overall confidence in taxonomy (0.0-1.0)'),

        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'),
                  onupdate=sa.text('NOW()'), nullable=False),

        comment='Game-specific behavioral taxonomy defining axes and expected category counts'
    )

    # Table 2: Behavioral Axes
    op.create_table(
        'behavioral_axes',
        sa.Column('axis_id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('taxonomy_id', postgresql.UUID(as_uuid=True), nullable=False),

        # Axis definition
        sa.Column('axis_name', sa.String(100), nullable=False,
                  comment='e.g., "monetization", "temporal", "progression_style"'),
        sa.Column('axis_type', sa.String(20), nullable=False,
                  comment='UNIVERSAL or GAME_SPECIFIC'),
        sa.Column('description', sa.Text, nullable=True),

        # Segments along this axis (stored as JSONB for flexibility)
        sa.Column('segments', postgresql.JSONB, nullable=False,
                  server_default=sa.text("'[]'::jsonb"),
                  comment='Array of segment definitions with centers and variance'),

        # Metrics that define this axis
        sa.Column('defining_metrics', postgresql.JSONB, nullable=False,
                  server_default=sa.text("'[]'::jsonb"),
                  comment='["monthly_spend", "purchase_frequency", "avg_purchase_amount"]'),

        # Statistical properties
        sa.Column('variance_explained', sa.Float, nullable=True,
                  comment='How much of population variance this axis captures'),

        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'),
                  onupdate=sa.text('NOW()'), nullable=False),

        sa.ForeignKeyConstraint(['taxonomy_id'], ['game_behavioral_taxonomy.taxonomy_id'],
                                ondelete='CASCADE'),
        sa.UniqueConstraint('taxonomy_id', 'axis_name', name='uq_taxonomy_axis'),

        comment='Behavioral axes per game with segment definitions'
    )

    # Create indexes for behavioral_axes
    op.create_index('ix_behavioral_axes_taxonomy', 'behavioral_axes', ['taxonomy_id'])
    op.create_index('ix_behavioral_axes_name', 'behavioral_axes', ['axis_name'])
    op.create_index('ix_behavioral_axes_type', 'behavioral_axes', ['axis_type'])

    # Table 3: Segment Definitions
    op.create_table(
        'segment_definitions',
        sa.Column('segment_id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('axis_id', postgresql.UUID(as_uuid=True), nullable=False),

        # Segment identity
        sa.Column('segment_name', sa.String(100), nullable=False,
                  comment='e.g., "whale", "weekend_concentrator", "free_play"'),
        sa.Column('axis_name', sa.String(100), nullable=False,
                  comment='Parent axis name for denormalized access'),

        # Segment center (multivariate mean)
        sa.Column('center_position', postgresql.JSONB, nullable=False,
                  comment='{"monthly_spend": 867.5, "purchase_frequency": 4.2}'),

        # Segment spread (covariance matrix and std devs)
        sa.Column('covariance_matrix', postgresql.JSONB, nullable=True,
                  comment='Stored as 2D array for distance calculations'),
        sa.Column('standard_deviations', postgresql.JSONB, nullable=False,
                  comment='{"monthly_spend": 450.2, "purchase_frequency": 1.8}'),

        # Contextual sub-patterns (optional - for temporal/lifecycle awareness)
        sa.Column('contextual_centers', postgresql.JSONB, nullable=True,
                  comment='{"weekday": {...}, "weekend": {...}} for temporal segments'),

        # Population statistics
        sa.Column('member_count', sa.Integer, nullable=True,
                  comment='Number of players in this segment'),
        sa.Column('percentage_of_population', sa.Float, nullable=True),

        # Outcome correlations (for prioritization)
        sa.Column('ltv_correlation', sa.Float, nullable=True,
                  comment='Correlation with LTV (0.0-1.0, higher = more predictive)'),
        sa.Column('churn_correlation', sa.Float, nullable=True,
                  comment='Correlation with churn (0.0-1.0)'),
        sa.Column('support_correlation', sa.Float, nullable=True,
                  comment='Correlation with support-seeking behavior'),

        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'),
                  onupdate=sa.text('NOW()'), nullable=False),

        sa.ForeignKeyConstraint(['axis_id'], ['behavioral_axes.axis_id'],
                                ondelete='CASCADE'),
        sa.UniqueConstraint('axis_id', 'segment_name', name='uq_axis_segment'),

        comment='Segment definitions with centers, variance, and outcome correlations'
    )

    # Create indexes for segment_definitions
    op.create_index('ix_segment_definitions_axis', 'segment_definitions', ['axis_id'])
    op.create_index('ix_segment_definitions_name', 'segment_definitions', ['segment_name'])
    op.create_index('ix_segment_definitions_ltv_corr', 'segment_definitions', ['ltv_correlation'])

    # Table 4: Player Segment Memberships
    op.create_table(
        'player_segment_memberships',
        sa.Column('membership_id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('player_id', sa.String(100), nullable=False, index=True),
        sa.Column('game_id', sa.String(100), nullable=False, index=True),
        sa.Column('segment_id', postgresql.UUID(as_uuid=True), nullable=False),

        # Membership properties
        sa.Column('membership_strength', sa.Float, nullable=False,
                  comment='Fuzzy membership 0.0-1.0 (closer to center = higher strength)'),

        # Player's position relative to segment center
        sa.Column('position_offset', postgresql.JSONB, nullable=False,
                  comment='{"monthly_spend": -367, "purchase_frequency": +0.3} - offset from center'),
        sa.Column('distance_from_center', sa.Float, nullable=False,
                  comment='Mahalanobis distance in normalized space'),

        # Context-aware positions (optional)
        sa.Column('contextual_positions', postgresql.JSONB, nullable=True,
                  comment='{"weekday": {...}, "weekend": {...}} if applicable'),

        # Tracking
        sa.Column('last_updated', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('confidence', sa.Float, nullable=True,
                  comment='Confidence in this membership based on data quantity'),

        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),

        sa.ForeignKeyConstraint(['segment_id'], ['segment_definitions.segment_id'],
                                ondelete='CASCADE'),
        sa.UniqueConstraint('player_id', 'game_id', 'segment_id', name='uq_player_game_segment'),

        comment='Player fuzzy segment memberships with position tracking'
    )

    # Create indexes for player_segment_memberships
    op.create_index('ix_player_memberships_player_game', 'player_segment_memberships',
                    ['player_id', 'game_id'])
    op.create_index('ix_player_memberships_segment', 'player_segment_memberships', ['segment_id'])
    op.create_index('ix_player_memberships_updated', 'player_segment_memberships', ['last_updated'])
    op.create_index('ix_player_memberships_strength', 'player_segment_memberships', ['membership_strength'])

    # Table 5: Player Behavioral Profiles (Enhanced)
    # Add columns to existing behavioral_profiles table for unified system
    op.add_column('behavioral_profiles',
                  sa.Column('primary_segments', postgresql.JSONB, nullable=True,
                           comment='{"monetization": "whale", "temporal": "weekend_concentrator"}'))
    op.add_column('behavioral_profiles',
                  sa.Column('all_memberships_summary', postgresql.JSONB, nullable=True,
                           comment='Summary of all segment memberships with strengths'))
    op.add_column('behavioral_profiles',
                  sa.Column('total_axes_covered', sa.Integer, nullable=True,
                           comment='Number of axes player has been segmented on'))
    op.add_column('behavioral_profiles',
                  sa.Column('variance_coverage', sa.Float, nullable=True,
                           comment='Percentage of player variance explained by segments'))
    op.add_column('behavioral_profiles',
                  sa.Column('ai_context_segments', postgresql.JSONB, nullable=True,
                           comment='Top-7 segments for AI optimization'))
    op.add_column('behavioral_profiles',
                  sa.Column('ai_context_string', sa.Text, nullable=True,
                           comment='Space-separated segment names for AI prompts'))

    # Create migration tracking table
    op.create_table(
        'segmentation_migration_tracking',
        sa.Column('migration_id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('migration_name', sa.String(100), nullable=False),
        sa.Column('game_id', sa.String(100), nullable=True),
        sa.Column('players_migrated', sa.Integer, nullable=False, server_default='0'),
        sa.Column('players_total', sa.Integer, nullable=True),
        sa.Column('migration_status', sa.String(20), nullable=False, server_default='pending',
                  comment='pending, in_progress, completed, failed'),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),

        comment='Tracks progress of baseline-to-segment migration'
    )


def downgrade():
    """Rollback unified segmentation schema"""

    # Drop migration tracking table
    op.drop_table('segmentation_migration_tracking')

    # Remove columns from behavioral_profiles
    op.drop_column('behavioral_profiles', 'ai_context_string')
    op.drop_column('behavioral_profiles', 'ai_context_segments')
    op.drop_column('behavioral_profiles', 'variance_coverage')
    op.drop_column('behavioral_profiles', 'total_axes_covered')
    op.drop_column('behavioral_profiles', 'all_memberships_summary')
    op.drop_column('behavioral_profiles', 'primary_segments')

    # Drop main tables (in reverse order due to foreign keys)
    op.drop_table('player_segment_memberships')
    op.drop_table('segment_definitions')
    op.drop_table('behavioral_axes')
    op.drop_table('game_behavioral_taxonomy')
