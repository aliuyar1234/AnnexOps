"""Public ingest routes for Logging Collector (Module F)."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_log_api_key
from src.core.config import get_settings
from src.core.database import get_db
from src.models.log_api_key import LogApiKey
from src.schemas.logging import LogIngestResponse
from src.services.logging_service import LoggingService

router = APIRouter()
settings = get_settings()

# In-memory rate limiting storage (production-only safeguard)
_ingest_requests: dict[str, list[datetime]] = defaultdict(list)


async def rate_limit_ingest(
    request: Request,
    api_key: LogApiKey = Depends(get_log_api_key),
) -> None:
    """Basic rate limiting for ingest endpoint (per API key, production only)."""
    if settings.environment != "production":
        return

    identifier = str(api_key.id)
    window = timedelta(minutes=1)
    limit = 120

    now = datetime.now(UTC)
    cutoff = now - window
    _ingest_requests[identifier] = [ts for ts in _ingest_requests[identifier] if ts > cutoff]
    if len(_ingest_requests[identifier]) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many ingest requests. Please try again later.",
        )
    _ingest_requests[identifier].append(now)


@router.post(
    "/logs",
    response_model=LogIngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a decision event (API key auth)",
)
async def ingest_log(
    payload: dict,
    api_key: LogApiKey = Depends(get_log_api_key),
    _: None = Depends(rate_limit_ingest),
    db: AsyncSession = Depends(get_db),
) -> LogIngestResponse:
    """Ingest a decision event using per-version API key authentication."""
    service = LoggingService(db)
    log = await service.ingest_event(
        api_key=api_key, raw_event=payload, allow_raw_pii=settings.allow_raw_pii
    )
    await db.commit()
    return LogIngestResponse(id=log.id)
