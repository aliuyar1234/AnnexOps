"""Create system version tables

Revision ID: 003
Revises: 002
Create Date: 2025-12-25

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create system version tables for Module C."""
    # Create enum type for version status
    op.execute("""
        CREATE TYPE version_status AS ENUM ('draft', 'review', 'approved')
    """)

    # Add new audit actions to existing enum for version operations
    op.execute("""
        ALTER TYPE audit_action ADD VALUE IF NOT EXISTS 'version.create';
    """)
    op.execute("""
        ALTER TYPE audit_action ADD VALUE IF NOT EXISTS 'version.update';
    """)
    op.execute("""
        ALTER TYPE audit_action ADD VALUE IF NOT EXISTS 'version.status_change';
    """)
    op.execute("""
        ALTER TYPE audit_action ADD VALUE IF NOT EXISTS 'version.delete';
    """)

    # Create system_versions table
    op.create_table(
        'system_versions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('ai_system_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('ai_systems.id', ondelete='CASCADE'), nullable=False),
        sa.Column('label', sa.String(50), nullable=False),
        sa.Column('status', postgresql.ENUM('draft', 'review', 'approved', name='version_status', create_type=False), nullable=False, server_default='draft'),
        sa.Column('release_date', sa.Date, nullable=True),
        sa.Column('snapshot_hash', sa.String(64), nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('approved_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('approved_at', sa.Date, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    )

    # Create indexes
    op.create_index('idx_versions_system', 'system_versions', ['ai_system_id'])
    op.create_index('idx_versions_system_label', 'system_versions', ['ai_system_id', 'label'], unique=True)
    op.create_index('idx_versions_status', 'system_versions', ['status'])
    op.create_index('idx_versions_snapshot', 'system_versions', ['snapshot_hash'])

    # Add trigger for updated_at timestamp
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER update_system_versions_updated_at
        BEFORE UPDATE ON system_versions
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    """Drop system version tables."""
    # Drop trigger and function
    op.execute('DROP TRIGGER IF EXISTS update_system_versions_updated_at ON system_versions')
    op.execute('DROP FUNCTION IF EXISTS update_updated_at_column()')

    # Drop table
    op.drop_table('system_versions')

    # Drop enum type
    op.execute('DROP TYPE IF EXISTS version_status')

    # Note: Cannot remove values from audit_action enum in PostgreSQL
    # They will remain but unused after downgrade
