"""Celery application configuration."""

from __future__ import annotations

import logging
import os
from contextvars import Token

from celery import Celery
from celery.schedules import crontab
from celery.signals import task_postrun, task_prerun

from src.core.request_context import reset_request_id, set_request_id

logger = logging.getLogger(__name__)
_task_tokens: dict[str, Token[str | None]] = {}


def _get_broker_url() -> str:
    return os.getenv("CELERY_BROKER_URL", "redis://localhost:6380/0")


def _get_backend_url() -> str:
    return os.getenv("CELERY_RESULT_BACKEND", _get_broker_url())


celery_app = Celery(
    "annexops",
    broker=_get_broker_url(),
    backend=_get_backend_url(),
    include=["src.tasks.retention_task"],
)

celery_app.conf.update(
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "retention-cleanup-daily": {
            "task": "src.tasks.retention_task.cleanup_retention",
            "schedule": crontab(hour=3, minute=0),
        }
    },
)


@task_prerun.connect
def _attach_correlation_id(
    task_id: str | None = None,
    **_: object,
) -> None:
    """Attach a correlation ID to the task execution context for logging."""

    if not task_id:
        return
    _task_tokens[task_id] = set_request_id(task_id)


@task_postrun.connect
def _detach_correlation_id(
    task_id: str | None = None,
    **_: object,
) -> None:
    """Detach the task correlation ID from the execution context."""

    if not task_id:
        return
    token = _task_tokens.pop(task_id, None)
    if not token:
        return
    try:
        reset_request_id(token)
    except Exception:
        logger.exception("Failed to reset task correlation ID")
