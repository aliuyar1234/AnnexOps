"""Invitation service for user invitation management.

Handles invitation creation, validation, acceptance, and expiry checks.
Implements security measures per research.md:
- Secure random tokens using secrets.token_urlsafe(32)
- SHA-256 hash storage
- 7-day expiry per FR-A10
- Single-use tokens
- Duplicate prevention
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import hash_password, validate_password, PasswordValidationError
from src.models.enums import AuditAction, UserRole
from src.models.invitation import Invitation
from src.models.user import User
from src.services.audit_service import AuditService


class InvitationService:
    """Service for managing user invitations."""

    def __init__(self, db: AsyncSession):
        """Initialize invitation service.

        Args:
            db: Database session
        """
        self.db = db
        self.audit_service = AuditService(db)

    async def create_invitation(
        self,
        email: str,
        role: UserRole,
        invited_by_user: User,
        ip_address: str | None = None
    ) -> tuple[Invitation, str]:
        """Create a new invitation.

        Generates secure token, stores hash in database, returns plaintext
        token for email. Validates that user doesn't already exist and no
        duplicate pending invitation exists.

        Args:
            email: Email address to invite
            role: Role to assign to invited user
            invited_by_user: Admin user creating the invitation
            ip_address: IP address of the admin (for audit)

        Returns:
            Tuple of (Invitation instance, plaintext token)

        Raises:
            HTTPException: 400 if user exists or duplicate invitation
        """
        # Check if user already exists in organization
        existing_user = await self._get_user_by_email(email, invited_by_user.org_id)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User with email {email} already exists in organization"
            )

        # Check for duplicate pending invitation
        existing_invitation = await self._get_pending_invitation(email, invited_by_user.org_id)
        if existing_invitation:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User with email {email} has already been invited"
            )

        # Generate secure token
        token = secrets.token_urlsafe(32)  # 256-bit entropy
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        # Create invitation with 7-day expiry
        invitation = Invitation(
            org_id=invited_by_user.org_id,
            email=email,
            role=role,
            token_hash=token_hash,
            invited_by=invited_by_user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7)
        )

        self.db.add(invitation)
        await self.db.flush()

        # Log audit event
        await self.audit_service.log(
            org_id=invited_by_user.org_id,
            action=AuditAction.INVITATION_CREATE,
            entity_type="invitation",
            entity_id=invitation.id,
            user_id=invited_by_user.id,
            ip_address=ip_address,
            diff_json={
                "email": email,
                "role": role.value,
                "expires_at": invitation.expires_at.isoformat()
            }
        )

        return invitation, token

    async def accept_invitation(
        self,
        token: str,
        password: str,
        ip_address: str | None = None
    ) -> User:
        """Accept an invitation and create user account.

        Validates token, checks expiry, ensures single-use, creates user
        with assigned role, and marks invitation as accepted.

        Args:
            token: Plaintext invitation token
            password: Password for new user account
            ip_address: IP address of the invitee (for audit)

        Returns:
            Created User instance

        Raises:
            HTTPException: 400 if token invalid, expired, or already used
        """
        # Validate token and get invitation
        invitation = await self._validate_token(token)

        # Check if invitation has expired
        if invitation.expires_at < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invitation has expired"
            )

        # Check if invitation has already been accepted (single-use)
        if invitation.accepted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invitation has already been accepted"
            )

        # Validate password
        try:
            validate_password(password)
        except PasswordValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )

        # Create user account
        user = User(
            org_id=invitation.org_id,
            email=invitation.email,
            password_hash=hash_password(password),
            role=invitation.role,
            is_active=True
        )

        self.db.add(user)
        await self.db.flush()

        # Mark invitation as accepted
        invitation.accepted_at = datetime.now(timezone.utc)
        await self.db.flush()

        # Log audit event
        await self.audit_service.log(
            org_id=user.org_id,
            action=AuditAction.INVITATION_ACCEPT,
            entity_type="invitation",
            entity_id=invitation.id,
            user_id=user.id,
            ip_address=ip_address,
            diff_json={
                "email": user.email,
                "role": user.role.value,
                "accepted_at": invitation.accepted_at.isoformat()
            }
        )

        return user

    async def _validate_token(self, token: str) -> Invitation:
        """Validate invitation token and return invitation.

        Args:
            token: Plaintext invitation token

        Returns:
            Invitation instance if valid

        Raises:
            HTTPException: 400 if token is invalid
        """
        # Hash token for lookup
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        # Find invitation by token hash
        result = await self.db.execute(
            select(Invitation).where(Invitation.token_hash == token_hash)
        )
        invitation = result.scalar_one_or_none()

        if not invitation:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid invitation token"
            )

        return invitation

    async def _get_user_by_email(self, email: str, org_id: UUID) -> User | None:
        """Get user by email within organization.

        Args:
            email: User email
            org_id: Organization ID

        Returns:
            User instance if found, None otherwise
        """
        result = await self.db.execute(
            select(User).where(
                User.email == email,
                User.org_id == org_id
            )
        )
        return result.scalar_one_or_none()

    async def _get_pending_invitation(self, email: str, org_id: UUID) -> Invitation | None:
        """Get pending invitation by email within organization.

        Args:
            email: Invitation email
            org_id: Organization ID

        Returns:
            Invitation instance if pending invitation found, None otherwise
        """
        result = await self.db.execute(
            select(Invitation).where(
                Invitation.email == email,
                Invitation.org_id == org_id,
                Invitation.accepted_at.is_(None),  # Not yet accepted
                Invitation.expires_at > datetime.now(timezone.utc)  # Not expired
            )
        )
        return result.scalar_one_or_none()
