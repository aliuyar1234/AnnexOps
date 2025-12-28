"""Celery task for retention cleanup (Module F)."""

import asyncio

from src.core.database import AsyncSessionLocal
from src.services.retention_service import RetentionService
from src.tasks.celery_app import celery_app


@celery_app.task(name="src.tasks.retention_task.cleanup_retention")
def cleanup_retention() -> int:
    """Delete decision log events older than the configured retention window.

    Runs daily via Celery Beat (see `src.tasks.celery_app`).
    """

    async def _run() -> int:
        async with AsyncSessionLocal() as session:
            try:
                service = RetentionService(session)
                deleted = await service.cleanup()
                await session.commit()
                return deleted
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    return asyncio.run(_run())
