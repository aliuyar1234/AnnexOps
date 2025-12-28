"""Create evidence tables

Revision ID: 004
Revises: 003
Create Date: 2025-12-25

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create evidence item and evidence mapping tables for Module D."""
    # Create enum types
    op.execute("""
        CREATE TYPE evidence_type AS ENUM ('upload', 'url', 'git', 'ticket', 'note')
    """)

    op.execute("""
        CREATE TYPE classification AS ENUM ('public', 'internal', 'confidential')
    """)

    op.execute("""
        CREATE TYPE mapping_target_type AS ENUM ('section', 'field', 'requirement')
    """)

    op.execute("""
        CREATE TYPE mapping_strength AS ENUM ('weak', 'medium', 'strong')
    """)

    # Add new audit actions to existing enum for evidence operations
    op.execute("""
        ALTER TYPE audit_action ADD VALUE IF NOT EXISTS 'evidence.create';
    """)
    op.execute("""
        ALTER TYPE audit_action ADD VALUE IF NOT EXISTS 'evidence.update';
    """)
    op.execute("""
        ALTER TYPE audit_action ADD VALUE IF NOT EXISTS 'evidence.delete';
    """)
    op.execute("""
        ALTER TYPE audit_action ADD VALUE IF NOT EXISTS 'mapping.create';
    """)
    op.execute("""
        ALTER TYPE audit_action ADD VALUE IF NOT EXISTS 'mapping.delete';
    """)

    # Create evidence_items table
    op.create_table(
        "evidence_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "type",
            postgresql.ENUM(
                "upload", "url", "git", "ticket", "note", name="evidence_type", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column(
            "classification",
            postgresql.ENUM(
                "public", "internal", "confidential", name="classification", create_type=False
            ),
            nullable=False,
            server_default="internal",
        ),
        sa.Column("type_metadata", postgresql.JSONB, nullable=False),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )

    # Create indexes for evidence_items
    op.create_index("idx_evidence_org", "evidence_items", ["org_id"])
    op.create_index("idx_evidence_type", "evidence_items", ["type"])
    op.create_index("idx_evidence_tags", "evidence_items", ["tags"], postgresql_using="gin")
    op.create_index("idx_evidence_classification", "evidence_items", ["classification"])

    # Create full-text search index on title and description
    op.execute("""
        CREATE INDEX idx_evidence_search ON evidence_items
        USING gin(to_tsvector('english', title || ' ' || COALESCE(description, '')))
    """)

    # Create evidence_mappings table
    op.create_table(
        "evidence_mappings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "evidence_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("evidence_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("system_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_type",
            postgresql.ENUM(
                "section", "field", "requirement", name="mapping_target_type", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("target_key", sa.String(100), nullable=False),
        sa.Column(
            "strength",
            postgresql.ENUM("weak", "medium", "strong", name="mapping_strength", create_type=False),
            nullable=True,
        ),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )

    # Create indexes for evidence_mappings
    op.create_index("idx_mapping_evidence", "evidence_mappings", ["evidence_id"])
    op.create_index("idx_mapping_version", "evidence_mappings", ["version_id"])
    op.create_index("idx_mapping_target", "evidence_mappings", ["target_type", "target_key"])

    # Create unique constraint index
    op.create_index(
        "idx_mapping_unique",
        "evidence_mappings",
        ["evidence_id", "version_id", "target_type", "target_key"],
        unique=True,
    )

    # Add triggers for updated_at timestamp (reuse existing function from previous migrations)
    op.execute("""
        CREATE TRIGGER update_evidence_items_updated_at
        BEFORE UPDATE ON evidence_items
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)

    op.execute("""
        CREATE TRIGGER update_evidence_mappings_updated_at
        BEFORE UPDATE ON evidence_mappings
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    """Drop evidence tables."""
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS update_evidence_mappings_updated_at ON evidence_mappings")
    op.execute("DROP TRIGGER IF EXISTS update_evidence_items_updated_at ON evidence_items")

    # Drop tables
    op.drop_table("evidence_mappings")
    op.drop_table("evidence_items")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS mapping_strength")
    op.execute("DROP TYPE IF EXISTS mapping_target_type")
    op.execute("DROP TYPE IF EXISTS classification")
    op.execute("DROP TYPE IF EXISTS evidence_type")

    # Note: Cannot remove values from audit_action enum in PostgreSQL
    # They will remain but unused after downgrade
