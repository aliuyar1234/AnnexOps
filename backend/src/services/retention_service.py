"""Retention management for decision logs (Module F)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.models.decision_log import DecisionLog


class RetentionService:
    """Service to purge expired decision logs based on retention policy."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()

    async def cleanup(self, retention_days: int | None = None) -> int:
        """Delete events older than retention window (based on ingested_at)."""
        days = int(retention_days if retention_days is not None else self.settings.retention_days)
        cutoff = datetime.now(UTC) - timedelta(days=days)

        count_query = select(func.count()).select_from(DecisionLog).where(DecisionLog.ingested_at < cutoff)
        count = int((await self.db.scalar(count_query)) or 0)

        await self.db.execute(delete(DecisionLog).where(DecisionLog.ingested_at < cutoff))
        await self.db.flush()
        return count

