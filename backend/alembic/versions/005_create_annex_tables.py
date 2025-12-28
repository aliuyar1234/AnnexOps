"""Create annex tables

Revision ID: 005
Revises: 004
Create Date: 2025-12-25

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create annex_sections and exports tables for Module E (Annex IV Generator)."""
    # Add new audit actions to existing enum for annex operations
    op.execute("""
        ALTER TYPE audit_action ADD VALUE IF NOT EXISTS 'section.update';
    """)
    op.execute("""
        ALTER TYPE audit_action ADD VALUE IF NOT EXISTS 'export.create';
    """)

    # Create annex_sections table
    op.create_table(
        "annex_sections",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("system_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("section_key", sa.String(50), nullable=False),
        sa.Column("content", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("completeness_score", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column(
            "evidence_refs",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("llm_assisted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "last_edited_by",
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

    # Create indexes for annex_sections
    op.create_index("idx_annex_section_version", "annex_sections", ["version_id"])
    op.create_index("idx_annex_section_key", "annex_sections", ["section_key"])

    # Create GIN index for evidence_refs array
    op.create_index(
        "idx_annex_section_evidence_refs",
        "annex_sections",
        ["evidence_refs"],
        postgresql_using="gin",
    )

    # Create unique constraint on (version_id, section_key)
    op.create_index(
        "idx_annex_section_version_key",
        "annex_sections",
        ["version_id", "section_key"],
        unique=True,
    )

    # Create exports table
    op.create_table(
        "exports",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("system_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("export_type", sa.String(20), nullable=False, server_default="full"),
        sa.Column("snapshot_hash", sa.String(64), nullable=False),
        sa.Column("storage_uri", sa.String(500), nullable=False),
        sa.Column("file_size", sa.BigInteger, nullable=False),
        sa.Column("include_diff", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "compare_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("system_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("completeness_score", sa.Numeric(5, 2), nullable=False),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=False,
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

    # Create indexes for exports
    op.create_index("idx_export_version", "exports", ["version_id"])
    op.create_index("idx_export_type", "exports", ["export_type"])
    op.create_index("idx_export_hash", "exports", ["snapshot_hash"])
    op.create_index("idx_export_created_by", "exports", ["created_by"])

    # Add triggers for updated_at timestamp (reuse existing function from previous migrations)
    op.execute("""
        CREATE TRIGGER update_annex_sections_updated_at
        BEFORE UPDATE ON annex_sections
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)

    op.execute("""
        CREATE TRIGGER update_exports_updated_at
        BEFORE UPDATE ON exports
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    """Drop annex tables."""
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS update_exports_updated_at ON exports")
    op.execute("DROP TRIGGER IF EXISTS update_annex_sections_updated_at ON annex_sections")

    # Drop tables
    op.drop_table("exports")
    op.drop_table("annex_sections")

    # Note: Cannot remove values from audit_action enum in PostgreSQL
    # They will remain but unused after downgrade
