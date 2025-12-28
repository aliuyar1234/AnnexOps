"""API routes for Annex IV section management."""
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import require_role
from src.core.database import get_db
from src.models.enums import UserRole
from src.models.user import User
from src.schemas.section import (
    SectionListResponse,
    SectionResponse,
    UpdateSectionRequest,
)
from src.services.completeness_service import SECTION_TITLES
from src.services.section_service import SectionService

router = APIRouter()


def _section_to_response(section) -> SectionResponse:
    """Convert AnnexSection model to SectionResponse."""
    return SectionResponse(
        id=section.id,
        version_id=section.version_id,
        section_key=section.section_key,
        title=SECTION_TITLES.get(section.section_key, section.section_key),
        content=section.content,
        completeness_score=section.completeness_score,
        evidence_refs=section.evidence_refs,
        llm_assisted=section.llm_assisted,
        last_edited_by=section.last_edited_by,
        updated_at=section.updated_at,
    )


@router.get(
    "/{system_id}/versions/{version_id}/sections",
    response_model=SectionListResponse,
    summary="List all Annex IV sections",
    description="Get all 12 Annex IV sections for a system version. Sections are automatically created if they don't exist.",
)
async def list_sections(
    system_id: UUID,
    version_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.VIEWER)),
) -> SectionListResponse:
    """List all Annex IV sections for a version.

    Args:
        system_id: AI system ID (for URL structure)
        version_id: System version ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        SectionListResponse with all 12 sections

    Raises:
        404: Version not found or access denied
    """
    service = SectionService(db)
    sections = await service.list_sections(
        version_id=version_id,
        org_id=current_user.org_id,
    )

    return SectionListResponse(
        items=[_section_to_response(s) for s in sections],
        total=len(sections),
    )


@router.get(
    "/{system_id}/versions/{version_id}/sections/{section_key}",
    response_model=SectionResponse,
    summary="Get a specific section",
    description="Get a single Annex IV section by its key (e.g., ANNEX4.RISK_MANAGEMENT).",
)
async def get_section(
    system_id: UUID,
    version_id: UUID,
    section_key: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.VIEWER)),
) -> SectionResponse:
    """Get a specific section by key.

    Args:
        system_id: AI system ID (for URL structure)
        version_id: System version ID
        section_key: Section key (e.g., "ANNEX4.RISK_MANAGEMENT")
        db: Database session
        current_user: Current authenticated user

    Returns:
        SectionResponse for the requested section

    Raises:
        404: Version not found or access denied
    """
    from fastapi import HTTPException

    service = SectionService(db)
    section = await service.get_by_key(
        version_id=version_id,
        section_key=section_key,
        org_id=current_user.org_id,
    )

    if not section:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Section not found",
        )

    return _section_to_response(section)


@router.patch(
    "/{system_id}/versions/{version_id}/sections/{section_key}",
    response_model=SectionResponse,
    summary="Update a section",
    description="Update section content and/or evidence references. Requires Editor role or higher.",
)
async def update_section(
    system_id: UUID,
    version_id: UUID,
    section_key: str,
    request: UpdateSectionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.EDITOR)),
) -> SectionResponse:
    """Update a section's content and/or evidence references.

    Args:
        system_id: AI system ID (for URL structure)
        version_id: System version ID
        section_key: Section key (e.g., "ANNEX4.RISK_MANAGEMENT")
        request: Update request with optional content and evidence_refs
        db: Database session
        current_user: Current authenticated user

    Returns:
        Updated SectionResponse

    Raises:
        404: Section or version not found
        403: Insufficient permissions
    """
    service = SectionService(db)

    section = await service.update_content(
        version_id=version_id,
        section_key=section_key,
        content=request.content,
        evidence_refs=request.evidence_refs,
        current_user=current_user,
    )

    await db.commit()

    return _section_to_response(section)
