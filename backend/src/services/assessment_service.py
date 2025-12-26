"""Assessment service for high-risk wizard operations."""
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.ai_system import AISystem
from src.models.high_risk_assessment import HighRiskAssessment
from src.models.enums import AssessmentResult, AuditAction
from src.models.user import User
from src.schemas.assessment import AssessmentSubmission
from src.core.wizard_questions import (
    WIZARD_QUESTIONS,
    WIZARD_VERSION,
    ASSESSMENT_DISCLAIMER,
    calculate_score,
    get_result_label,
    get_checklist,
)
from src.services.audit_service import AuditService


class AssessmentService:
    """Service for managing high-risk assessments."""

    def __init__(self, db: AsyncSession):
        """Initialize assessment service.

        Args:
            db: Database session
        """
        self.db = db
        self.audit_service = AuditService(db)

    async def get_system(
        self,
        system_id: UUID,
        org_id: UUID,
    ) -> AISystem:
        """Get AI system by ID with org scoping.

        Args:
            system_id: System ID
            org_id: Organization ID

        Returns:
            AISystem if found

        Raises:
            HTTPException: 404 if not found
        """
        query = (
            select(AISystem)
            .where(AISystem.id == system_id)
            .where(AISystem.org_id == org_id)
        )
        result = await self.db.execute(query)
        system = result.scalar_one_or_none()

        if not system:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="System not found",
            )
        return system

    def get_questions(self) -> dict:
        """Get wizard questions.

        Returns:
            Dict with version and questions list
        """
        return {
            "version": WIZARD_VERSION,
            "questions": WIZARD_QUESTIONS,
        }

    async def submit_assessment(
        self,
        system_id: UUID,
        submission: AssessmentSubmission,
        current_user: User,
    ) -> HighRiskAssessment:
        """Submit a high-risk assessment.

        Args:
            system_id: System ID to assess
            submission: Assessment submission with answers
            current_user: User submitting the assessment

        Returns:
            Created HighRiskAssessment

        Raises:
            HTTPException: 404 if system not found
        """
        # Verify system exists and belongs to user's org
        system = await self.get_system(system_id, current_user.org_id)

        # Calculate score and result
        answers_list = [{"question_id": a.question_id, "answer": a.answer} for a in submission.answers]
        score = calculate_score(answers_list)
        result_label = get_result_label(score)

        # Build answers JSON
        answers_json = {
            "version": WIZARD_VERSION,
            "questions": [
                {
                    "id": a.question_id,
                    "text": next((q["text"] for q in WIZARD_QUESTIONS if q["id"] == a.question_id), ""),
                    "answer": a.answer,
                    "high_risk_indicator": next(
                        (q["high_risk_indicator"] for q in WIZARD_QUESTIONS if q["id"] == a.question_id),
                        False,
                    ),
                }
                for a in submission.answers
            ],
            "completed_at": None,  # Will be set by created_at
        }

        # Create assessment
        assessment = HighRiskAssessment(
            ai_system_id=system.id,
            answers_json=answers_json,
            result_label=AssessmentResult(result_label),
            score=score,
            notes=submission.notes,
            created_by=current_user.id,
        )

        self.db.add(assessment)
        await self.db.flush()

        # Log audit event
        await self.audit_service.log(
            org_id=current_user.org_id,
            user_id=current_user.id,
            action=AuditAction.ASSESSMENT_CREATE,
            entity_type="high_risk_assessment",
            entity_id=assessment.id,
            diff_json={
                "system_id": str(system.id),
                "result": result_label,
                "score": score,
            },
        )

        await self.db.refresh(assessment)
        return assessment

    async def get_assessments(
        self,
        system_id: UUID,
        org_id: UUID,
    ) -> list[HighRiskAssessment]:
        """Get assessment history for a system.

        Args:
            system_id: System ID
            org_id: Organization ID

        Returns:
            List of assessments ordered by creation date (newest first)
        """
        # Verify system exists
        await self.get_system(system_id, org_id)

        query = (
            select(HighRiskAssessment)
            .where(HighRiskAssessment.ai_system_id == system_id)
            .options(selectinload(HighRiskAssessment.creator))
            .order_by(HighRiskAssessment.created_at.desc())
        )

        result = await self.db.execute(query)
        return list(result.scalars().all())

    def get_checklist(self, result_label: str) -> list[str]:
        """Get checklist items for a result.

        Args:
            result_label: Assessment result label

        Returns:
            List of checklist items
        """
        return get_checklist(result_label)

    def get_disclaimer(self) -> str:
        """Get assessment disclaimer text.

        Returns:
            Disclaimer string
        """
        return ASSESSMENT_DISCLAIMER
