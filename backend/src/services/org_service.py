"""Organization service for managing organizations and bootstrap."""
from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status
from src.models.organization import Organization
from src.models.user import User
from src.models.enums import UserRole, AuditAction
from src.core.security import hash_password, validate_password, PasswordValidationError
from src.services.audit_service import AuditService


class OrganizationService:
    """Service for creating and managing organizations."""

    def __init__(self, db: AsyncSession):
        """Initialize organization service.

        Args:
            db: Database session
        """
        self.db = db
        self.audit_service = AuditService(db)

    async def create(
        self,
        name: str,
        admin_email: str,
        admin_password: str
    ) -> Organization:
        """Create organization with initial admin user (bootstrap).

        This is the bootstrap operation that creates the first organization
        and its admin user. It enforces the single-tenant constraint: only
        one organization can exist (MVP limitation).

        Args:
            name: Organization name
            admin_email: Email for initial admin user
            admin_password: Password for initial admin user

        Returns:
            Created Organization instance

        Raises:
            HTTPException: 409 if an organization already exists
        """
        # Check if any organization exists (single-tenant MVP constraint)
        result = await self.db.execute(select(Organization))
        existing_org = result.scalar_one_or_none()
        if existing_org:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Organization already exists. Only one organization allowed in MVP."
            )

        # Validate admin password
        try:
            validate_password(admin_password)
        except PasswordValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )

        # Create organization
        organization = Organization(name=name)
        self.db.add(organization)
        await self.db.flush()  # Flush to get org ID for admin user

        # Create admin user
        admin_user = User(
            org_id=organization.id,
            email=admin_email,
            password_hash=hash_password(admin_password),
            role=UserRole.ADMIN,
            is_active=True
        )
        self.db.add(admin_user)
        await self.db.flush()

        # Log organization creation (user_id=None for bootstrap)
        await self.audit_service.log_organization_create(
            org_id=organization.id,
            user_id=None  # Bootstrap action, no authenticated user yet
        )

        await self.db.commit()
        await self.db.refresh(organization)

        return organization

    async def get_by_id(self, org_id: UUID) -> Organization:
        """Get organization by ID.

        Args:
            org_id: Organization ID

        Returns:
            Organization instance

        Raises:
            HTTPException: 404 if organization not found
        """
        result = await self.db.execute(
            select(Organization).where(Organization.id == org_id)
        )
        organization = result.scalar_one_or_none()

        if not organization:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found"
            )

        return organization

    async def update(
        self,
        org_id: UUID,
        user_id: UUID,
        name: Optional[str] = None
    ) -> Organization:
        """Update organization details.

        Args:
            org_id: Organization ID
            user_id: ID of user performing update (for audit)
            name: New organization name (optional)

        Returns:
            Updated Organization instance

        Raises:
            HTTPException: 404 if organization not found
        """
        # Get organization
        organization = await self.get_by_id(org_id)

        # Store old values for audit diff
        old_values = {"name": organization.name}

        # Update fields
        if name is not None:
            organization.name = name

        await self.db.flush()

        # Create audit log with diff
        new_values = {"name": organization.name}
        diff = {
            "before": old_values,
            "after": new_values
        }

        await self.audit_service.log_organization_update(
            org_id=organization.id,
            user_id=user_id,
            diff=diff
        )

        await self.db.commit()
        await self.db.refresh(organization)

        return organization
