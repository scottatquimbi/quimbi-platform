"""Add PII tokenization vault tables

Revision ID: 005
Revises: scaler_params_001
Create Date: 2025-10-14

Creates tables for PII protection via tokenization:
- pii_token_vault: Encrypted storage of PII-to-token mappings
- pii_access_audit: Audit trail of PII access for compliance

Compliance: GDPR, CCPA (right to be forgotten)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, BYTEA, UUID
import uuid


# revision identifiers
revision = 'pii_tokenization_001'
down_revision = 'scaler_params_001'
branch_labels = None
depends_on = None


def upgrade():
    # PII Token Vault - Encrypted storage
    op.create_table(
        'pii_token_vault',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('token', sa.String(64), nullable=False, unique=True, index=True,
                  comment='Deterministic token (safe to store/log)'),
        sa.Column('encrypted_pii', BYTEA, nullable=True,
                  comment='Fernet-encrypted original value (NULL after deletion)'),
        sa.Column('metadata', JSONB, nullable=True,
                  comment='Context: game_id, source, etc.'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False, index=True,
                  comment='Token expiration (for rotation)'),
        sa.Column('access_count', sa.Integer, default=0, nullable=False,
                  comment='Number of detokenizations'),
        sa.Column('last_accessed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True,
                  comment='When PII was deleted (GDPR/CCPA)'),
        sa.Column('deletion_reason', sa.String(100), nullable=True),

        comment='Encrypted vault for PII tokenization (GDPR/CCPA compliant)'
    )

    # Access Audit Trail - Compliance requirement
    op.create_table(
        'pii_access_audit',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('token', sa.String(64), nullable=False, index=True,
                  comment='Token that was accessed'),
        sa.Column('accessed_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
        sa.Column('access_reason', sa.String(100), nullable=False,
                  comment='Why PII was accessed: customer_support, analytics, etc.'),
        sa.Column('service', sa.String(50), nullable=False,
                  comment='Which service accessed: api, support_tool, etc.'),
        sa.Column('user_id', sa.String(100), nullable=True,
                  comment='User who accessed (if applicable)'),
        sa.Column('ip_address', sa.String(45), nullable=True,
                  comment='Source IP (for security)'),

        # Indexes for audit queries
        sa.Index('idx_pii_audit_token_date', 'token', 'accessed_at'),
        sa.Index('idx_pii_audit_service_date', 'service', 'accessed_at'),

        comment='Audit trail for PII access (compliance requirement)'
    )

    # Token expiration cleanup function (PostgreSQL)
    # Automatically delete expired tokens
    op.execute("""
        CREATE OR REPLACE FUNCTION cleanup_expired_tokens()
        RETURNS void AS $$
        BEGIN
            DELETE FROM pii_token_vault
            WHERE expires_at < NOW() - INTERVAL '90 days'
              AND encrypted_pii IS NULL;  -- Only delete if PII already removed
        END;
        $$ LANGUAGE plpgsql;
    """)


def downgrade():
    # Drop function
    op.execute("DROP FUNCTION IF EXISTS cleanup_expired_tokens();")

    # Drop tables
    op.drop_table('pii_access_audit')
    op.drop_table('pii_token_vault')
