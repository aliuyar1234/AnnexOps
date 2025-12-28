"""API routes for evidence mappings."""
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user, require_role
from src.core.database import get_db
from src.models.enums import MappingTargetType, UserRole
from src.models.user import User
from src.schemas.evidence import EvidenceResponse
from src.schemas.mapping import (
    CreateMappingRequest,
    MappingResponse,
    MappingWithEvidence,
)
from src.services.mapping_service import MappingService

router = APIRouter()


def _mapping_to_response(mapping) -> MappingResponse:
    """Convert EvidenceMapping model to MappingResponse."""
    return MappingResponse(
        id=mapping.id,
        evidence_id=mapping.evidence_id,
        version_id=mapping.version_id,
        target_type=mapping.target_type,
        target_key=mapping.target_key,
        strength=mapping.strength,
        notes=mapping.notes,
        created_by=mapping.created_by,
        created_at=mapping.created_at,
    )


def _mapping_to_response_with_evidence(mapping) -> MappingWithEvidence:
    """Convert EvidenceMapping model to MappingWithEvidence."""
    evidence = mapping.evidence_item
    return MappingWithEvidence(
        id=mapping.id,
        evidence_id=mapping.evidence_id,
        version_id=mapping.version_id,
        target_type=mapping.target_type,
        target_key=mapping.target_key,
        strength=mapping.strength,
        notes=mapping.notes,
        created_by=mapping.created_by,
        created_at=mapping.created_at,
        evidence=EvidenceResponse(
            id=evidence.id,
            org_id=evidence.org_id,
            type=evidence.type,
            title=evidence.title,
            description=evidence.description,
            tags=evidence.tags,
            classification=evidence.classification,
            type_metadata=evidence.type_metadata,
            created_by=evidence.created_by,
            created_at=evidence.created_at,
            updated_at=evidence.updated_at,
        ),
    )


@router.post(
    "/{system_id}/versions/{version_id}/evidence",
    response_model=MappingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create evidence mapping",
    description="Map an evidence item to a section/field/requirement in a system version. Requires EDITOR role or higher.",
)
async def create_mapping(
    system_id: UUID,
    version_id: UUID,
    request: CreateMappingRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.EDITOR)),
):
    """Create a new evidence mapping.

    Args:
        system_id: AI system ID (for URL structure)
        version_id: System version ID
        request: Mapping creation request
        db: Database session
        current_user: Current authenticated user

    Returns:
        Created mapping

    Raises:
        404: Version or evidence not found
        409: Mapping already exists (unique constraint violation)
        403: Insufficient permissions
    """
    service = MappingService(db)
    mapping = await service.create(
        version_id=version_id,
        request=request,
        current_user=current_user,
    )
    await db.commit()
    return _mapping_to_response(mapping)


@router.get(
    "/{system_id}/versions/{version_id}/evidence",
    response_model=list[MappingWithEvidence],
    summary="List evidence mappings",
    description="List all evidence mappings for a system version with optional filters.",
)
async def list_mappings(
    system_id: UUID,
    version_id: UUID,
    target_type: MappingTargetType | None = Query(None, description="Filter by target type"),
    target_key: str | None = Query(None, description="Filter by target key (exact match or prefix with *)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List evidence mappings for a version.

    Args:
        system_id: AI system ID (for URL structure)
        version_id: System version ID
        target_type: Optional filter by target type
        target_key: Optional filter by target key (supports prefix with *)
        limit: Maximum results to return
        offset: Number of results to skip
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of mappings with nested evidence details

    Raises:
        404: Version not found
    """
    service = MappingService(db)
    mappings = await service.list(
        version_id=version_id,
        org_id=current_user.org_id,
        target_type=target_type,
        target_key=target_key,
        limit=limit,
        offset=offset,
    )
    return [_mapping_to_response_with_evidence(m) for m in mappings]


@router.delete(
    "/{system_id}/versions/{version_id}/evidence/{mapping_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete evidence mapping",
    description="Delete an evidence mapping. Requires EDITOR role or higher.",
)
async def delete_mapping(
    system_id: UUID,
    version_id: UUID,
    mapping_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.EDITOR)),
):
    """Delete an evidence mapping.

    Args:
        system_id: AI system ID (for URL structure)
        version_id: System version ID
        mapping_id: Mapping ID to delete
        db: Database session
        current_user: Current authenticated user

    Raises:
        404: Mapping not found
        403: Insufficient permissions
    """
    service = MappingService(db)
    await service.delete(
        mapping_id=mapping_id,
        version_id=version_id,
        current_user=current_user,
    )
    await db.commit()
