"""Pydantic schemas for attachment endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from src.schemas.ai_system import UserSummary


class AttachmentResponse(BaseModel):
    """Response schema for system attachment."""

    id: UUID
    title: str
    description: str | None = None
    file_size: int
    mime_type: str
    uploaded_by: UserSummary | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
