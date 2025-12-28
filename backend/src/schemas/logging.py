"""Pydantic schemas for Logging Collector (Module F)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EnableLoggingRequest(BaseModel):
    """Request schema for enabling logging on a system version."""

    name: str = Field(..., min_length=1, max_length=100)


class ApiKeyResponse(BaseModel):
    """Response schema for created API key (shown once)."""

    key_id: UUID
    api_key: str
    endpoint: str


class LogIngestResponse(BaseModel):
    """Response schema for ingest endpoint."""

    id: UUID


class LogListItem(BaseModel):
    """List item for stored decision logs."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_id: str
    event_time: datetime
    actor: str
    decision: str | None = None
    ingested_at: datetime


class LogListResponse(BaseModel):
    """Paginated list response for decision logs."""

    items: list[LogListItem]
    total: int
    limit: int
    offset: int


class LogDetailResponse(BaseModel):
    """Detail response for a single decision log entry."""

    id: UUID
    event_id: str
    event_time: datetime
    actor: str
    ingested_at: datetime
    event_json: dict[str, Any]

