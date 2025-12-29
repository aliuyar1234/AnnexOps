"""Pydantic schemas for section review comments."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CommentAuthor(BaseModel):
    """Minimal user info for comment authors."""

    id: UUID
    email: str

    model_config = ConfigDict(from_attributes=True)


class CreateSectionCommentRequest(BaseModel):
    """Request schema for creating a comment on a section."""

    model_config = ConfigDict(extra="forbid")

    comment: str = Field(..., min_length=1, max_length=2000)

    @field_validator("comment")
    @classmethod
    def strip_comment(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("comment cannot be empty")
        return v


class SectionCommentResponse(BaseModel):
    """Response schema for a section comment."""

    id: UUID
    version_id: UUID
    section_key: str
    comment: str
    author: CommentAuthor | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SectionCommentListResponse(BaseModel):
    """Paginated list response for section comments."""

    items: list[SectionCommentResponse]
    total: int
    limit: int
    offset: int
