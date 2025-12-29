"""API routes for evidence management."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import require_role
from src.core.database import get_db
from src.models.enums import Classification, EvidenceType, UserRole
from src.models.user import User
from src.schemas.evidence import (
    CreateEvidenceRequest,
    DownloadUrlResponse,
    EvidenceDetailResponse,
    EvidenceListResponse,
    EvidenceResponse,
    UpdateEvidenceRequest,
    UploadUrlRequest,
    UploadUrlResponse,
    VersionSummary,
)
from src.services.evidence_service import EvidenceService
from src.services.storage_service import get_storage_service

router = APIRouter()


def _evidence_to_response(evidence) -> EvidenceResponse:
    """Convert EvidenceItem model to response."""
    return EvidenceResponse(
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
        usage_count=getattr(evidence, "usage_count", None),
    )


@router.post(
    "/upload-url",
    response_model=UploadUrlResponse,
    status_code=status.HTTP_200_OK,
    summary="Get presigned upload URL",
)
async def get_upload_url(
    request: UploadUrlRequest,
    current_user: User = Depends(require_role(UserRole.EDITOR)),
) -> UploadUrlResponse:
    """Get a presigned URL for uploading evidence files.

    Requires Editor or Admin role.

    The client should:
    1. Call this endpoint to get a presigned URL
    2. Upload the file directly to the presigned URL using PUT
    3. Call POST /evidence with the returned storage_uri in type_metadata

    Args:
        request: Upload URL request with filename and mime_type
        current_user: Current authenticated user

    Returns:
        UploadUrlResponse with presigned URL and storage URI
    """
    storage_service = get_storage_service()

    # Validate MIME type
    from src.services.evidence_service import ALLOWED_MIME_TYPES

    if request.mime_type not in ALLOWED_MIME_TYPES:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File type '{request.mime_type}' is not allowed",
        )

    # Generate presigned URL
    upload_url, storage_uri = storage_service.generate_upload_url(
        org_id=current_user.org_id,
        filename=request.filename,
        mime_type=request.mime_type,
    )

    return UploadUrlResponse(
        upload_url=upload_url,
        storage_uri=storage_uri,
        expires_in=3600,
    )


@router.post(
    "",
    response_model=EvidenceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create evidence item",
)
async def create_evidence(
    request: CreateEvidenceRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.EDITOR)),
) -> EvidenceResponse:
    """Create a new evidence item.

    Requires Editor or Admin role.

    For upload type evidence:
    - First call POST /evidence/upload-url to get presigned URL
    - Upload file to the presigned URL
    - Then call this endpoint with storage_uri in type_metadata

    For other types (url, git, ticket, note):
    - Call this endpoint directly with appropriate type_metadata

    Args:
        request: Evidence creation request
        db: Database session
        current_user: Current authenticated user

    Returns:
        Created evidence item
    """
    service = EvidenceService(db)

    # If type is UPLOAD, verify the file was uploaded and compute checksum
    if request.type == EvidenceType.UPLOAD:
        storage_service = get_storage_service()
        storage_uri = request.type_metadata.get("storage_uri")

        if not storage_uri:
            from fastapi import HTTPException

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="storage_uri is required for upload type",
            )

        # Verify file exists
        if not storage_service.file_exists(storage_uri):
            from fastapi import HTTPException

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found in storage. Please upload the file first.",
            )

        # Get file metadata and compute checksum
        file_metadata = storage_service.get_file_metadata(storage_uri)

        # Update type_metadata with actual file size and checksum
        request.type_metadata["file_size"] = file_metadata["file_size"]
        request.type_metadata["checksum_sha256"] = storage_service.compute_checksum(storage_uri)

    evidence, duplicate_of = await service.create(request, current_user)
    await db.commit()

    response = _evidence_to_response(evidence)
    response.duplicate_of = duplicate_of
    return response


@router.get(
    "",
    response_model=EvidenceListResponse,
    summary="List and search evidence items",
)
async def list_evidence(
    search: str | None = Query(None, description="Full-text search on title and description"),
    tags: list[str] | None = Query(None, description="Filter by tags (must have ALL tags)"),
    evidence_type: EvidenceType | None = Query(
        None, alias="type", description="Filter by evidence type"
    ),
    classification: Classification | None = Query(
        None, description="Filter by classification level"
    ),
    orphaned: bool | None = Query(
        None, description="Filter by orphaned status (true = no mappings, false = has mappings)"
    ),
    limit: int = Query(100, ge=1, le=1000, description="Maximum items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.VIEWER)),
) -> EvidenceListResponse:
    """List and search evidence items for the current user's organization.

    Supports multiple filters that can be combined:
    - **search**: Full-text search across title and description using PostgreSQL full-text search
    - **tags**: Filter by tags (evidence must contain ALL specified tags)
    - **type**: Filter by evidence type (upload, url, git, ticket, note)
    - **classification**: Filter by classification level (public, internal, confidential)
    - **orphaned**: Filter by orphaned status (true = no mappings, false = has mappings, null = all)
    - **limit**: Maximum number of items per page (1-1000, default 100)
    - **offset**: Pagination offset (default 0)

    Args:
        search: Full-text search query
        tags: List of tags to filter by
        evidence_type: Evidence type filter
        classification: Classification level filter
        orphaned: Orphaned status filter
        limit: Maximum items to return (1-1000)
        offset: Number of items to skip
        db: Database session
        current_user: Current authenticated user

    Returns:
        EvidenceListResponse with items (including usage_count), total count, limit, and offset
    """
    service = EvidenceService(db)
    evidence_items, total = await service.list(
        org_id=current_user.org_id,
        evidence_type=evidence_type,
        classification=classification,
        tags=tags,
        search=search,
        orphaned=orphaned,
        limit=limit,
        offset=offset,
    )

    return EvidenceListResponse(
        items=[_evidence_to_response(e) for e in evidence_items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{evidence_id}",
    response_model=EvidenceDetailResponse,
    summary="Get evidence item with details",
)
async def get_evidence(
    evidence_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.VIEWER)),
) -> EvidenceDetailResponse:
    """Get a specific evidence item by ID with usage count and mapped versions.

    Args:
        evidence_id: Evidence item ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Evidence item with usage_count and mapped_versions

    Raises:
        HTTPException: 404 if evidence not found
    """
    from fastapi import HTTPException

    service = EvidenceService(db)
    evidence, usage_count, mapped_versions = await service.get_by_id_with_details(
        evidence_id, current_user.org_id
    )

    if not evidence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence not found",
        )

    # Convert to response
    base_response = _evidence_to_response(evidence)

    # Convert mapped_versions dicts to VersionSummary objects
    version_summaries = [VersionSummary(**v) for v in mapped_versions]

    return EvidenceDetailResponse(
        **base_response.model_dump(exclude={"usage_count"}),
        usage_count=usage_count,
        mapped_versions=version_summaries,
    )


@router.get(
    "/{evidence_id}/download",
    status_code=status.HTTP_302_FOUND,
    summary="Get presigned download URL for evidence file",
)
async def download_evidence(
    evidence_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.VIEWER)),
):
    """Get a presigned download URL for an evidence file.

    Only works for upload type evidence. Returns 302 redirect to presigned URL.

    Args:
        evidence_id: Evidence item ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Redirect to presigned download URL (valid for 1 hour)

    Raises:
        HTTPException: 404 if evidence not found, 400 if not upload type
    """
    from fastapi import HTTPException
    from fastapi.responses import RedirectResponse

    service = EvidenceService(db)
    evidence = await service.get_by_id(evidence_id, current_user.org_id)

    if not evidence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence not found",
        )

    # Only upload type evidence has files to download
    if evidence.type != EvidenceType.UPLOAD:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot download {evidence.type.value} type evidence. Only 'upload' type evidence has downloadable files.",
        )

    # Get storage URI from metadata
    storage_uri = evidence.type_metadata.get("storage_uri")
    if not storage_uri:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Storage URI not found in evidence metadata",
        )

    # Generate presigned download URL
    storage_service = get_storage_service()
    download_url = storage_service.generate_download_url(storage_uri, expires_in=3600)

    return RedirectResponse(url=download_url, status_code=status.HTTP_302_FOUND)


@router.get(
    "/{evidence_id}/download-url",
    response_model=DownloadUrlResponse,
    summary="Get presigned download URL for evidence file (JSON)",
)
async def get_evidence_download_url(
    evidence_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.VIEWER)),
) -> DownloadUrlResponse:
    """Get a presigned download URL for an evidence file as JSON.

    Only works for upload type evidence.
    """
    from fastapi import HTTPException

    service = EvidenceService(db)
    evidence = await service.get_by_id(evidence_id, current_user.org_id)

    if not evidence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence not found",
        )

    if evidence.type != EvidenceType.UPLOAD:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot download {evidence.type.value} type evidence. Only 'upload' type evidence has downloadable files.",
        )

    storage_uri = evidence.type_metadata.get("storage_uri")
    if not storage_uri:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Storage URI not found in evidence metadata",
        )

    storage_service = get_storage_service()
    download_url = storage_service.generate_download_url(storage_uri, expires_in=3600)

    return DownloadUrlResponse(download_url=download_url, expires_in=3600)


@router.patch(
    "/{evidence_id}",
    response_model=EvidenceDetailResponse,
    summary="Update evidence item",
)
async def update_evidence(
    evidence_id: UUID,
    request: UpdateEvidenceRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.EDITOR)),
) -> EvidenceDetailResponse:
    """Update an evidence item.

    Requires Editor or Admin role.

    All fields are optional. Only provided fields will be updated.
    Note: Evidence type cannot be changed after creation.

    Args:
        evidence_id: Evidence item ID
        request: Update request with optional fields
        db: Database session
        current_user: Current authenticated user

    Returns:
        Updated evidence item with usage_count and mapped_versions

    Raises:
        HTTPException: 404 if evidence not found, 422 if validation fails
    """
    service = EvidenceService(db)

    # Convert request to dict, excluding None values
    updates = request.model_dump(exclude_none=True)

    # Update evidence
    evidence = await service.update(evidence_id, updates, current_user)
    await db.commit()

    # Get updated details
    evidence, usage_count, mapped_versions = await service.get_by_id_with_details(
        evidence_id, current_user.org_id
    )

    # Convert to response
    base_response = _evidence_to_response(evidence)
    version_summaries = [VersionSummary(**v) for v in mapped_versions]

    return EvidenceDetailResponse(
        **base_response.model_dump(exclude={"usage_count"}),
        usage_count=usage_count,
        mapped_versions=version_summaries,
    )


@router.delete(
    "/{evidence_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete evidence item",
)
async def delete_evidence(
    evidence_id: UUID,
    force: bool = Query(False, description="If true, delete all mappings before deleting evidence"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.EDITOR)),
) -> None:
    """Delete an evidence item.

    Requires Editor or Admin role.

    If evidence has mappings and force=false: Returns 409 Conflict
    If evidence has mappings and force=true: Deletes all mappings first, then deletes evidence
    If evidence has no mappings: Deletes evidence directly
    For upload type: Also deletes file from storage

    Args:
        evidence_id: Evidence item ID
        force: If true, delete all mappings before deleting evidence
        db: Database session
        current_user: Current authenticated user

    Raises:
        HTTPException: 404 if evidence not found, 409 if has mappings without force
    """
    service = EvidenceService(db)
    await service.delete(evidence_id, current_user, force=force)
    await db.commit()
