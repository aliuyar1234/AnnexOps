"""Admin and authenticated routes for Logging Collector (Module F)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import require_role
from src.core.database import get_db
from src.models.enums import UserRole
from src.models.user import User
from src.schemas.logging import (
    ApiKeyResponse,
    EnableLoggingRequest,
    LogDetailResponse,
    LogListItem,
    LogListResponse,
)
from src.services.log_export_service import LogExportService
from src.services.logging_service import LoggingService
from src.services.version_service import VersionService

router = APIRouter()


@router.post(
    "/systems/{system_id}/versions/{version_id}/logging/enable",
    response_model=ApiKeyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Enable logging for a system version (creates API key)",
)
async def enable_logging(
    request: Request,
    system_id: UUID,
    version_id: UUID,
    body: EnableLoggingRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.EDITOR)),
) -> ApiKeyResponse:
    """Create an API key for decision event ingestion (key shown once)."""
    service = LoggingService(db)
    key, api_key = await service.enable_logging(
        system_id=system_id,
        version_id=version_id,
        name=body.name,
        current_user=current_user,
    )

    base_url = str(request.base_url).rstrip("/")
    endpoint = f"{base_url}/api/v1/logs"
    await db.commit()
    return ApiKeyResponse(key_id=key.id, api_key=api_key, endpoint=endpoint)


@router.delete(
    "/logging/keys/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke logging API key (admin only)",
)
async def revoke_logging_key(
    key_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> None:
    """Revoke an API key so it can no longer ingest events."""
    service = LoggingService(db)
    await service.revoke_api_key(key_id=key_id, org_id=current_user.org_id)
    await db.commit()


@router.get(
    "/systems/{system_id}/versions/{version_id}/logs",
    response_model=LogListResponse,
    summary="List decision logs for a version (time-range filter)",
)
async def list_logs(
    system_id: UUID,
    version_id: UUID,
    start_time: datetime | None = Query(None),
    end_time: datetime | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.VIEWER)),
) -> LogListResponse:
    """List stored decision logs for a version (viewer+)."""
    version_service = VersionService(db)
    await version_service.get_by_id(
        system_id=system_id, version_id=version_id, org_id=current_user.org_id
    )

    service = LoggingService(db)
    logs, total = await service.list_events(
        version_id=version_id,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )

    items: list[LogListItem] = []
    for log in logs:
        event_json = log.event_json or {}
        output = event_json.get("output") or {}
        items.append(
            LogListItem(
                id=log.id,
                event_id=log.event_id,
                event_time=log.event_time,
                actor=event_json.get("actor", ""),
                decision=output.get("decision"),
                ingested_at=log.ingested_at,
            )
        )

    return LogListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/systems/{system_id}/versions/{version_id}/logs/export",
    summary="Export decision logs for a time range (JSON or CSV)",
)
async def export_logs(
    system_id: UUID,
    version_id: UUID,
    format: str = Query("json", pattern="^(json|csv)$"),
    start_time: datetime | None = Query(None),
    end_time: datetime | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.VIEWER)),
):
    """Export decision logs (viewer+)."""
    version_service = VersionService(db)
    await version_service.get_by_id(
        system_id=system_id, version_id=version_id, org_id=current_user.org_id
    )

    export_service = LogExportService(db)
    if format == "csv":
        content = await export_service.export_csv(
            version_id=version_id, start_time=start_time, end_time=end_time
        )
        return Response(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="decision_logs.csv"'},
        )

    content = await export_service.export_json(
        version_id=version_id, start_time=start_time, end_time=end_time
    )
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="decision_logs.json"'},
    )


@router.get(
    "/systems/{system_id}/versions/{version_id}/logs/{log_id}",
    response_model=LogDetailResponse,
    summary="Get decision log entry details",
)
async def get_log_detail(
    system_id: UUID,
    version_id: UUID,
    log_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.VIEWER)),
) -> LogDetailResponse:
    """Get a single decision log entry by id (viewer+)."""
    version_service = VersionService(db)
    await version_service.get_by_id(
        system_id=system_id, version_id=version_id, org_id=current_user.org_id
    )

    service = LoggingService(db)
    log = await service.get_event(version_id=version_id, log_id=log_id)

    event_json = log.event_json or {}
    return LogDetailResponse(
        id=log.id,
        event_id=log.event_id,
        event_time=log.event_time,
        actor=event_json.get("actor", ""),
        ingested_at=log.ingested_at,
        event_json=event_json,
    )
