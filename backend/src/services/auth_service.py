"""Authentication service for login, logout, and session management."""

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from src.models.enums import AuditAction
from src.models.user import User
from src.services.audit_service import AuditService


class AuthService:
    """Service for authentication and session management."""

    # Lockout configuration
    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_DURATIONS = [1, 2, 4, 8, 15]  # Minutes, exponential backoff with 15min max

    def __init__(self, db: AsyncSession):
        """Initialize auth service.

        Args:
            db: Database session
        """
        self.db = db
        self.audit_service = AuditService(db)

    async def login(
        self, email: str, password: str, ip_address: str | None = None
    ) -> tuple[str, str, User]:
        """Authenticate user and create session tokens.

        Validates credentials, tracks failed attempts, handles account lockout,
        and creates access/refresh tokens on success.

        Args:
            email: User email address
            password: User password
            ip_address: Client IP address for audit logging

        Returns:
            Tuple of (access_token, refresh_token, user)

        Raises:
            HTTPException: 401 if credentials invalid
            HTTPException: 403 if account is inactive
            HTTPException: 423 if account is locked
        """
        # Find user by email
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if not user:
            # Don't reveal if user exists or not (security)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
            )

        # Check if account is active
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive")

        # Check if account is locked
        if user.locked_until and user.locked_until > datetime.now(UTC):
            # Log lockout attempt
            await self.audit_service.log(
                org_id=user.org_id,
                user_id=user.id,
                action=AuditAction.USER_LOCKOUT,
                entity_type="user",
                entity_id=user.id,
                ip_address=ip_address,
                diff_json={"locked_until": user.locked_until.isoformat()},
            )
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=f"Account is locked until {user.locked_until.isoformat()}",
            )

        # Verify password
        if not verify_password(password, user.password_hash):
            # Increment failed login attempts
            await self._handle_failed_login(user, ip_address)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
            )

        # Successful login - reset failed attempts and update last login
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login_at = datetime.now(UTC)
        await self.db.flush()

        # Create tokens
        token_data = {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value,
            "org_id": str(user.org_id),
        }
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token({"sub": str(user.id)})

        # Log successful login
        await self.audit_service.log_user_login(
            org_id=user.org_id, user_id=user.id, ip_address=ip_address, success=True
        )

        return access_token, refresh_token, user

    async def _handle_failed_login(self, user: User, ip_address: str | None = None):
        """Handle failed login attempt with exponential backoff lockout.

        Increments failed login counter and locks account if threshold exceeded.

        Args:
            user: User instance
            ip_address: Client IP address for audit logging
        """
        user.failed_login_attempts += 1

        # Check if we should lock the account
        if user.failed_login_attempts % self.MAX_FAILED_ATTEMPTS == 0:
            # Calculate lockout duration based on number of lockouts
            # Use number of times locked (approximated by attempts / MAX_FAILED_ATTEMPTS)
            lockout_index = min(
                (user.failed_login_attempts // self.MAX_FAILED_ATTEMPTS) - 1,
                len(self.LOCKOUT_DURATIONS) - 1,
            )
            lockout_minutes = self.LOCKOUT_DURATIONS[lockout_index]

            # Set lockout expiration
            user.locked_until = datetime.now(UTC) + timedelta(minutes=lockout_minutes)

            # Log lockout event
            await self.audit_service.log(
                org_id=user.org_id,
                user_id=user.id,
                action=AuditAction.USER_LOCKOUT,
                entity_type="user",
                entity_id=user.id,
                ip_address=ip_address,
                diff_json={
                    "failed_attempts": user.failed_login_attempts,
                    "locked_until": user.locked_until.isoformat(),
                    "lockout_duration_minutes": lockout_minutes,
                },
            )

        await self.db.flush()

    async def refresh_access_token(self, refresh_token: str) -> str:
        """Create new access token from refresh token.

        Args:
            refresh_token: Valid refresh token

        Returns:
            New access token

        Raises:
            HTTPException: 401 if refresh token is invalid or expired
        """
        # Decode refresh token
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
            )

        # Get user ID from token
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload"
            )

        # Fetch user from database
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive"
            )

        # Create new access token
        token_data = {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value,
            "org_id": str(user.org_id),
        }
        access_token = create_access_token(token_data)

        return access_token

    async def logout(self, user: User, ip_address: str | None = None):
        """Log out user and invalidate session.

        Args:
            user: User instance
            ip_address: Client IP address for audit logging
        """
        # Log logout event
        await self.audit_service.log_user_logout(
            org_id=user.org_id, user_id=user.id, ip_address=ip_address
        )

        # Note: Refresh token invalidation is handled by clearing the cookie
        # In a more complex system, we might maintain a token blacklist
