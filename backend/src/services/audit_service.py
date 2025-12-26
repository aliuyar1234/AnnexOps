"""Audit service for logging administrative actions."""
from typing import Optional, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.audit_event import AuditEvent
from src.models.enums import AuditAction


class AuditService:
    """Service for creating and managing audit trail entries."""

    def __init__(self, db: AsyncSession):
        """Initialize audit service.

        Args:
            db: Database session
        """
        self.db = db

    async def log(
        self,
        org_id: UUID,
        action: AuditAction,
        entity_type: str,
        entity_id: UUID,
        user_id: Optional[UUID] = None,
        diff_json: Optional[dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> AuditEvent:
        """Create an audit log entry.

        Args:
            org_id: Organization ID
            action: Action being performed
            entity_type: Type of entity being acted upon
            entity_id: ID of entity being acted upon
            user_id: ID of user performing action (None for system actions)
            diff_json: Before/after diff for update actions
            ip_address: Client IP address

        Returns:
            Created AuditEvent instance
        """
        audit_event = AuditEvent(
            org_id=org_id,
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            diff_json=diff_json,
            ip_address=ip_address,
        )
        self.db.add(audit_event)
        await self.db.flush()
        return audit_event

    async def log_user_login(
        self,
        org_id: UUID,
        user_id: UUID,
        ip_address: Optional[str] = None,
        success: bool = True,
    ) -> AuditEvent:
        """Log a user login attempt.

        Args:
            org_id: Organization ID
            user_id: User ID
            ip_address: Client IP address
            success: Whether login was successful

        Returns:
            Created AuditEvent instance
        """
        action = AuditAction.USER_LOGIN if success else AuditAction.USER_LOCKOUT
        return await self.log(
            org_id=org_id,
            user_id=user_id,
            action=action,
            entity_type="user",
            entity_id=user_id,
            ip_address=ip_address,
        )

    async def log_user_logout(
        self,
        org_id: UUID,
        user_id: UUID,
        ip_address: Optional[str] = None,
    ) -> AuditEvent:
        """Log a user logout.

        Args:
            org_id: Organization ID
            user_id: User ID
            ip_address: Client IP address

        Returns:
            Created AuditEvent instance
        """
        return await self.log(
            org_id=org_id,
            user_id=user_id,
            action=AuditAction.USER_LOGOUT,
            entity_type="user",
            entity_id=user_id,
            ip_address=ip_address,
        )

    async def log_organization_create(
        self,
        org_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> AuditEvent:
        """Log organization creation.

        Args:
            org_id: Organization ID
            user_id: ID of user who created (None for bootstrap)

        Returns:
            Created AuditEvent instance
        """
        return await self.log(
            org_id=org_id,
            user_id=user_id,
            action=AuditAction.ORG_CREATE,
            entity_type="organization",
            entity_id=org_id,
        )

    async def log_organization_update(
        self,
        org_id: UUID,
        user_id: UUID,
        diff: Optional[dict[str, Any]] = None,
    ) -> AuditEvent:
        """Log organization update.

        Args:
            org_id: Organization ID
            user_id: ID of user who updated
            diff: Before/after diff

        Returns:
            Created AuditEvent instance
        """
        return await self.log(
            org_id=org_id,
            user_id=user_id,
            action=AuditAction.ORG_UPDATE,
            entity_type="organization",
            entity_id=org_id,
            diff_json=diff,
        )
