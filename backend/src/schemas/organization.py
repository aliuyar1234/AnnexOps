"""Pydantic schemas for organization endpoints.

Schemas match the OpenAPI contract defined in specs/001-org-auth/contracts/openapi.yaml
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class CreateOrganizationRequest(BaseModel):
    """Request schema for creating an organization (bootstrap).

    Used for POST /organizations endpoint.
    Creates organization with initial admin user.
    """

    name: str = Field(..., min_length=1, max_length=255, description="Organization display name")
    admin_email: EmailStr = Field(..., description="Email address for the initial admin user")
    admin_password: str = Field(
        ..., min_length=8, description="Password for the initial admin user"
    )

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        """Validate that name is not empty or whitespace only."""
        if not v or not v.strip():
            raise ValueError("Organization name cannot be empty")
        return v.strip()


class OrganizationUpdateRequest(BaseModel):
    """Request schema for updating an organization.

    Used for PATCH /organizations/{org_id} endpoint.
    All fields are optional (partial update).
    """

    name: str | None = Field(
        None, min_length=1, max_length=255, description="Organization display name"
    )

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str | None) -> str | None:
        """Validate that name is not empty or whitespace only if provided."""
        if v is not None and (not v or not v.strip()):
            raise ValueError("Organization name cannot be empty")
        return v.strip() if v else None


class OrganizationResponse(BaseModel):
    """Response schema for organization endpoints.

    Used for GET and POST responses.
    Matches OpenAPI spec OrganizationResponse.
    """

    id: UUID = Field(..., description="Organization unique identifier")
    name: str = Field(..., description="Organization display name")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last modification timestamp")

    model_config = ConfigDict(from_attributes=True)
