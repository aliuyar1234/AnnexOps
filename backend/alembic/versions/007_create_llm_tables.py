"""Create LLM Assist tables

Revision ID: 007
Revises: 006
Create Date: 2025-12-28
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create llm_interactions table for Module G (LLM Assist)."""
    op.create_table(
        "llm_interactions",
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
            nullable=False,
        ),
        sa.Column(
            "selected_evidence_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("response", sa.Text(), nullable=False),
        sa.Column(
            "cited_evidence_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "strict_mode",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "duration_ms",
            sa.Integer(),
            nullable=False,
            server_default="0",
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

    op.create_index("idx_llm_version", "llm_interactions", ["version_id"])
    op.create_index("idx_llm_section", "llm_interactions", ["section_key"])
    op.create_index("idx_llm_user", "llm_interactions", ["user_id"])
    op.create_index("idx_llm_created", "llm_interactions", ["created_at"])


def downgrade() -> None:
    """Drop llm_interactions table."""
    op.drop_index("idx_llm_created", table_name="llm_interactions")
    op.drop_index("idx_llm_user", table_name="llm_interactions")
    op.drop_index("idx_llm_section", table_name="llm_interactions")
    op.drop_index("idx_llm_version", table_name="llm_interactions")
    op.drop_table("llm_interactions")
