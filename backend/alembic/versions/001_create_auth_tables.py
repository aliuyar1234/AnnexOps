"""Create auth tables

Revision ID: 001
Revises:
Create Date: 2025-12-25

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create authentication tables."""
    # Create UUID extension if not exists
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # Create enum types
    op.execute("""
        CREATE TYPE user_role AS ENUM ('admin', 'editor', 'reviewer', 'viewer')
    """)
    op.execute("""
        CREATE TYPE audit_action AS ENUM (
            'organization.create', 'organization.update',
            'user.create', 'user.update', 'user.delete', 'user.role_change',
            'user.login', 'user.logout', 'user.lockout',
            'invitation.create', 'invitation.accept', 'invitation.expire', 'invitation.revoke'
        )
    """)

    # Create organizations table
    op.create_table(
        'organizations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('name', sa.String(255), nullable=False, unique=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.CheckConstraint('LENGTH(name) > 0', name='organization_name_not_empty')
    )
    op.create_index('idx_organizations_name', 'organizations', ['name'], unique=True)

    # Create users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('role', postgresql.ENUM('admin', 'editor', 'reviewer', 'viewer', name='user_role', create_type=False), nullable=False, server_default='viewer'),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('failed_login_attempts', sa.Integer, nullable=False, server_default='0'),
        sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('idx_users_org_id', 'users', ['org_id'])
    op.create_index('idx_users_org_email', 'users', ['org_id', 'email'], unique=True)

    # Create invitations table
    op.create_table(
        'invitations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('role', postgresql.ENUM('admin', 'editor', 'reviewer', 'viewer', name='user_role', create_type=False), nullable=False),
        sa.Column('token_hash', sa.String(255), nullable=False, unique=True),
        sa.Column('invited_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('idx_invitations_token_hash', 'invitations', ['token_hash'], unique=True)
    op.create_index('idx_invitations_org_email', 'invitations', ['org_id', 'email'])
    op.create_index('idx_invitations_expires_at', 'invitations', ['expires_at'])

    # Create audit_events table
    op.create_table(
        'audit_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('action', postgresql.ENUM(
            'organization.create', 'organization.update',
            'user.create', 'user.update', 'user.delete', 'user.role_change',
            'user.login', 'user.logout', 'user.lockout',
            'invitation.create', 'invitation.accept', 'invitation.expire', 'invitation.revoke',
            name='audit_action', create_type=False
        ), nullable=False),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('diff_json', postgresql.JSONB, nullable=True),
        sa.Column('ip_address', postgresql.INET, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('idx_audit_events_org_id', 'audit_events', ['org_id'])
    op.create_index('idx_audit_events_user_id', 'audit_events', ['user_id'])
    op.create_index('idx_audit_events_entity', 'audit_events', ['entity_type', 'entity_id'])
    op.create_index('idx_audit_events_created_at', 'audit_events', ['created_at'])

    # Create trigger to prevent UPDATE/DELETE on audit_events
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_audit_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'Audit events cannot be modified or deleted';
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER prevent_audit_update
        BEFORE UPDATE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION prevent_audit_modification();
    """)
    op.execute("""
        CREATE TRIGGER prevent_audit_delete
        BEFORE DELETE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION prevent_audit_modification();
    """)


def downgrade() -> None:
    """Drop authentication tables."""
    # Drop triggers first
    op.execute('DROP TRIGGER IF EXISTS prevent_audit_delete ON audit_events')
    op.execute('DROP TRIGGER IF EXISTS prevent_audit_update ON audit_events')
    op.execute('DROP FUNCTION IF EXISTS prevent_audit_modification()')

    # Drop tables
    op.drop_table('audit_events')
    op.drop_table('invitations')
    op.drop_table('users')
    op.drop_table('organizations')

    # Drop enum types
    op.execute('DROP TYPE IF EXISTS audit_action')
    op.execute('DROP TYPE IF EXISTS user_role')
