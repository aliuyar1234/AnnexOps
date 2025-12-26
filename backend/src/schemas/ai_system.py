"""Pydantic schemas for AI System endpoints."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from src.models.enums import HRUseCaseType, DeploymentType, DecisionInfluence


class UserSummary(BaseModel):
    """Minimal user information for embedding in responses."""

    id: UUID
    email: str

    class Config:
        from_attributes = True


class CreateSystemRequest(BaseModel):
    """Request schema for creating an AI system."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    hr_use_case_type: HRUseCaseType
    intended_purpose: str = Field(..., min_length=1)
    deployment_type: DeploymentType
    decision_influence: DecisionInfluence
    contact_name: Optional[str] = Field(None, max_length=255)
    contact_email: Optional[EmailStr] = None


class UpdateSystemRequest(BaseModel):
    """Request schema for updating an AI system."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    hr_use_case_type: Optional[HRUseCaseType] = None
    intended_purpose: Optional[str] = Field(None, min_length=1)
    deployment_type: Optional[DeploymentType] = None
    decision_influence: Optional[DecisionInfluence] = None
    contact_name: Optional[str] = Field(None, max_length=255)
    contact_email: Optional[EmailStr] = None
    expected_version: Optional[int] = Field(
        None,
        description="For optimistic locking - must match current version",
    )


class SystemResponse(BaseModel):
    """Response schema for AI system."""

    id: UUID
    name: str
    description: Optional[str] = None
    hr_use_case_type: HRUseCaseType
    intended_purpose: str
    deployment_type: DeploymentType
    decision_influence: DecisionInfluence
    owner: Optional[UserSummary] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    version: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SystemDetailResponse(SystemResponse):
    """Extended response with additional details for single system view."""

    latest_assessment: Optional["AssessmentSummary"] = None
    attachment_count: int = 0
    version_count: int = 0


class SystemListResponse(BaseModel):
    """Paginated list response for systems."""

    items: list[SystemResponse]
    total: int


class AssessmentSummary(BaseModel):
    """Summary of a high-risk assessment for embedding."""

    id: UUID
    result_label: str
    score: int
    created_at: datetime

    class Config:
        from_attributes = True


# Update forward reference
SystemDetailResponse.model_rebuild()
