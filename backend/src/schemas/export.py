"""Schemas for export endpoints."""
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class CreateExportRequest(BaseModel):
    """Request schema for creating an export."""

    include_diff: bool = Field(
        default=False,
        description="Whether to include diff compared to another version"
    )
    compare_version_id: UUID | None = Field(
        default=None,
        description="Version ID to compare against (required if include_diff=true)"
    )


class ExportResponse(BaseModel):
    """Response model for export entity."""

    id: UUID
    version_id: UUID
    export_type: str
    snapshot_hash: str
    storage_uri: str
    file_size: int
    include_diff: bool
    compare_version_id: UUID | None
    completeness_score: Decimal
    created_by: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ExportListResponse(BaseModel):
    """Response model for listing exports."""

    items: list[ExportResponse] = Field(default_factory=list)
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=1000)
    offset: int = Field(ge=0)
