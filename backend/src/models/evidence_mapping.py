"""Evidence Mapping model."""
from sqlalchemy import Column, String, Text, ForeignKey, Enum as SQLEnum, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from src.models.base import BaseModel
from src.models.enums import MappingTargetType, MappingStrength


class EvidenceMapping(BaseModel):
    """Evidence mapping entity linking evidence to system version targets.

    Junction table connecting evidence items to specific parts of system versions.
    The target_type and target_key identify what the evidence is mapped to:
    - section: target_key = "ANNEX4.RISK_MANAGEMENT"
    - field: target_key = "hr_use_case_type"
    - requirement: target_key = "REQ_123"

    The strength field indicates how strong the evidence connection is.
    """

    __tablename__ = "evidence_mappings"

    evidence_id = Column(
        UUID(as_uuid=True),
        ForeignKey("evidence_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("system_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    target_type = Column(
        SQLEnum(MappingTargetType, name="mapping_target_type", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False
    )
    target_key = Column(
        String(100),
        nullable=False
    )
    strength = Column(
        SQLEnum(MappingStrength, name="mapping_strength", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=True
    )
    notes = Column(
        Text,
        nullable=True
    )
    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )

    # Relationships
    evidence_item = relationship(
        "EvidenceItem",
        back_populates="mappings"
    )
    system_version = relationship(
        "SystemVersion",
        back_populates="evidence_mappings"
    )
    creator = relationship(
        "User",
        foreign_keys=[created_by]
    )

    __table_args__ = (
        # Unique constraint: one evidence item can only be mapped once to a specific target
        UniqueConstraint(
            "evidence_id",
            "version_id",
            "target_type",
            "target_key",
            name="uq_evidence_version_target"
        ),
        # Composite index for target lookups
        {"schema": None},
    )

    def __repr__(self) -> str:
        return f"<EvidenceMapping(id={self.id}, evidence_id={self.evidence_id}, target={self.target_type}:{self.target_key})>"
