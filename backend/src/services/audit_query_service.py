"""Service for querying audit events."""

from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.audit_event import AuditEvent
from src.models.enums import AuditAction


class AuditQueryService:
    """Service for listing and reading audit events (admin)."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_events(
        self,
        *,
        org_id: UUID,
        action: AuditAction | None = None,
        entity_type: str | None = None,
        entity_id: UUID | None = None,
        user_id: UUID | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AuditEvent], int]:
        query = select(AuditEvent).where(AuditEvent.org_id == org_id)
        count_query = select(func.count()).select_from(AuditEvent).where(AuditEvent.org_id == org_id)

        if action is not None:
            query = query.where(AuditEvent.action == action)
            count_query = count_query.where(AuditEvent.action == action)
        if entity_type:
            query = query.where(AuditEvent.entity_type == entity_type)
            count_query = count_query.where(AuditEvent.entity_type == entity_type)
        if entity_id is not None:
            query = query.where(AuditEvent.entity_id == entity_id)
            count_query = count_query.where(AuditEvent.entity_id == entity_id)
        if user_id is not None:
            query = query.where(AuditEvent.user_id == user_id)
            count_query = count_query.where(AuditEvent.user_id == user_id)
        if start_time is not None:
            query = query.where(AuditEvent.created_at >= start_time)
            count_query = count_query.where(AuditEvent.created_at >= start_time)
        if end_time is not None:
            query = query.where(AuditEvent.created_at <= end_time)
            count_query = count_query.where(AuditEvent.created_at <= end_time)

        total = int((await self.db.scalar(count_query)) or 0)

        query = (
            query.options(selectinload(AuditEvent.user))
            .order_by(AuditEvent.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def get_event(
        self,
        *,
        event_id: UUID,
        org_id: UUID,
    ) -> AuditEvent:
        query = (
            select(AuditEvent)
            .where(AuditEvent.id == event_id)
            .where(AuditEvent.org_id == org_id)
            .options(selectinload(AuditEvent.user))
        )
        result = await self.db.execute(query)
        event = result.scalar_one_or_none()
        if not event:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit event not found")
        return event

