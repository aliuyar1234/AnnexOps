"""AI System model for registering HR-AI systems."""
from sqlalchemy import Column, ForeignKey, Index, Integer, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.models.base import BaseModel
from src.models.enums import DecisionInfluence, DeploymentType, HRUseCaseType


class AISystem(BaseModel):
    """AI System entity for EU AI Act compliance registration.

    Represents an HR-AI system registered within an organization that
    needs to be documented for regulatory compliance.
    """

    __tablename__ = "ai_systems"

    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(
        String(255),
        nullable=False,
    )
    description = Column(
        Text,
        nullable=True,
    )
    hr_use_case_type = Column(
        SQLEnum(HRUseCaseType, name="hr_use_case_type", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    intended_purpose = Column(
        Text,
        nullable=False,
    )
    deployment_type = Column(
        SQLEnum(DeploymentType, name="deployment_type", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    decision_influence = Column(
        SQLEnum(DecisionInfluence, name="decision_influence", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    owner_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    contact_name = Column(
        String(255),
        nullable=True,
    )
    contact_email = Column(
        String(255),
        nullable=True,
    )
    version = Column(
        Integer,
        nullable=False,
        default=1,
    )

    # Relationships
    organization = relationship(
        "Organization",
        backref="ai_systems",
    )
    owner = relationship(
        "User",
        backref="owned_systems",
        foreign_keys=[owner_user_id],
    )
    assessments = relationship(
        "HighRiskAssessment",
        back_populates="ai_system",
        cascade="all, delete-orphan",
        order_by="desc(HighRiskAssessment.created_at)",
    )
    attachments = relationship(
        "SystemAttachment",
        back_populates="ai_system",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_ai_systems_org_name", "org_id", "name", unique=True),
        Index("idx_ai_systems_use_case", "hr_use_case_type"),
    )

    def __repr__(self) -> str:
        return f"<AISystem(id={self.id}, name={self.name})>"
