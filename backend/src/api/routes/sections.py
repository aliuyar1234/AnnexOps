"""API routes for Annex IV section management."""

from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, status
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
from src.schemas.section_comment import (
    CommentAuthor,
    CreateSectionCommentRequest,
    SectionCommentListResponse,
    SectionCommentResponse,
)
from src.services.completeness_service import SECTION_TITLES
from src.services.section_comment_service import SectionCommentService
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


def _comment_to_response(comment) -> SectionCommentResponse:
    author = (
        CommentAuthor(id=comment.author.id, email=comment.author.email)
        if getattr(comment, "author", None)
        else None
    )
    return SectionCommentResponse(
        id=comment.id,
        version_id=comment.version_id,
        section_key=comment.section_key,
        comment=comment.comment,
        author=author,
        created_at=comment.created_at,
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
    section_key: str = Path(..., min_length=1, max_length=100, pattern=r"^[A-Z0-9._-]+$"),
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
    request: UpdateSectionRequest,
    section_key: str = Path(..., min_length=1, max_length=100, pattern=r"^[A-Z0-9._-]+$"),
    force: bool = Query(
        False,
        description="If true, overwrite even if the section has changed since it was last loaded.",
    ),
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
        expected_updated_at=request.expected_updated_at,
        force=force,
        current_user=current_user,
    )

    await db.commit()

    return _section_to_response(section)


@router.get(
    "/{system_id}/versions/{version_id}/sections/{section_key}/comments",
    response_model=SectionCommentListResponse,
    summary="List section review comments",
)
async def list_section_comments(
    system_id: UUID,
    version_id: UUID,
    section_key: str = Path(..., min_length=1, max_length=100, pattern=r"^[A-Z0-9._-]+$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.VIEWER)),
) -> SectionCommentListResponse:
    service = SectionCommentService(db)
    comments, total = await service.list(
        version_id=version_id,
        section_key=section_key,
        org_id=current_user.org_id,
        limit=limit,
        offset=offset,
    )
    return SectionCommentListResponse(
        items=[_comment_to_response(c) for c in comments],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/{system_id}/versions/{version_id}/sections/{section_key}/comments",
    response_model=SectionCommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create section review comment",
)
async def create_section_comment(
    system_id: UUID,
    version_id: UUID,
    request: CreateSectionCommentRequest,
    section_key: str = Path(..., min_length=1, max_length=100, pattern=r"^[A-Z0-9._-]+$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.REVIEWER)),
) -> SectionCommentResponse:
    service = SectionCommentService(db)
    comment = await service.create(
        version_id=version_id,
        section_key=section_key,
        comment=request.comment,
        current_user=current_user,
    )
    await db.commit()
    return _comment_to_response(comment)
