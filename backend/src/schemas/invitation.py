"""Pydantic schemas for invitation endpoints.

Schemas match the OpenAPI contract for invitation-related endpoints.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from src.models.enums import UserRole


class InviteRequest(BaseModel):
    """Request schema for creating an invitation.

    Used for POST /auth/invite endpoint.
    """

    email: EmailStr = Field(..., description="Email address of the user to invite")
    role: UserRole = Field(..., description="Role to assign to the invited user")


class InvitationResponse(BaseModel):
    """Response schema for invitation creation.

    Used for POST /auth/invite response.
    Contains invitation details including plaintext token for email.
    """

    id: UUID = Field(..., description="Invitation unique identifier")
    email: str = Field(..., description="Invitee email address")
    role: str = Field(..., description="Assigned role")
    token: str = Field(..., description="Invitation token (plaintext, for email)")
    expires_at: datetime = Field(..., description="Invitation expiry timestamp")

    model_config = ConfigDict(from_attributes=True)


class AcceptInviteRequest(BaseModel):
    """Request schema for accepting an invitation.

    Used for POST /auth/accept-invite endpoint.
    """

    token: str = Field(..., min_length=32, description="Invitation token from email")
    password: str = Field(..., min_length=8, description="Password for new user account")


class AcceptInviteResponse(BaseModel):
    """Response schema for accepting an invitation.

    Used for POST /auth/accept-invite response.
    Returns the newly created user information.
    """

    id: UUID = Field(..., description="User unique identifier")
    email: str = Field(..., description="User email address")
    role: str = Field(..., description="User role")
    org_id: UUID = Field(..., description="Organization ID")
    is_active: bool = Field(..., description="Account active status")
    created_at: datetime = Field(..., description="Account creation timestamp")

    model_config = ConfigDict(from_attributes=True)
