"""User service for managing user CRUD operations and RBAC."""
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.enums import AuditAction, UserRole
from src.models.user import User
from src.services.audit_service import AuditService


class UserService:
    """Service for user management operations."""

    def __init__(self, db: AsyncSession):
        """Initialize user service.

        Args:
            db: Database session
        """
        self.db = db
        self.audit_service = AuditService(db)

    async def list_users(
        self,
        org_id: UUID,
        role_filter: str | None = None,
    ) -> list[User]:
        """List all users in an organization.

        Args:
            org_id: Organization ID
            role_filter: Optional role to filter by

        Returns:
            List of User instances
        """
        query = select(User).where(User.org_id == org_id)

        # Apply role filter if provided
        if role_filter:
            try:
                role_enum = UserRole(role_filter)
                query = query.where(User.role == role_enum)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid role: {role_filter}"
                ) from None

        result = await self.db.execute(query)
        users = result.scalars().all()
        return list(users)

    async def get_user(
        self,
        user_id: UUID,
        org_id: UUID,
    ) -> User:
        """Get a specific user by ID.

        Args:
            user_id: User ID
            org_id: Organization ID (for access control)

        Returns:
            User instance

        Raises:
            HTTPException: 404 if user not found or not in org
        """
        result = await self.db.execute(
            select(User).where(
                and_(
                    User.id == user_id,
                    User.org_id == org_id
                )
            )
        )
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        return user

    async def _count_admins(self, org_id: UUID) -> int:
        """Count number of admin users in an organization.

        Args:
            org_id: Organization ID

        Returns:
            Number of active admin users
        """
        result = await self.db.execute(
            select(func.count(User.id)).where(
                and_(
                    User.org_id == org_id,
                    User.role == UserRole.ADMIN,
                    User.is_active.is_(True)
                )
            )
        )
        return result.scalar_one()

    async def _is_last_admin(self, user: User) -> bool:
        """Check if user is the last admin in their organization.

        Args:
            user: User to check

        Returns:
            True if user is the last active admin
        """
        if user.role != UserRole.ADMIN or not user.is_active:
            return False

        admin_count = await self._count_admins(user.org_id)
        return admin_count == 1

    async def update_user(
        self,
        user_id: UUID,
        org_id: UUID,
        current_user: User,
        role: str | None = None,
        is_active: bool | None = None,
    ) -> User:
        """Update user information.

        Args:
            user_id: User ID to update
            org_id: Organization ID (for access control)
            current_user: User performing the update
            role: New role (admin-only)
            is_active: New active status (admin-only)

        Returns:
            Updated User instance

        Raises:
            HTTPException: 400 if trying to demote last admin
            HTTPException: 403 if insufficient permissions
            HTTPException: 404 if user not found
        """
        # Get the user to update
        user = await self.get_user(user_id, org_id)

        # Track changes for audit
        changes = {}
        old_role = user.role.value

        # Update role if provided
        if role is not None:
            # Check if trying to demote the last admin (FR-A09)
            if user.role == UserRole.ADMIN and role != "admin":
                if await self._is_last_admin(user):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Cannot demote the last admin in the organization"
                    )

            try:
                new_role = UserRole(role)
                user.role = new_role
                changes["role"] = {"old": old_role, "new": role}
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid role: {role}"
                ) from None

        # Update active status if provided
        if is_active is not None:
            old_active = user.is_active
            user.is_active = is_active
            changes["is_active"] = {"old": old_active, "new": is_active}

        # Flush changes
        await self.db.flush()

        # Audit logging
        if changes:
            # Log role change separately if it happened
            if "role" in changes:
                await self.audit_service.log(
                    org_id=org_id,
                    user_id=current_user.id,
                    action=AuditAction.USER_ROLE_CHANGE,
                    entity_type="user",
                    entity_id=user.id,
                    diff_json={
                        "user_id": str(user.id),
                        "old_role": old_role,
                        "new_role": role,
                    }
                )

            # Log general user update
            await self.audit_service.log(
                org_id=org_id,
                user_id=current_user.id,
                action=AuditAction.USER_UPDATE,
                entity_type="user",
                entity_id=user.id,
                diff_json=changes
            )

        return user

    async def delete_user(
        self,
        user_id: UUID,
        org_id: UUID,
        current_user: User,
    ) -> None:
        """Delete a user.

        Args:
            user_id: User ID to delete
            org_id: Organization ID (for access control)
            current_user: User performing the deletion

        Raises:
            HTTPException: 400 if trying to delete last admin
            HTTPException: 404 if user not found
        """
        # Get the user to delete
        user = await self.get_user(user_id, org_id)

        # Check if trying to delete the last admin (FR-A09)
        if await self._is_last_admin(user):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete the last admin in the organization"
            )

        # Audit log before deletion
        await self.audit_service.log(
            org_id=org_id,
            user_id=current_user.id,
            action=AuditAction.USER_DELETE,
            entity_type="user",
            entity_id=user.id,
            diff_json={
                "email": user.email,
                "role": user.role.value,
            }
        )

        # Delete the user
        await self.db.delete(user)
        await self.db.flush()
