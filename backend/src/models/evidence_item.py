"""Evidence Item model."""
from sqlalchemy import Column, ForeignKey, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import relationship

from src.models.base import BaseModel
from src.models.enums import Classification, EvidenceType


class EvidenceItem(BaseModel):
    """Evidence item entity for storing compliance evidence.

    Evidence items can be of various types (upload, URL, git, ticket, note)
    and are mapped to specific parts of system versions through EvidenceMapping.

    Each evidence type stores its metadata in the type_metadata JSONB column:
    - upload: {file_key, file_size, mime_type, original_filename}
    - url: {url, title, accessed_at}
    - git: {repo_url, commit_hash, branch, file_path}
    - ticket: {ticket_system, ticket_id, ticket_url}
    - note: {content}
    """

    __tablename__ = "evidence_items"

    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    type = Column(
        SQLEnum(EvidenceType, name="evidence_type", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True
    )
    title = Column(
        String(255),
        nullable=False
    )
    description = Column(
        Text,
        nullable=True
    )
    tags = Column(
        ARRAY(Text),
        nullable=False,
        server_default="{}"
    )
    classification = Column(
        SQLEnum(Classification, name="classification", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        server_default="internal",
        index=True
    )
    type_metadata = Column(
        JSONB,
        nullable=False
    )
    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )

    # Relationships
    organization = relationship(
        "Organization",
        back_populates="evidence_items"
    )
    creator = relationship(
        "User",
        foreign_keys=[created_by]
    )
    mappings = relationship(
        "EvidenceMapping",
        back_populates="evidence_item",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<EvidenceItem(id={self.id}, type={self.type}, title={self.title})>"
