"""Export service for decision logs (Module F)."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.decision_log import DecisionLog


class LogExportService:
    """Service for exporting decision logs in JSON and CSV formats."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _fetch_logs(
        self,
        version_id: UUID,
        start_time: datetime | None,
        end_time: datetime | None,
    ) -> list[DecisionLog]:
        filters = [DecisionLog.version_id == version_id]
        if start_time is not None:
            filters.append(DecisionLog.event_time >= start_time)
        if end_time is not None:
            filters.append(DecisionLog.event_time <= end_time)

        query = select(DecisionLog).where(*filters).order_by(DecisionLog.event_time.asc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def export_json(
        self,
        version_id: UUID,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> str:
        """Export logs as a JSON array of validated event objects."""
        logs = await self._fetch_logs(version_id=version_id, start_time=start_time, end_time=end_time)
        payload = [log.event_json for log in logs]
        return json.dumps(payload, ensure_ascii=False)

    async def export_csv(
        self,
        version_id: UUID,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> str:
        """Export logs as CSV (flattened key fields + full JSON)."""
        logs = await self._fetch_logs(version_id=version_id, start_time=start_time, end_time=end_time)
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "event_id",
                "event_time",
                "actor",
                "decision",
                "score",
                "subject_type",
                "subject_id_hash",
                "model_id",
                "model_version",
                "prompt_version",
                "input_hash",
                "output_hash",
                "ingested_at",
                "event_json",
            ],
        )
        writer.writeheader()

        for log in logs:
            event = log.event_json or {}
            subject = event.get("subject") or {}
            model = event.get("model") or {}
            input_data = event.get("input") or {}
            output_data = event.get("output") or {}

            writer.writerow(
                {
                    "event_id": log.event_id,
                    "event_time": event.get("event_time") or log.event_time.isoformat(),
                    "actor": event.get("actor", ""),
                    "decision": output_data.get("decision"),
                    "score": output_data.get("score"),
                    "subject_type": subject.get("subject_type"),
                    "subject_id_hash": subject.get("subject_id_hash"),
                    "model_id": model.get("model_id"),
                    "model_version": model.get("model_version"),
                    "prompt_version": model.get("prompt_version"),
                    "input_hash": input_data.get("input_hash"),
                    "output_hash": output_data.get("output_hash"),
                    "ingested_at": log.ingested_at.isoformat() if log.ingested_at else None,
                    "event_json": json.dumps(event, ensure_ascii=False),
                }
            )

        return output.getvalue()

