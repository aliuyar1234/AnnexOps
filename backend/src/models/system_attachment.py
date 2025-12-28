"""System attachment model for file storage."""

from sqlalchemy import BigInteger, Column, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.models.base import BaseModel


class SystemAttachment(BaseModel):
    """System attachment entity for storing documents.

    Stores metadata for files attached to AI systems, with
    actual file content in S3/MinIO storage.
    """

    __tablename__ = "system_attachments"

    ai_system_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ai_systems.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(
        String(255),
        nullable=False,
    )
    description = Column(
        Text,
        nullable=True,
    )
    storage_uri = Column(
        String(500),
        nullable=False,
    )
    checksum_sha256 = Column(
        String(64),
        nullable=False,
    )
    file_size = Column(
        BigInteger,
        nullable=False,
    )
    mime_type = Column(
        String(100),
        nullable=False,
    )
    uploaded_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    ai_system = relationship(
        "AISystem",
        back_populates="attachments",
    )
    uploader = relationship(
        "User",
        backref="uploaded_attachments",
        foreign_keys=[uploaded_by],
    )

    __table_args__ = (Index("idx_attachments_checksum", "checksum_sha256"),)

    def __repr__(self) -> str:
        return f"<SystemAttachment(id={self.id}, title={self.title})>"
