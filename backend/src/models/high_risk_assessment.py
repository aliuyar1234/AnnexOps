"""High-risk assessment model for AI system evaluation."""

from sqlalchemy import Column, ForeignKey, Index, Integer, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from src.models.base import BaseModel
from src.models.enums import AssessmentResult


class HighRiskAssessment(BaseModel):
    """High-risk assessment entity for evaluating AI systems.

    Stores completed assessments from the high-risk wizard with
    answers, scores, and result labels.
    """

    __tablename__ = "high_risk_assessments"

    ai_system_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ai_systems.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_label = Column(
        String(50),
        nullable=True,
    )
    answers_json = Column(
        JSONB,
        nullable=False,
    )
    result_label = Column(
        SQLEnum(
            AssessmentResult,
            name="assessment_result",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    score = Column(
        Integer,
        nullable=False,
    )
    notes = Column(
        Text,
        nullable=True,
    )
    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    ai_system = relationship(
        "AISystem",
        back_populates="assessments",
    )
    creator = relationship(
        "User",
        backref="created_assessments",
        foreign_keys=[created_by],
    )

    __table_args__ = (
        Index("idx_assessments_result", "result_label"),
        Index("idx_assessments_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<HighRiskAssessment(id={self.id}, result={self.result_label})>"
