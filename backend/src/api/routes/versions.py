"""API routes for system versions."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.deps import get_current_user, require_role
from src.core.database import get_db
from src.models.ai_system import AISystem
from src.models.annex_section import AnnexSection
from src.models.evidence_mapping import EvidenceMapping
from src.models.enums import UserRole, VersionStatus
from src.models.high_risk_assessment import HighRiskAssessment
from src.models.organization import Organization
from src.models.system_version import SystemVersion
from src.models.user import User
from src.schemas.completeness import CompletenessResponse
from src.schemas.version import (
    CloneVersionRequest,
    CreateVersionRequest,
    StatusChangeRequest,
    UpdateVersionRequest,
    UserSummary,
    VersionDetailResponse,
    VersionDiffResponse,
    VersionListResponse,
    VersionResponse,
)
from src.services.completeness_service import get_completeness_report
from src.services.diff_service import DiffService
from src.services.snapshot_service import SnapshotService
from src.services.version_service import VersionService

router = APIRouter()


def _version_to_response(version) -> VersionResponse:
    """Convert SystemVersion model to VersionResponse."""
    # Access all attributes synchronously to avoid lazy loading issues
    creator = version.creator
    created_by = None
    if creator:
        created_by = UserSummary(id=creator.id, email=creator.email)

    return VersionResponse(
        id=version.id,
        ai_system_id=version.ai_system_id,
        label=version.label,
        status=version.status,
        release_date=version.release_date,
        notes=version.notes,
        created_by=created_by,
        created_at=version.created_at,
        updated_at=version.updated_at,
    )


def _version_to_detail_response(version) -> VersionDetailResponse:
    """Convert SystemVersion model to VersionDetailResponse with counts."""
    # Access all attributes synchronously to avoid lazy loading issues
    creator = version.creator
    created_by = None
    if creator:
        created_by = UserSummary(id=creator.id, email=creator.email)

    return VersionDetailResponse(
        id=version.id,
        ai_system_id=version.ai_system_id,
        label=version.label,
        status=version.status,
        release_date=version.release_date,
        notes=version.notes,
        created_by=created_by,
        created_at=version.created_at,
        updated_at=version.updated_at,
        section_count=0,  # Placeholder for Module E
        evidence_count=0,  # Placeholder for Module D
    )


@router.post(
    "/{system_id}/versions",
    response_model=VersionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create system version",
)
async def create_version(
    system_id: UUID,
    request: CreateVersionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.EDITOR)),
) -> VersionResponse:
    """Create a new version for an AI system.

    Requires Editor or Admin role.
    Version label must be unique within the AI system.
    New versions start with 'draft' status.
    """
    service = VersionService(db)
    version = await service.create(system_id, request, current_user)
    # Build response before commit to avoid lazy loading issues
    response = _version_to_response(version)
    await db.commit()
    return response


@router.get(
    "/{system_id}/versions",
    response_model=VersionListResponse,
    summary="List system versions",
)
async def list_versions(
    system_id: UUID,
    status: VersionStatus | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VersionListResponse:
    """List versions for an AI system.

    Optionally filter by version status.
    """
    service = VersionService(db)
    versions, total = await service.list(
        system_id=system_id,
        org_id=current_user.org_id,
        status_filter=status,
        limit=limit,
        offset=offset,
    )
    return VersionListResponse(
        items=[_version_to_response(v) for v in versions],
        total=total,
    )


@router.patch(
    "/{system_id}/versions/{version_id}/status",
    response_model=VersionResponse,
    summary="Change version status",
)
async def change_version_status(
    system_id: UUID,
    version_id: UUID,
    request: StatusChangeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.EDITOR)),
) -> VersionResponse:
    """Change version status through workflow.

    Requires Editor or Admin role for most transitions.
    Only Admin can approve versions (transition to 'approved').

    Valid transitions:
    - draft -> review (Editor+)
    - review -> approved (Admin only)
    - review -> draft (Editor+)
    - approved -> (no transitions, terminal state)
    """
    service = VersionService(db)
    version = await service.change_status(system_id, version_id, request, current_user)
    # Build response before commit to avoid lazy loading issues
    response = _version_to_response(version)
    await db.commit()
    return response


@router.get(
    "/{system_id}/versions/compare",
    response_model=VersionDiffResponse,
    summary="Compare two system versions",
)
async def compare_versions(
    system_id: UUID,
    from_version: UUID = Query(..., description="Source version ID"),
    to_version: UUID = Query(..., description="Target version ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VersionDiffResponse:
    """Compare two versions of the same AI system.

    Returns differences between the two versions including:
    - Changed fields (label, status, notes, etc.)
    - Summary counts (added, removed, modified)

    Both versions must belong to the same AI system (cross-system comparison is rejected).
    """
    version_service = VersionService(db)
    diff_service = DiffService()

    # Verify system exists and user has access
    await version_service._get_ai_system(system_id, current_user.org_id)

    # Get both versions with org scoping (system verified below)
    from_ver = await version_service._get_version_unscoped(from_version, current_user.org_id)
    to_ver = await version_service._get_version_unscoped(to_version, current_user.org_id)

    # Verify both versions belong to the same AI system
    if from_ver.ai_system_id != to_ver.ai_system_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot compare versions from different AI systems",
        )

    # Ensure versions belong to requested system
    if from_ver.ai_system_id != system_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Version not found",
        )

    # Compute diff
    diff_result = diff_service.compute_version_diff_response(from_ver, to_ver)

    return VersionDiffResponse(**diff_result)


@router.get(
    "/{system_id}/versions/{version_id}",
    response_model=VersionDetailResponse,
    summary="Get version by ID",
)
async def get_version_by_id(
    system_id: UUID,
    version_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VersionDetailResponse:
    """Get a single version by ID with full details.

    Returns version information with section_count and evidence_count
    (placeholders for future modules).
    """
    service = VersionService(db)
    version = await service.get_by_id(system_id, version_id, current_user.org_id)
    return _version_to_detail_response(version)


@router.patch(
    "/{system_id}/versions/{version_id}",
    response_model=VersionDetailResponse,
    summary="Update version",
)
async def update_version(
    system_id: UUID,
    version_id: UUID,
    request: UpdateVersionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.EDITOR)),
) -> VersionDetailResponse:
    """Update a system version.

    Requires Editor or Admin role.
    Allows updating notes and release_date fields.
    Past and future release dates are allowed (for pre-announced releases).

    Note: Cannot update immutable versions (approved with exports) - will be enforced in Phase 8.
    """
    service = VersionService(db)
    version = await service.update(system_id, version_id, request, current_user)
    # Build response before commit to avoid lazy loading issues
    response = _version_to_detail_response(version)
    await db.commit()
    return response


@router.get(
    "/{system_id}/versions/{version_id}/manifest",
    response_model=dict,
    summary="Get version manifest",
)
async def get_version_manifest(
    system_id: UUID,
    version_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Get the system manifest for a version.

    Returns the canonical manifest structure used as SSOT for exports and
    reproducibility (Constitution Principle V).

    Important: the `snapshot_hash` is computed and returned but NOT persisted to
    the version by this endpoint. Hash storage happens during export creation.
    """
    snapshot_service = SnapshotService()

    # Load version + system with org scoping (avoid async lazy loading in routes).
    version_query = (
        select(SystemVersion)
        .join(AISystem, SystemVersion.ai_system_id == AISystem.id)
        .options(selectinload(SystemVersion.ai_system))
        .where(
            SystemVersion.id == version_id,
            SystemVersion.ai_system_id == system_id,
            AISystem.org_id == current_user.org_id,
        )
    )
    version_result = await db.execute(version_query)
    version = version_result.scalar_one_or_none()
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")

    ai_system = version.ai_system
    if not ai_system:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="System not found")

    org_result = await db.execute(select(Organization).where(Organization.id == current_user.org_id))
    org = org_result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    sections_result = await db.execute(
        select(AnnexSection)
        .where(AnnexSection.version_id == version_id)
        .order_by(AnnexSection.section_key)
    )
    sections = list(sections_result.scalars().all())

    mappings_result = await db.execute(
        select(EvidenceMapping)
        .options(selectinload(EvidenceMapping.evidence_item))
        .where(EvidenceMapping.version_id == version_id)
    )
    mappings = list(mappings_result.scalars().all())

    evidence_map = {}
    for mapping in mappings:
        if mapping.evidence_item:
            evidence_map[str(mapping.evidence_item.id)] = mapping.evidence_item
    evidence_items = sorted(evidence_map.values(), key=lambda e: str(e.id))

    assessment_result = await db.execute(
        select(HighRiskAssessment)
        .where(HighRiskAssessment.ai_system_id == ai_system.id)
        .order_by(HighRiskAssessment.created_at.desc())
        .limit(1)
    )
    assessment = assessment_result.scalar_one_or_none()

    manifest = snapshot_service.generate_manifest(
        org=org,
        version=version,
        ai_system=ai_system,
        sections=sections,
        evidence_items=evidence_items,
        mappings=mappings,
        assessment=assessment,
    )
    manifest = snapshot_service.finalize_manifest(manifest)
    return manifest.to_dict()


