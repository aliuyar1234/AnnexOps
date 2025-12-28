"""Pydantic schemas for authentication endpoints.

Schemas match the OpenAPI contract defined in specs/001-org-auth/contracts/openapi.yaml
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    """Request schema for user login.

    Used for POST /auth/login endpoint.
    """

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="User password")


class TokenResponse(BaseModel):
    """Response schema for token endpoints.

    Used for POST /auth/login and POST /auth/refresh responses.
    Contains access token and metadata.
    """

    access_token: str = Field(..., description="JWT access token for API authentication")
    token_type: str = Field(default="bearer", description="Token type (always 'bearer')")
    expires_in: int | None = Field(default=None, description="Seconds until access token expires")


class UserResponse(BaseModel):
    """Response schema for user information.

    Used for GET /me and user-related endpoints.
    Matches OpenAPI spec UserResponse.
    """

    id: UUID = Field(..., description="User unique identifier")
    email: str = Field(..., description="User email address")
    role: str = Field(..., description="User role (admin, editor, reviewer, viewer)")
    is_active: bool = Field(..., description="Whether user account is active")
    last_login_at: datetime | None = Field(None, description="Last login timestamp")
    created_at: datetime = Field(..., description="Account creation timestamp")

    model_config = ConfigDict(from_attributes=True)


class LogoutResponse(BaseModel):
    """Response schema for logout endpoint.

    Used for POST /auth/logout response.
    """

    message: str = Field(
        default="Logged out successfully", description="Logout confirmation message"
    )
