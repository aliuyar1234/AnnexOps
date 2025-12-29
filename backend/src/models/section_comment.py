"""SectionComment model for per-section review comments."""

from sqlalchemy import Column, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.models.base import BaseModel


class SectionComment(BaseModel):
    """Review comment attached to a specific Annex IV section within a version."""

    __tablename__ = "section_comments"

    version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("system_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    section_key = Column(String(50), nullable=False, index=True)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    comment = Column(Text, nullable=False)

    author = relationship("User", foreign_keys=[user_id])

