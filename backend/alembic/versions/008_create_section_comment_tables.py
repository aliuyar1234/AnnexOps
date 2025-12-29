"""Create section comment tables

Revision ID: 008
Revises: 007
Create Date: 2025-12-29
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create section_comments table for section review UX."""
    op.create_table(
        "section_comments",
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
        sa.Column("section_key", sa.String(length=50), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("comment", sa.Text(), nullable=False),
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

    op.create_index(
        "idx_section_comments_version_section",
        "section_comments",
        ["version_id", "section_key"],
    )
    op.create_index(
        "idx_section_comments_version",
        "section_comments",
        ["version_id"],
    )
    op.create_index(
        "idx_section_comments_section",
        "section_comments",
        ["section_key"],
    )
    op.create_index(
        "idx_section_comments_user",
        "section_comments",
        ["user_id"],
    )
    op.create_index(
        "idx_section_comments_created",
        "section_comments",
        ["created_at"],
    )


def downgrade() -> None:
    """Drop section_comments table."""
    op.drop_index("idx_section_comments_created", table_name="section_comments")
    op.drop_index("idx_section_comments_user", table_name="section_comments")
    op.drop_index("idx_section_comments_section", table_name="section_comments")
    op.drop_index("idx_section_comments_version", table_name="section_comments")
    op.drop_index(
        "idx_section_comments_version_section",
        table_name="section_comments",
    )
    op.drop_table("section_comments")

