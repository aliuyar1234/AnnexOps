"""Pydantic schemas for attachment endpoints."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from src.schemas.ai_system import UserSummary


class AttachmentResponse(BaseModel):
    """Response schema for system attachment."""

    id: UUID
    title: str
    description: Optional[str] = None
    file_size: int
    mime_type: str
    uploaded_by: Optional[UserSummary] = None
    created_at: datetime

    class Config:
        from_attributes = True
