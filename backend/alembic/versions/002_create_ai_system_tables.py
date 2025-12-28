"""Create AI system tables

Revision ID: 002
Revises: 001
Create Date: 2025-12-25

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create AI system registry tables."""
    # Create enum types for Module B
    op.execute("""
        CREATE TYPE hr_use_case_type AS ENUM (
            'recruitment_screening', 'application_filtering', 'candidate_matching',
            'performance_evaluation', 'employee_monitoring', 'task_allocation',
            'promotion_termination', 'other_hr'
        )
    """)
    op.execute("""
        CREATE TYPE deployment_type AS ENUM ('saas', 'onprem', 'hybrid')
    """)
    op.execute("""
        CREATE TYPE decision_influence AS ENUM ('assistive', 'semi_automated', 'automated')
    """)
    op.execute("""
        CREATE TYPE assessment_result AS ENUM ('likely_high_risk', 'unclear', 'likely_not')
    """)

    # Add new audit actions to existing enum
    op.execute("""
        ALTER TYPE audit_action ADD VALUE IF NOT EXISTS 'ai_system.create';
    """)
    op.execute("""
        ALTER TYPE audit_action ADD VALUE IF NOT EXISTS 'ai_system.update';
    """)
    op.execute("""
        ALTER TYPE audit_action ADD VALUE IF NOT EXISTS 'ai_system.delete';
    """)
    op.execute("""
        ALTER TYPE audit_action ADD VALUE IF NOT EXISTS 'assessment.create';
    """)
    op.execute("""
        ALTER TYPE audit_action ADD VALUE IF NOT EXISTS 'attachment.upload';
    """)
    op.execute("""
        ALTER TYPE audit_action ADD VALUE IF NOT EXISTS 'attachment.delete';
    """)

    # Create ai_systems table
    op.create_table(
        "ai_systems",
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
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "hr_use_case_type",
            postgresql.ENUM(
                "recruitment_screening",
                "application_filtering",
                "candidate_matching",
                "performance_evaluation",
                "employee_monitoring",
                "task_allocation",
                "promotion_termination",
                "other_hr",
                name="hr_use_case_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("intended_purpose", sa.Text, nullable=False),
        sa.Column(
            "deployment_type",
            postgresql.ENUM("saas", "onprem", "hybrid", name="deployment_type", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "decision_influence",
            postgresql.ENUM(
                "assistive",
                "semi_automated",
                "automated",
                name="decision_influence",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "owner_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("contact_name", sa.String(255), nullable=True),
        sa.Column("contact_email", sa.String(255), nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
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
    op.create_index("idx_ai_systems_org_id", "ai_systems", ["org_id"])
    op.create_index("idx_ai_systems_org_name", "ai_systems", ["org_id", "name"], unique=True)
    op.create_index("idx_ai_systems_owner", "ai_systems", ["owner_user_id"])
    op.create_index("idx_ai_systems_use_case", "ai_systems", ["hr_use_case_type"])

    # Create high_risk_assessments table
    op.create_table(
        "high_risk_assessments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "ai_system_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ai_systems.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_label", sa.String(50), nullable=True),
        sa.Column("answers_json", postgresql.JSONB, nullable=False),
        sa.Column(
            "result_label",
            postgresql.ENUM(
                "likely_high_risk",
                "unclear",
                "likely_not",
                name="assessment_result",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("score", sa.Integer, nullable=False),
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
    op.create_index("idx_assessments_system", "high_risk_assessments", ["ai_system_id"])
    op.create_index("idx_assessments_result", "high_risk_assessments", ["result_label"])
    op.create_index("idx_assessments_created", "high_risk_assessments", ["created_at"])
    op.create_index("idx_assessments_created_by", "high_risk_assessments", ["created_by"])

    # Create system_attachments table
    op.create_table(
        "system_attachments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "ai_system_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ai_systems.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("storage_uri", sa.String(500), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("file_size", sa.BigInteger, nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column(
            "uploaded_by",
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
    op.create_index("idx_attachments_system", "system_attachments", ["ai_system_id"])
    op.create_index("idx_attachments_checksum", "system_attachments", ["checksum_sha256"])
    op.create_index("idx_attachments_uploaded_by", "system_attachments", ["uploaded_by"])


def downgrade() -> None:
    """Drop AI system registry tables."""
    # Drop tables
    op.drop_table("system_attachments")
    op.drop_table("high_risk_assessments")
    op.drop_table("ai_systems")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS assessment_result")
    op.execute("DROP TYPE IF EXISTS decision_influence")
    op.execute("DROP TYPE IF EXISTS deployment_type")
    op.execute("DROP TYPE IF EXISTS hr_use_case_type")

    # Note: Cannot remove values from audit_action enum in PostgreSQL
    # They will remain but unused after downgrade
