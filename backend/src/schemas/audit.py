"""Pydantic schemas for audit log endpoints."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from src.models.enums import AuditAction, UserRole


class AuditUserSummary(BaseModel):
    """Minimal user info for audit entries."""

    id: UUID
    email: str
    role: UserRole

    model_config = ConfigDict(from_attributes=True)


class AuditEventListItem(BaseModel):
    """List item for audit events."""

    id: UUID
    created_at: datetime
    user: AuditUserSummary | None = None
    action: AuditAction
    entity_type: str
    entity_id: UUID
    ip_address: str | None = None

    model_config = ConfigDict(from_attributes=True)


class AuditEventListResponse(BaseModel):
    """Paginated list response for audit events."""

    items: list[AuditEventListItem]
    total: int
    limit: int
    offset: int


class AuditEventDetailResponse(BaseModel):
    """Detail response for a single audit event."""

    id: UUID
    created_at: datetime
    user: AuditUserSummary | None = None
    action: AuditAction
    entity_type: str
    entity_id: UUID
    ip_address: str | None = None
    diff_json: dict[str, Any] | None = None

    model_config = ConfigDict(from_attributes=True)

