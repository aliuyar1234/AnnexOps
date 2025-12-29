"""Small structured logging helper.

The codebase primarily logs JSON strings so it can be consumed by any log
collector without introducing new dependencies.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from src.core.request_context import get_request_id


def log_json(
    logger: logging.Logger,
    level: int,
    event: str,
    **fields: Any,
) -> None:
    """Emit a single JSON log line with optional request/task correlation ID."""

    payload: dict[str, Any] = {
        "timestamp": datetime.now(UTC).isoformat(),
        "event": event,
    }
    request_id = get_request_id()
    if request_id:
        payload["request_id"] = request_id

    payload.update(fields)
    logger.log(level, json.dumps(payload, default=str))

