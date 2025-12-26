"""FastAPI dependencies for authentication and authorization."""
from typing import Callable
from datetime import datetime, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.core.database import get_db
from src.core.security import decode_token
from src.models.user import User
from src.models.enums import UserRole

# HTTP Bearer token security scheme
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get current authenticated user from JWT token.

    Args:
        credentials: HTTP Bearer credentials from request
        db: Database session

    Returns:
        Authenticated User instance

    Raises:
        HTTPException: 401 if token is invalid or user not found
        HTTPException: 403 if account is locked or inactive
    """
    # Decode token
    token = credentials.credentials
    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    # Extract user ID from token
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    # Fetch user from database
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    # Check if account is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    # Check if account is locked
    if user.locked_until and user.locked_until > datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Account is locked until {user.locked_until.isoformat()}",
        )

    return user


def require_role(minimum_role: UserRole) -> Callable:
    """Dependency factory for role-based access control.

    Creates a dependency that checks if the current user has sufficient
    permissions based on role hierarchy.

    Args:
        minimum_role: Minimum role required for access

    Returns:
        FastAPI dependency function

    Example:
        @router.post("/systems")
        async def create_system(
            user: User = Depends(require_role(UserRole.EDITOR))
        ):
            # Only EDITOR and ADMIN can access
            pass
    """

    async def check_role(
        current_user: User = Depends(get_current_user),
    ) -> User:
        """Check if current user has required role.

        Args:
            current_user: Authenticated user from get_current_user

        Returns:
            User instance if authorized

        Raises:
            HTTPException: 403 if user doesn't have sufficient permissions
        """
        if not current_user.role.has_permission(minimum_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Requires {minimum_role.value} or higher.",
            )
        return current_user

    return check_role


def require_admin() -> Callable:
    """Dependency for endpoints that require admin role.

    Returns:
        FastAPI dependency function that requires ADMIN role
    """
    return require_role(UserRole.ADMIN)


def require_editor() -> Callable:
    """Dependency for endpoints that require editor role or higher.

    Returns:
        FastAPI dependency function that requires EDITOR or ADMIN role
    """
    return require_role(UserRole.EDITOR)


def require_reviewer() -> Callable:
    """Dependency for endpoints that require reviewer role or higher.

    Returns:
        FastAPI dependency function that requires REVIEWER, EDITOR, or ADMIN role
    """
    return require_role(UserRole.REVIEWER)
