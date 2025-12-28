"""API routes for high-risk assessments."""
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user
from src.core.database import get_db
from src.models.user import User
from src.schemas.ai_system import UserSummary
from src.schemas.assessment import (
    AssessmentResponse,
    AssessmentSubmission,
    WizardQuestion,
    WizardQuestions,
)
from src.services.assessment_service import AssessmentService

router = APIRouter()


def _assessment_to_response(assessment, service: AssessmentService) -> AssessmentResponse:
    """Convert HighRiskAssessment model to response."""
    return AssessmentResponse(
        id=assessment.id,
        result_label=assessment.result_label.value,
        score=assessment.score,
        notes=assessment.notes,
        checklist=service.get_checklist(assessment.result_label.value),
        disclaimer=service.get_disclaimer(),
        created_by=UserSummary(
            id=assessment.creator.id,
            email=assessment.creator.email,
        ) if assessment.creator else None,
        created_at=assessment.created_at,
    )


@router.get(
    "/{system_id}/high-risk-assessment/questions",
    response_model=WizardQuestions,
    summary="Get wizard questions",
)
async def get_wizard_questions(
    system_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WizardQuestions:
    """Get the high-risk assessment wizard questions.

    System ID is validated to ensure it exists in the user's org.
    """
    service = AssessmentService(db)
    # Validate system exists
    await service.get_system(system_id, current_user.org_id)

    questions_data = service.get_questions()
    return WizardQuestions(
        version=questions_data["version"],
        questions=[WizardQuestion(**q) for q in questions_data["questions"]],
    )


@router.post(
    "/{system_id}/high-risk-assessment",
    response_model=AssessmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit high-risk assessment",
)
async def submit_assessment(
    system_id: UUID,
    submission: AssessmentSubmission,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AssessmentResponse:
    """Submit a completed high-risk assessment.

    The assessment is scored automatically based on the answers.
    """
    service = AssessmentService(db)
    assessment = await service.submit_assessment(system_id, submission, current_user)
    await db.commit()
    await db.refresh(assessment)
    return _assessment_to_response(assessment, service)


@router.get(
    "/{system_id}/high-risk-assessment",
    response_model=list[AssessmentResponse],
    summary="Get assessment history",
)
async def get_assessments(
    system_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AssessmentResponse]:
    """Get the assessment history for a system.

    Returns assessments ordered by creation date (newest first).
    """
    service = AssessmentService(db)
    assessments = await service.get_assessments(system_id, current_user.org_id)
    return [_assessment_to_response(a, service) for a in assessments]
