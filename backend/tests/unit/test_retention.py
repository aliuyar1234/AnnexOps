"""Unit tests for retention cleanup logic (Module F)."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.decision_log import DecisionLog
from src.models.system_version import SystemVersion
from src.services.retention_service import RetentionService


@pytest.mark.asyncio
async def test_retention_cleanup_deletes_old_events(db: AsyncSession, test_version: SystemVersion):
    """Events older than retention window are deleted."""
    now = datetime.now(UTC)

    old_log = DecisionLog(
        version_id=test_version.id,
        event_id="evt_old",
        event_time=now - timedelta(days=200),
        event_json={"event_id": "evt_old"},
        ingested_at=now - timedelta(days=200),
    )
    new_log = DecisionLog(
        version_id=test_version.id,
        event_id="evt_new",
        event_time=now - timedelta(days=1),
        event_json={"event_id": "evt_new"},
        ingested_at=now - timedelta(days=1),
    )
    db.add_all([old_log, new_log])
    await db.flush()

    service = RetentionService(db)
    deleted = await service.cleanup(retention_days=180)

    assert deleted == 1

    result = await db.execute(select(DecisionLog).where(DecisionLog.version_id == test_version.id))
    remaining = list(result.scalars().all())
    assert len(remaining) == 1
    assert remaining[0].event_id == "evt_new"

