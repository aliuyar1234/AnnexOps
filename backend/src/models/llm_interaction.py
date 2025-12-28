"""LLM interaction audit log model (Module G)."""

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import relationship

from src.models.base import BaseModel


class LlmInteraction(BaseModel):
    """Audit log record of an LLM draft/gap interaction."""

    __tablename__ = "llm_interactions"

    version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("system_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    section_key = Column(
        String(50),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
        index=True,
    )
    selected_evidence_ids = Column(
        ARRAY(UUID(as_uuid=True)),
        nullable=False,
        server_default="{}",
    )
    prompt = Column(
        Text,
        nullable=False,
    )
    response = Column(
        Text,
        nullable=False,
    )
    cited_evidence_ids = Column(
        ARRAY(UUID(as_uuid=True)),
        nullable=False,
        server_default="{}",
    )
    model = Column(
        String(100),
        nullable=False,
    )
    input_tokens = Column(
        Integer,
        nullable=False,
        server_default="0",
    )
    output_tokens = Column(
        Integer,
        nullable=False,
        server_default="0",
    )
    strict_mode = Column(
        Boolean,
        nullable=False,
        server_default="false",
    )
    duration_ms = Column(
        Integer,
        nullable=False,
        server_default="0",
    )

    system_version = relationship(
        "SystemVersion",
        backref="llm_interactions",
    )
    user = relationship(
        "User",
        foreign_keys=[user_id],
    )

    def __repr__(self) -> str:
        return (
            f"<LlmInteraction(id={self.id}, version_id={self.version_id}, "
            f"section_key={self.section_key}, strict_mode={self.strict_mode})>"
        )
