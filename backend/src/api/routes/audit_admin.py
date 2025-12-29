"""Admin routes for audit log access."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import require_role
from src.core.database import get_db
from src.models.enums import AuditAction, UserRole
from src.models.user import User
from src.schemas.audit import (
    AuditEventDetailResponse,
    AuditEventListItem,
    AuditEventListResponse,
    AuditUserSummary,
)
from src.services.audit_query_service import AuditQueryService

router = APIRouter()


def _user_summary(user: User | None) -> AuditUserSummary | None:
    if not user:
        return None
    return AuditUserSummary(id=user.id, email=user.email, role=user.role)


def _event_to_list_item(event) -> AuditEventListItem:
    return AuditEventListItem(
        id=event.id,
        created_at=event.created_at,
        user=_user_summary(getattr(event, "user", None)),
        action=event.action,
        entity_type=event.entity_type,
        entity_id=event.entity_id,
        ip_address=str(event.ip_address) if event.ip_address is not None else None,
    )


def _event_to_detail(event) -> AuditEventDetailResponse:
    return AuditEventDetailResponse(
        id=event.id,
        created_at=event.created_at,
        user=_user_summary(getattr(event, "user", None)),
        action=event.action,
        entity_type=event.entity_type,
        entity_id=event.entity_id,
        ip_address=str(event.ip_address) if event.ip_address is not None else None,
        diff_json=event.diff_json,
    )


@router.get(
    "/audit/events",
    response_model=AuditEventListResponse,
    summary="List audit events (admin)",
)
async def list_audit_events(
    action: AuditAction | None = Query(None),
    entity_type: str | None = Query(None, max_length=50),
    entity_id: UUID | None = Query(None),
    user_id: UUID | None = Query(None),
    start_time: datetime | None = Query(None),
    end_time: datetime | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> AuditEventListResponse:
    service = AuditQueryService(db)
    events, total = await service.list_events(
        org_id=current_user.org_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=user_id,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )
    return AuditEventListResponse(
        items=[_event_to_list_item(e) for e in events],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/audit/events/{event_id}",
    response_model=AuditEventDetailResponse,
    summary="Get audit event detail (admin)",
)
async def get_audit_event(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> AuditEventDetailResponse:
    service = AuditQueryService(db)
    event = await service.get_event(event_id=event_id, org_id=current_user.org_id)
    return _event_to_detail(event)

