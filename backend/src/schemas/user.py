"""Pydantic schemas for user management endpoints.

Schemas for user CRUD operations and RBAC.
"""
from datetime import datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class UserResponse(BaseModel):
    """Response schema for user information.

    Used for GET /users/{user_id} and user-related endpoints.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="User unique identifier")
    email: str = Field(..., description="User email address")
    role: str = Field(..., description="User role (admin, editor, reviewer, viewer)")
    is_active: bool = Field(..., description="Whether user account is active")
    last_login_at: Optional[datetime] = Field(None, description="Last login timestamp")
    created_at: datetime = Field(..., description="Account creation timestamp")


class UserListResponse(BaseModel):
    """Response schema for listing users.

    Used for GET /users endpoint.
    Returns a list of UserResponse objects.
    """

    model_config = ConfigDict(from_attributes=True)

    users: list[UserResponse] = Field(
        default_factory=list,
        description="List of users"
    )
    total: int = Field(..., description="Total number of users")


class UserUpdateRequest(BaseModel):
    """Request schema for updating user information.

    Used for PATCH /users/{user_id} endpoint.
    All fields are optional for partial updates.
    """

    model_config = ConfigDict(from_attributes=True)

    role: Optional[str] = Field(
        None,
        description="User role (admin, editor, reviewer, viewer). Admin-only.",
        pattern="^(admin|editor|reviewer|viewer)$"
    )
    is_active: Optional[bool] = Field(
        None,
        description="Account active status. Admin-only."
    )
