"""Add API keys table for authentication

Revision ID: 006
Revises: pii_tokenization_001
Create Date: 2025-10-14

Creates table for API key authentication and authorization.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, UUID
import uuid


# revision identifiers
revision = 'api_keys_001'
down_revision = 'pii_tokenization_001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'api_keys',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('key_hash', sa.String(128), nullable=False, unique=True, index=True,
                  comment='Bcrypt hash of API key (never store plaintext)'),
        sa.Column('name', sa.String(100), nullable=False,
                  comment='Human-readable key name'),
        sa.Column('scopes', ARRAY(sa.String), nullable=False, default=[],
                  comment='Permission scopes: read, write, admin'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('usage_count', sa.Integer, default=0, nullable=False),
        sa.Column('is_active', sa.Boolean, default=True, nullable=False, index=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revocation_reason', sa.String(200), nullable=True),

        # Rate limiting (per key)
        sa.Column('rate_limit_per_hour', sa.Integer, default=1000, nullable=False),
        sa.Column('rate_limit_remaining', sa.Integer, default=1000, nullable=False),
        sa.Column('rate_limit_reset_at', sa.DateTime(timezone=True), nullable=True),

        comment='API keys for authentication and authorization'
    )

    # Create index for active keys lookup (most common query)
    # Note: Cannot use NOW() in partial index predicate (not IMMUTABLE)
    # Instead, index both columns and let query planner use them
    op.create_index(
        'idx_api_keys_active_unexpired',
        'api_keys',
        ['is_active', 'expires_at']
    )


def downgrade():
    op.drop_index('idx_api_keys_active_unexpired', table_name='api_keys')
    op.drop_table('api_keys')
