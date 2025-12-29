"""Pydantic schemas for System Version endpoints."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.models.enums import VersionStatus


class UserSummary(BaseModel):
    """Minimal user information for embedding in responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str


class CreateVersionRequest(BaseModel):
    """Request schema for creating a system version."""

    model_config = ConfigDict(extra="forbid")

    label: str = Field(..., min_length=1, max_length=50)
    notes: str | None = Field(None, max_length=5000)

    @field_validator("label")
    @classmethod
    def strip_label(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("label cannot be empty")
        return v

    @field_validator("notes")
    @classmethod
    def strip_notes(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None


class VersionResponse(BaseModel):
    """Response schema for system version."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ai_system_id: UUID
    label: str
    status: VersionStatus
    release_date: date | None = None
    notes: str | None = None
    created_by: UserSummary | None = None
    created_at: datetime
    updated_at: datetime


class VersionListResponse(BaseModel):
    """Paginated list response for versions."""

    items: list[VersionResponse]
    total: int


class StatusChangeRequest(BaseModel):
    """Request schema for changing version status."""

    model_config = ConfigDict(extra="forbid")

    status: VersionStatus
    comment: str | None = Field(None, max_length=2000)

    @field_validator("comment")
    @classmethod
    def strip_comment(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None


class VersionSummary(BaseModel):
    """Minimal version information for embedding in diff responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    label: str
    status: VersionStatus


class FieldChange(BaseModel):
    """Represents a single field change between versions."""

    field: str
    old_value: str | None = None
    new_value: str | None = None


class DiffSummary(BaseModel):
    """Summary counts for version diff."""

    added: int
    removed: int
    modified: int


class VersionDiffResponse(BaseModel):
    """Response schema for version comparison."""

    from_version: VersionSummary
    to_version: VersionSummary
    changes: list[FieldChange]
    summary: DiffSummary


class UpdateVersionRequest(BaseModel):
    """Request schema for updating a system version."""

    model_config = ConfigDict(extra="forbid")

    notes: str | None = Field(None, max_length=5000)
    release_date: date | None = None

    @field_validator("notes")
    @classmethod
    def strip_notes(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None


class VersionDetailResponse(VersionResponse):
    """Detailed response schema for single version with related counts.

    Extends VersionResponse with additional fields:
    - section_count: Number of sections (placeholder for Module E)
    - evidence_count: Number of evidence items (placeholder for Module D)
    """

    section_count: int = 0
    evidence_count: int = 0


class CloneVersionRequest(BaseModel):
    """Request schema for cloning a system version."""

    model_config = ConfigDict(extra="forbid")

    label: str = Field(..., min_length=1, max_length=50, pattern=r"^[a-zA-Z0-9._-]+$")

    @field_validator("label")
    @classmethod
    def strip_label(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("label cannot be empty")
        return v
