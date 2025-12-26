"""Annex Section model for Annex IV technical documentation."""
from sqlalchemy import Column, String, Numeric, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship

from src.models.base import BaseModel


class AnnexSection(BaseModel):
    """Annex Section entity for storing Annex IV section content.

    Each section represents one of the 12 Annex IV documentation sections
    and is associated with a specific system version.
    """

    __tablename__ = "annex_sections"

    version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("system_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    section_key = Column(
        String(50),
        nullable=False,
    )
    content = Column(
        JSONB,
        nullable=False,
        server_default="{}",
    )
    completeness_score = Column(
        Numeric(5, 2),
        nullable=False,
        server_default="0",
    )
    evidence_refs = Column(
        ARRAY(UUID(as_uuid=True)),
        nullable=False,
        server_default="{}",
    )
    llm_assisted = Column(
        Boolean,
        nullable=False,
        server_default="false",
    )
    last_edited_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    system_version = relationship(
        "SystemVersion",
        backref="annex_sections",
    )
    editor = relationship(
        "User",
        foreign_keys=[last_edited_by],
    )

    def __repr__(self) -> str:
        return f"<AnnexSection(id={self.id}, section_key={self.section_key}, completeness={self.completeness_score})>"
