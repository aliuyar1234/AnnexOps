"""Create logging collector tables

Revision ID: 006
Revises: 005
Create Date: 2025-12-25
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create log_api_keys and decision_logs tables for Module F (Logging Collector)."""
    # Create log_api_keys table
    op.create_table(
        "log_api_keys",
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
        sa.Column("key_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
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

    op.create_index("idx_log_api_keys_version_id", "log_api_keys", ["version_id"])
    op.create_index("idx_log_api_keys_created_by", "log_api_keys", ["created_by"])
    op.create_index("idx_log_api_keys_revoked_at", "log_api_keys", ["revoked_at"])

    # Keep updated_at consistent via trigger (reuses update_updated_at_column() from migration 003)
    op.execute(
        """
        CREATE TRIGGER update_log_api_keys_updated_at
        BEFORE UPDATE ON log_api_keys
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
        """
    )

    # Create decision_logs table
    op.create_table(
        "decision_logs",
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
        sa.Column("event_id", sa.String(255), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_json", postgresql.JSONB, nullable=False),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
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

    op.create_index("idx_logs_version_time", "decision_logs", ["version_id", "event_time"])
    op.create_index("idx_logs_event_id", "decision_logs", ["version_id", "event_id"], unique=True)
    op.create_index("idx_logs_ingested", "decision_logs", ["ingested_at"])


def downgrade() -> None:
    """Drop logging collector tables."""
    op.execute("DROP TRIGGER IF EXISTS update_log_api_keys_updated_at ON log_api_keys")
    op.drop_table("decision_logs")
    op.drop_table("log_api_keys")