@router.post(
    "/{system_id}/versions/{version_id}/clone",
    response_model=VersionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Clone system version",
)
async def clone_version(
    system_id: UUID,
    version_id: UUID,
    request: CloneVersionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.EDITOR)),
) -> VersionResponse:
    """Clone an existing version with a new label.

    Requires Editor or Admin role.
    Creates a new draft version as a copy of the source version.

    Copied fields:
    - notes

    NOT copied (new version gets fresh values):
    - snapshot_hash
    - approved_by
    - approved_at
    - release_date

    The cloned version always starts with 'draft' status.
    """
    service = VersionService(db)
    cloned_version = await service.clone(system_id, version_id, request, current_user)
    # Build response before commit to avoid lazy loading issues
    response = _version_to_response(cloned_version)
    await db.commit()
    return response


@router.delete(
    "/{system_id}/versions/{version_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete system version",
)
async def delete_version(
    system_id: UUID,
    version_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> None:
    """Delete a system version.

    Requires Admin role.
    Cannot delete immutable versions (approved with exports).

    For Phase 8, since exports table doesn't exist yet,
    all approved versions are still mutable and can be deleted.
    When exports are implemented in Module E, deletion of
    approved versions with exports will be rejected with 409.
    """
    service = VersionService(db)
    await service.delete(system_id, version_id, current_user)
    await db.commit()


@router.get(
    "/{system_id}/versions/{version_id}/completeness",
    response_model=CompletenessResponse,
    summary="Get completeness dashboard",
)
async def get_completeness_dashboard(
    system_id: UUID,
    version_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CompletenessResponse:
    """Get completeness dashboard for a system version.

    Returns overall completeness score and per-section details including:
    - Section completeness scores (0-100)
    - Field completion status for each required field
    - Evidence count per section
    - Identified gaps (missing required fields, no evidence)

    Accessible by Viewer role and above.

    Completeness calculation:
    - Section score = 50% from required fields + 50% from evidence (max 3)
    - Overall score = weighted average using SECTION_WEIGHTS
    """
    from src.services.version_service import VersionService

    # Verify version exists and belongs to system (org-scoped)
    version_service = VersionService(db)
    await version_service.get_by_id(system_id, version_id, current_user.org_id)

    # Generate completeness report
    completeness = await get_completeness_report(db, version_id)

    return completeness
