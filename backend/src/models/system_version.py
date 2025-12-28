"""System Version model for AI system versioning."""
from sqlalchemy import Column, Date, ForeignKey, Index, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.models.base import BaseModel
from src.models.enums import VersionStatus


class SystemVersion(BaseModel):
    """System Version entity for tracking AI system releases.

    Represents a specific release/version of an AI system for
    documentation and compliance tracking purposes.
    """

    __tablename__ = "system_versions"

    ai_system_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ai_systems.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    label = Column(
        String(50),
        nullable=False,
    )
    status = Column(
        SQLEnum(VersionStatus, name="version_status", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=VersionStatus.DRAFT,
        index=True,
    )
    release_date = Column(
        Date,
        nullable=True,
    )
    snapshot_hash = Column(
        String(64),
        nullable=True,
        index=True,
    )
    notes = Column(
        Text,
        nullable=True,
    )
    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at = Column(
        Date,
        nullable=True,
    )

    # Relationships
    ai_system = relationship(
        "AISystem",
        backref="versions",
    )
    creator = relationship(
        "User",
        foreign_keys=[created_by],
        backref="created_versions",
    )
    approver = relationship(
        "User",
        foreign_keys=[approved_by],
        backref="approved_versions",
    )
    evidence_mappings = relationship(
        "EvidenceMapping",
        back_populates="system_version",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_versions_system", "ai_system_id"),
        Index("idx_versions_system_label", "ai_system_id", "label", unique=True),
        Index("idx_versions_status", "status"),
        Index("idx_versions_snapshot", "snapshot_hash"),
    )

    def __repr__(self) -> str:
        return f"<SystemVersion(id={self.id}, label={self.label}, status={self.status})>"
