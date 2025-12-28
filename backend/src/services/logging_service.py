"""Logging Collector service (Module F)."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.ai_system import AISystem
from src.models.decision_log import DecisionLog
from src.models.log_api_key import LogApiKey
from src.models.system_version import SystemVersion
from src.models.user import User
from src.schemas.decision_event import DecisionEvent
from src.services.version_service import VersionService


class LoggingService:
    """Service for managing logging keys and decision event ingestion."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.version_service = VersionService(db)

    @staticmethod
    def generate_api_key() -> str:
        """Generate a secure random API key (shown once)."""
        return f"ak_{secrets.token_urlsafe(32)}"

    @staticmethod
    def hash_api_key(api_key: str) -> str:
        """Hash API key using SHA-256 (never store plaintext)."""
        return hashlib.sha256(api_key.encode("utf-8")).hexdigest()

    async def enable_logging(
        self,
        system_id: UUID,
        version_id: UUID,
        name: str,
        current_user: User,
    ) -> tuple[LogApiKey, str]:
        """Create a new per-version API key."""
        await self.version_service.get_by_id(
            system_id=system_id,
            version_id=version_id,
            org_id=current_user.org_id,
        )

        api_key = self.generate_api_key()
        key = LogApiKey(
            version_id=version_id,
            key_hash=self.hash_api_key(api_key),
            name=name,
            created_by=current_user.id,
        )
        self.db.add(key)

        try:
            await self.db.flush()
        except IntegrityError:
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="API key collision; please retry",
            ) from None

        return key, api_key

    async def revoke_api_key(self, key_id: UUID, org_id: UUID) -> None:
        """Revoke an API key by id (org-scoped)."""
        query = (
            select(LogApiKey)
            .join(SystemVersion, LogApiKey.version_id == SystemVersion.id)
            .join(AISystem, SystemVersion.ai_system_id == AISystem.id)
            .where(LogApiKey.id == key_id)
            .where(AISystem.org_id == org_id)
        )
        result = await self.db.execute(query)
        key = result.scalar_one_or_none()
        if not key:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

        if key.revoked_at is None:
            key.revoked_at = datetime.now(UTC)
            await self.db.flush()

    async def ingest_event(
        self,
        api_key: LogApiKey,
        raw_event: dict,
        allow_raw_pii: bool,
    ) -> DecisionLog:
        """Validate and store a decision event for the API key's scoped version."""
        try:
            event = DecisionEvent.model_validate(raw_event)
        except ValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"message": "Schema validation failed", "errors": e.errors()},
            ) from None

        event_json = event.model_dump(mode="json")

        # PII minimization: hash subject_id into subject_id_hash unless explicitly allowed
        subject = event_json.get("subject") or {}
        if not allow_raw_pii:
            raw_subject_id = subject.get("subject_id")
            if raw_subject_id and not subject.get("subject_id_hash"):
                subject["subject_id_hash"] = f"sha256:{hashlib.sha256(raw_subject_id.encode('utf-8')).hexdigest()}"
            subject.pop("subject_id", None)
            event_json["subject"] = subject

        log = DecisionLog(
            version_id=api_key.version_id,
            event_id=event.event_id,
            event_time=event.event_time,
            event_json=event_json,
            ingested_at=datetime.now(UTC),
        )
        self.db.add(log)

        # Update last_used_at on API key usage
        api_key.last_used_at = datetime.now(UTC)

        try:
            await self.db.flush()
        except IntegrityError:
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Duplicate event_id for this version",
            ) from None

        return log

    async def list_events(
        self,
        version_id: UUID,
        start_time: datetime | None,
        end_time: datetime | None,
        limit: int,
        offset: int,
    ) -> tuple[list[DecisionLog], int]:
        """List stored events for a version with optional time-range filter."""
        base_filters = [DecisionLog.version_id == version_id]
        if start_time is not None:
            base_filters.append(DecisionLog.event_time >= start_time)
        if end_time is not None:
            base_filters.append(DecisionLog.event_time <= end_time)

        count_query = select(func.count()).select_from(DecisionLog).where(*base_filters)
        total = await self.db.scalar(count_query)
        total = int(total or 0)

        query = (
            select(DecisionLog)
            .where(*base_filters)
            .order_by(DecisionLog.event_time.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def get_event(self, version_id: UUID, log_id: UUID) -> DecisionLog:
        """Get a single event by id (scoped to version)."""
        query = select(DecisionLog).where(DecisionLog.id == log_id).where(DecisionLog.version_id == version_id)
        result = await self.db.execute(query)
        log = result.scalar_one_or_none()
        if not log:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Log entry not found")
        return log

