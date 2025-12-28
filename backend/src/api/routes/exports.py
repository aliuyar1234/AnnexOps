"""API routes for export management."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import require_role
from src.core.database import get_db
from src.models.enums import UserRole
from src.models.user import User
from src.schemas.export import CreateExportRequest, ExportListResponse, ExportResponse
from src.services.export_service import ExportService

router = APIRouter()


@router.post(
    "/systems/{system_id}/versions/{version_id}/exports",
    response_model=ExportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate export package for a system version",
)
async def create_export(
    system_id: UUID,
    version_id: UUID,
    request: CreateExportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.EDITOR)),
) -> ExportResponse:
    """Generate an export package (ZIP) for a system version.

    Requires Editor or higher role.

    Creates a ZIP file containing:
    - AnnexIV.docx: The main document
    - SystemManifest.json: Version metadata with snapshot hash
    - EvidenceIndex.json: All evidence items (sorted)
    - EvidenceIndex.csv: Evidence items in CSV format
    - CompletenessReport.json: Completeness scores and gaps
    - DiffReport.json: (optional) Changes from compare version

    Args:
        system_id: System ID (not used, but part of URL hierarchy)
        version_id: System version ID
        request: Export request with optional diff settings
        db: Database session
        current_user: Current authenticated user

    Returns:
        ExportResponse with export metadata

    Raises:
        HTTPException: 404 if version not found or doesn't belong to user's org
        HTTPException: 400 if include_diff is true but compare_version_id is missing
    """
    service = ExportService(db)
    export = await service.generate_export(
        version_id=version_id,
        org_id=current_user.org_id,
        user=current_user,
        include_diff=request.include_diff,
        compare_version_id=request.compare_version_id,
    )

    return _export_to_response(export)


def _export_to_response(export) -> ExportResponse:
    """Convert Export model to response."""
    return ExportResponse(
        id=export.id,
        version_id=export.version_id,
        export_type=export.export_type,
        snapshot_hash=export.snapshot_hash,
        storage_uri=export.storage_uri,
        file_size=export.file_size,
        include_diff=export.include_diff,
        compare_version_id=export.compare_version_id,
        completeness_score=export.completeness_score,
        created_by=export.created_by,
        created_at=export.created_at,
        updated_at=export.updated_at,
    )


@router.get(
    "/systems/{system_id}/versions/{version_id}/exports",
    response_model=ExportListResponse,
    summary="List exports for a system version",
)
async def list_exports(
    system_id: UUID,
    version_id: UUID,
    limit: int = Query(100, ge=1, le=1000, description="Maximum items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.VIEWER)),
) -> ExportListResponse:
    """List all exports for a system version.

    Requires Viewer or higher role.

    Returns exports ordered by creation date (newest first) with pagination support.

    Args:
        system_id: System ID (not used, but part of URL hierarchy)
        version_id: System version ID
        limit: Maximum items to return (1-1000, default 100)
        offset: Number of items to skip (default 0)
        db: Database session
        current_user: Current authenticated user

    Returns:
        ExportListResponse with items, total count, limit, and offset

    Raises:
        HTTPException: 404 if version not found or doesn't belong to user's org
    """
    service = ExportService(db)
    exports, total = await service.list_exports(
        version_id=version_id,
        org_id=current_user.org_id,
        limit=limit,
        offset=offset,
    )

    return ExportListResponse(
        items=[_export_to_response(e) for e in exports],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/exports/{export_id}/download",
    status_code=status.HTTP_302_FOUND,
    summary="Get presigned download URL for export",
)
async def download_export(
    export_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.VIEWER)),
):
    """Get a presigned download URL for an export file.

    Requires Viewer or higher role.

    Returns 302 redirect to presigned URL (valid for 1 hour).

    Args:
        export_id: Export ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Redirect to presigned download URL

    Raises:
        HTTPException: 404 if export not found or doesn't belong to user's org
    """
    service = ExportService(db)
    download_url = await service.get_download_url(
        export_id=export_id,
        org_id=current_user.org_id,
    )

    return RedirectResponse(url=download_url, status_code=status.HTTP_302_FOUND)
