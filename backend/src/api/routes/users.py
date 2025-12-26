"""User management endpoints."""
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.database import get_db
from src.api.deps import get_current_user, require_admin
from src.models.user import User
from src.schemas.user import UserResponse, UserUpdateRequest
from src.services.user_service import UserService

router = APIRouter()


@router.get("", response_model=list[UserResponse])
async def list_users(
    role: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all users in the organization.

    Any authenticated user can list users. Optional role filter.

    Args:
        role: Optional role filter (admin, editor, reviewer, viewer)
        current_user: Current authenticated user
        db: Database session

    Returns:
        List of users in the organization
    """
    user_service = UserService(db)
    users = await user_service.list_users(
        org_id=current_user.org_id,
        role_filter=role
    )

    return [
        UserResponse(
            id=user.id,
            email=user.email,
            role=user.role.value,
            is_active=user.is_active,
            last_login_at=user.last_login_at,
            created_at=user.created_at
        )
        for user in users
    ]


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get detailed information about a specific user.

    Any authenticated user can view user details.

    Args:
        user_id: User ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        User details
    """
    user_service = UserService(db)
    user = await user_service.get_user(
        user_id=user_id,
        org_id=current_user.org_id
    )

    return UserResponse(
        id=user.id,
        email=user.email,
        role=user.role.value,
        is_active=user.is_active,
        last_login_at=user.last_login_at,
        created_at=user.created_at
    )


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    update_data: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update user information.

    Only admins can change roles and is_active status.
    Users can update their own non-role fields (future: profile info).

    Args:
        user_id: User ID to update
        update_data: Fields to update
        current_user: Current authenticated user
        db: Database session

    Returns:
        Updated user information

    Raises:
        403: If non-admin tries to change role or is_active
        400: If trying to demote last admin
    """
    from src.models.enums import UserRole
    from fastapi import HTTPException

    # Check if trying to update role or is_active
    if update_data.role is not None or update_data.is_active is not None:
        # Only admin can change role or is_active
        if current_user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can change user roles or active status"
            )

    user_service = UserService(db)
    user = await user_service.update_user(
        user_id=user_id,
        org_id=current_user.org_id,
        current_user=current_user,
        role=update_data.role,
        is_active=update_data.is_active
    )

    await db.commit()

    return UserResponse(
        id=user.id,
        email=user.email,
        role=user.role.value,
        is_active=user.is_active,
        last_login_at=user.last_login_at,
        created_at=user.created_at
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    current_user: User = Depends(require_admin()),
    db: AsyncSession = Depends(get_db),
):
    """Delete a user.

    Admin-only operation. Cannot delete the last admin in the organization.

    Args:
        user_id: User ID to delete
        current_user: Current authenticated admin user
        db: Database session

    Returns:
        204 No Content on success

    Raises:
        403: If non-admin attempts deletion
        400: If trying to delete last admin
    """
    user_service = UserService(db)
    await user_service.delete_user(
        user_id=user_id,
        org_id=current_user.org_id,
        current_user=current_user
    )

    await db.commit()
