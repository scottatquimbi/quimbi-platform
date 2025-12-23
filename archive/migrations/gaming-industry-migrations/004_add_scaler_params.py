"""Add scaler_params to multi_axis_segments

Revision ID: 004
Revises: multi_axis_001
Create Date: 2025-10-14

Adds scaler_params column to store StandardScaler mean/scale for correct
fuzzy membership calculation. This fixes the critical bug where player
features were standardized using their own statistics instead of population
statistics.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers
revision = 'scaler_params_001'
down_revision = 'multi_axis_001'
branch_labels = None
depends_on = None


def upgrade():
    # Add scaler_params column to multi_axis_segments
    op.add_column(
        'multi_axis_segments',
        sa.Column(
            'scaler_params',
            JSONB,
            nullable=True,  # Nullable initially for existing rows
            comment='StandardScaler parameters: {"mean": [...], "scale": [...], "feature_names": [...]}'
        )
    )

    # Note: Existing segments will have NULL scaler_params and need rediscovery
    # After this migration, run discovery again to populate scaler_params


def downgrade():
    op.drop_column('multi_axis_segments', 'scaler_params')
