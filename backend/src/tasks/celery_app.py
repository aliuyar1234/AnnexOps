"""Celery application configuration."""

import os

from celery import Celery
from celery.schedules import crontab


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
