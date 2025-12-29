"""Celery task for retention cleanup (Module F)."""

import asyncio
import logging
import time

from src.core.database import AsyncSessionLocal
from src.core.structured_logging import log_json
from src.services.retention_service import RetentionService
from src.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="src.tasks.retention_task.cleanup_retention")
def cleanup_retention() -> int:
    """Delete decision log events older than the configured retention window.

    Runs daily via Celery Beat (see `src.tasks.celery_app`).
    """

    started = time.perf_counter()
    log_json(logger, logging.INFO, "retention_cleanup_start")

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

    try:
        deleted = asyncio.run(_run())
    except Exception as exc:
        duration_ms = (time.perf_counter() - started) * 1000
        log_json(
            logger,
            logging.ERROR,
            "retention_cleanup_error",
            duration_ms=round(duration_ms, 2),
            error=str(exc),
            exception=exc.__class__.__name__,
        )
        raise

    duration_ms = (time.perf_counter() - started) * 1000
    log_json(
        logger,
        logging.INFO,
        "retention_cleanup_done",
        deleted=deleted,
        duration_ms=round(duration_ms, 2),
    )
    return deleted
