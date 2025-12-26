"""API routes for AI systems."""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user, require_role
from src.core.database import get_db
from src.models.enums import HRUseCaseType, UserRole
from src.models.user import User
from src.schemas.ai_system import (
    CreateSystemRequest,
    UpdateSystemRequest,
    SystemResponse,
    SystemDetailResponse,
    SystemListResponse,
    UserSummary,
)
from src.services.ai_system_service import AISystemService


router = APIRouter()


def _system_to_response(system) -> SystemResponse:
    """Convert AISystem model to SystemResponse."""
    return SystemResponse(
        id=system.id,
        name=system.name,
        description=system.description,
        hr_use_case_type=system.hr_use_case_type,
        intended_purpose=system.intended_purpose,
        deployment_type=system.deployment_type,
        decision_influence=system.decision_influence,
        owner=UserSummary(id=system.owner.id, email=system.owner.email) if system.owner else None,
        contact_name=system.contact_name,
        contact_email=system.contact_email,
        version=system.version,
        created_at=system.created_at,
        updated_at=system.updated_at,
    )


def _system_to_detail_response(system) -> SystemDetailResponse:
    """Convert AISystem model to SystemDetailResponse."""
    latest_assessment = None
    if system.assessments:
        assessment = system.assessments[0]
        from src.schemas.ai_system import AssessmentSummary
        latest_assessment = AssessmentSummary(
            id=assessment.id,
            result_label=assessment.result_label.value,
            score=assessment.score,
            created_at=assessment.created_at,
        )

    return SystemDetailResponse(
        id=system.id,
        name=system.name,
        description=system.description,
        hr_use_case_type=system.hr_use_case_type,
        intended_purpose=system.intended_purpose,
        deployment_type=system.deployment_type,
        decision_influence=system.decision_influence,
        owner=UserSummary(id=system.owner.id, email=system.owner.email) if system.owner else None,
        contact_name=system.contact_name,
        contact_email=system.contact_email,
        version=system.version,
        created_at=system.created_at,
        updated_at=system.updated_at,
        latest_assessment=latest_assessment,
        attachment_count=len(system.attachments) if system.attachments else 0,
        version_count=0,  # Placeholder for Module C
    )


@router.post(
    "",
    response_model=SystemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create AI system",
)
async def create_system(
    request: CreateSystemRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.EDITOR)),
) -> SystemResponse:
    """Create a new AI system.

    Requires Editor or Admin role.
    """
    service = AISystemService(db)
    system = await service.create(request, current_user)
    await db.commit()
    return _system_to_response(system)


@router.get(
    "",
    response_model=SystemListResponse,
    summary="List AI systems",
)
async def list_systems(
    use_case_type: Optional[HRUseCaseType] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SystemListResponse:
    """List AI systems for the current organization.

    Optionally filter by HR use case type.
    """
    service = AISystemService(db)
    systems, total = await service.list(
        org_id=current_user.org_id,
        use_case_type=use_case_type,
        limit=limit,
        offset=offset,
    )
    return SystemListResponse(
        items=[_system_to_response(s) for s in systems],
        total=total,
    )


@router.get(
    "/{system_id}",
    response_model=SystemDetailResponse,
    summary="Get AI system details",
)
async def get_system(
    system_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SystemDetailResponse:
    """Get detailed information about an AI system."""
    service = AISystemService(db)
    system = await service.get_by_id(system_id, current_user.org_id)
    if not system:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="System not found",
        )
    return _system_to_detail_response(system)


@router.patch(
    "/{system_id}",
    response_model=SystemResponse,
    summary="Update AI system",
)
async def update_system(
    system_id: UUID,
    request: UpdateSystemRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.EDITOR)),
) -> SystemResponse:
    """Update an AI system.

    Requires Editor or Admin role.
    Supports optimistic locking via expected_version.
    """
    service = AISystemService(db)
    system = await service.update(system_id, request, current_user)
    await db.commit()
    return _system_to_response(system)


@router.delete(
    "/{system_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete AI system (Admin only)",
)
async def delete_system(
    system_id: UUID,
    confirm_with_versions: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> None:
    """Delete an AI system.

    Requires Admin role.
    If the system has versions, confirm_with_versions must be true.
    """
    service = AISystemService(db)
    await service.delete(system_id, current_user, confirm_with_versions)
    await db.commit()
