"""Schemas for export endpoints."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CreateExportRequest(BaseModel):
    """Request schema for creating an export."""

    model_config = ConfigDict(extra="forbid")

    include_diff: bool = Field(
        default=False, description="Whether to include diff compared to another version"
    )
    compare_version_id: UUID | None = Field(
        default=None, description="Version ID to compare against (required if include_diff=true)"
    )

    @model_validator(mode="after")
    def validate_diff_request(self) -> "CreateExportRequest":
        if self.include_diff and not self.compare_version_id:
            raise ValueError("compare_version_id is required when include_diff=true")
        if not self.include_diff and self.compare_version_id is not None:
            raise ValueError("compare_version_id must be omitted when include_diff=false")
        return self


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

    model_config = ConfigDict(from_attributes=True)


class ExportListResponse(BaseModel):
    """Response model for listing exports."""

    items: list[ExportResponse] = Field(default_factory=list)
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=1000)
    offset: int = Field(ge=0)


class DownloadUrlResponse(BaseModel):
    """Response model for presigned download URLs."""

    download_url: str
    expires_in: int = 3600
