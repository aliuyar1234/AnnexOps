"""Version service for CRUD operations on system versions."""
import re
from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.system_version import SystemVersion
from src.models.ai_system import AISystem
from src.models.enums import VersionStatus, AuditAction, UserRole
from src.models.user import User
from src.schemas.version import CreateVersionRequest, StatusChangeRequest, UpdateVersionRequest, CloneVersionRequest
from src.services.audit_service import AuditService
from src.core.version_workflow import is_valid_transition


class VersionService:
    """Service for managing system versions."""

    # Regex pattern for label validation
    # Alphanumeric + dots + dashes + underscores, 1-50 characters
    LABEL_PATTERN = re.compile(r'^[a-zA-Z0-9._-]{1,50}$')

    def __init__(self, db: AsyncSession):
        """Initialize version service.

        Args:
            db: Database session
        """
        self.db = db
        self.audit_service = AuditService(db)

    def _validate_label(self, label: str) -> None:
        """Validate version label format.

        Args:
            label: Version label to validate

        Raises:
            HTTPException: 422 if label is invalid
        """
        if not self.LABEL_PATTERN.match(label):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Version label must be 1-50 characters and contain only alphanumeric characters, dots, dashes, and underscores",
            )

    async def _check_duplicate_label(
        self,
        ai_system_id: UUID,
        label: str,
    ) -> None:
        """Check if version label already exists for this AI system.

        Args:
            ai_system_id: AI System ID
            label: Version label to check

        Raises:
            HTTPException: 409 if label already exists
        """
        query = select(SystemVersion).where(
            SystemVersion.ai_system_id == ai_system_id,
            SystemVersion.label == label,
        )
        result = await self.db.execute(query)
        existing = result.scalar_one_or_none()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Version with label '{label}' already exists for this AI system",
            )

    async def _get_ai_system(
        self,
        system_id: UUID,
        org_id: UUID,
    ) -> AISystem:
        """Get AI system by ID with org scoping.

        Args:
            system_id: System ID
            org_id: Organization ID for scoping

        Returns:
            AISystem instance

        Raises:
            HTTPException: 404 if system not found
        """
        query = (
            select(AISystem)
            .where(AISystem.id == system_id)
            .where(AISystem.org_id == org_id)
        )
        result = await self.db.execute(query)
        system = result.scalar_one_or_none()

        if not system:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="AI system not found",
            )

        return system

    async def create(
        self,
        system_id: UUID,
        request: CreateVersionRequest,
        current_user: User,
    ) -> SystemVersion:
        """Create a new system version.

        Args:
            system_id: AI System ID
            request: Version creation request
            current_user: User creating the version

        Returns:
            Created SystemVersion instance

        Raises:
            HTTPException: 404 if system not found
            HTTPException: 422 if label is invalid
            HTTPException: 409 if label already exists
        """
        # Verify system exists and user has access
        ai_system = await self._get_ai_system(system_id, current_user.org_id)

        # Validate label format
        self._validate_label(request.label)

        # Check for duplicate label
        await self._check_duplicate_label(system_id, request.label)

        # Create version
        version = SystemVersion(
            ai_system_id=system_id,
            label=request.label,
            status=VersionStatus.DRAFT,
            notes=request.notes,
            created_by=current_user.id,
        )

        self.db.add(version)

        try:
            await self.db.flush()
        except IntegrityError:
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Version with label '{request.label}' already exists for this AI system",
            )

        # Log audit event
        await self.audit_service.log(
            org_id=current_user.org_id,
            user_id=current_user.id,
            action=AuditAction.VERSION_CREATE,
            entity_type="system_version",
            entity_id=version.id,
            diff_json={
                "ai_system_id": str(system_id),
                "label": request.label,
                "status": VersionStatus.DRAFT.value,
            },
        )

        # Re-query with eager loading to ensure relationships are loaded
        query = (
            select(SystemVersion)
            .where(SystemVersion.id == version.id)
            .options(selectinload(SystemVersion.creator))
        )
        result = await self.db.execute(query)
        return result.scalar_one()

    async def list(
        self,
        system_id: UUID,
        org_id: UUID,
        status_filter: Optional[VersionStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[SystemVersion], int]:
        """List versions for an AI system.

        Args:
            system_id: AI System ID
            org_id: Organization ID for scoping
            status_filter: Optional status filter
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            Tuple of (versions list, total count)

        Raises:
            HTTPException: 404 if system not found
        """
        # Verify system exists and user has access
        await self._get_ai_system(system_id, org_id)

        # Base query
        query = (
            select(SystemVersion)
            .where(SystemVersion.ai_system_id == system_id)
            .options(selectinload(SystemVersion.creator))
            .order_by(SystemVersion.created_at.desc())
        )

        # Count query
        count_query = (
            select(func.count())
            .select_from(SystemVersion)
            .where(SystemVersion.ai_system_id == system_id)
        )

        # Apply filter
        if status_filter:
            query = query.where(SystemVersion.status == status_filter)
            count_query = count_query.where(SystemVersion.status == status_filter)

        # Apply pagination
        query = query.limit(limit).offset(offset)

        # Execute queries
        result = await self.db.execute(query)
        versions = list(result.scalars().all())

        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        return versions, total

    async def _get_version(
        self,
        system_id: UUID,
        version_id: UUID,
        org_id: UUID,
    ) -> SystemVersion:
        """Get version by ID with system and org scoping.

        Args:
            system_id: AI System ID
            version_id: Version ID
            org_id: Organization ID for scoping

        Returns:
            SystemVersion instance

        Raises:
            HTTPException: 404 if version not found
        """
        # First verify system exists and user has access
        await self._get_ai_system(system_id, org_id)

        # Then get the version
        query = (
            select(SystemVersion)
            .where(SystemVersion.id == version_id)
            .where(SystemVersion.ai_system_id == system_id)
            .options(selectinload(SystemVersion.creator))
        )
        result = await self.db.execute(query)
        version = result.scalar_one_or_none()

        if not version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Version not found",
            )

        return version

    async def _get_version_unscoped(
        self,
        version_id: UUID,
        org_id: UUID,
    ) -> SystemVersion:
        """Get version by ID with org scoping (no system filter).

        Args:
            version_id: Version ID
            org_id: Organization ID for scoping

        Returns:
            SystemVersion instance

        Raises:
            HTTPException: 404 if version not found
        """
        query = (
            select(SystemVersion)
            .join(AISystem, SystemVersion.ai_system_id == AISystem.id)
            .where(SystemVersion.id == version_id)
            .where(AISystem.org_id == org_id)
            .options(selectinload(SystemVersion.creator))
        )
        result = await self.db.execute(query)
        version = result.scalar_one_or_none()

        if not version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Version not found",
            )

        return version

    async def change_status(
        self,
        system_id: UUID,
        version_id: UUID,
        request: StatusChangeRequest,
        current_user: User,
    ) -> SystemVersion:
        """Change version status with workflow validation.

        Args:
            system_id: AI System ID
            version_id: Version ID
            request: Status change request with new status and optional comment
            current_user: User requesting the status change

        Returns:
            Updated SystemVersion instance

        Raises:
            HTTPException: 404 if version not found
            HTTPException: 409 if transition is invalid
            HTTPException: 403 if user lacks permission (e.g., editor trying to approve)
        """
        # Get version with scoping
        version = await self._get_version(system_id, version_id, current_user.org_id)

        # Check if transition is valid
        if not is_valid_transition(version.status, request.status):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Invalid status transition from {version.status.value} to {request.status.value}",
            )

        # Check role requirements for approval
        if request.status == VersionStatus.APPROVED:
            if current_user.role != UserRole.ADMIN:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only administrators can approve versions",
                )

        # Store old status for audit log
        old_status = version.status

        # Update status
        version.status = request.status

        # Set approval metadata if transitioning to approved
        if request.status == VersionStatus.APPROVED:
            version.approved_by = current_user.id
            version.approved_at = date.today()

        await self.db.flush()

        # Log audit event
        await self.audit_service.log(
            org_id=current_user.org_id,
            user_id=current_user.id,
            action=AuditAction.VERSION_STATUS_CHANGE,
            entity_type="system_version",
            entity_id=version.id,
            diff_json={
                "from_status": old_status.value,
                "to_status": request.status.value,
                "comment": request.comment,
            },
        )

        # Re-query with eager loading to ensure relationships are loaded
        query = (
            select(SystemVersion)
            .where(SystemVersion.id == version.id)
            .options(selectinload(SystemVersion.creator))
        )
        result = await self.db.execute(query)
        return result.scalar_one()

    async def get_by_id(
        self,
        system_id: UUID,
        version_id: UUID,
        org_id: UUID,
    ) -> SystemVersion:
        """Get a single version by ID with full details.

        Args:
            system_id: AI System ID
            version_id: Version ID
            org_id: Organization ID for scoping

        Returns:
            SystemVersion instance

        Raises:
            HTTPException: 404 if version not found or doesn't belong to system
        """
        return await self._get_version(system_id, version_id, org_id)

    async def update(
        self,
        system_id: UUID,
        version_id: UUID,
        request: UpdateVersionRequest,
        current_user: User,
    ) -> SystemVersion:
        """Update a system version.

        Args:
            system_id: AI System ID
            version_id: Version ID
            request: Update request with notes and/or release_date
            current_user: User requesting the update

        Returns:
            Updated SystemVersion instance

        Raises:
            HTTPException: 404 if version not found
        """
        # Get version with scoping
        version = await self._get_version(system_id, version_id, current_user.org_id)

        # Track changes for audit log
        changes = {}

        # Update notes if provided
        if request.notes is not None:
            if version.notes != request.notes:
                changes["notes"] = {
                    "from": version.notes,
                    "to": request.notes,
                }
                version.notes = request.notes

        # Update release_date if provided
        if request.release_date is not None:
            if version.release_date != request.release_date:
                changes["release_date"] = {
                    "from": version.release_date.isoformat() if version.release_date else None,
                    "to": request.release_date.isoformat(),
                }
                version.release_date = request.release_date

        # Only flush and log if there are actual changes
        if changes:
            await self.db.flush()

            # Log audit event
            await self.audit_service.log(
                org_id=current_user.org_id,
                user_id=current_user.id,
                action=AuditAction.VERSION_UPDATE,
                entity_type="system_version",
                entity_id=version.id,
                diff_json=changes,
            )

        # Re-query with eager loading to ensure relationships are loaded
        query = (
            select(SystemVersion)
            .where(SystemVersion.id == version.id)
            .options(selectinload(SystemVersion.creator))
        )
        result = await self.db.execute(query)
        return result.scalar_one()

    async def clone(
        self,
        system_id: UUID,
        version_id: UUID,
        request: CloneVersionRequest,
        current_user: User,
    ) -> SystemVersion:
        """Clone an existing version with a new label.

        Args:
            system_id: AI System ID
            version_id: Source version ID to clone
            request: Clone request with new label
            current_user: User creating the clone

        Returns:
            Newly created SystemVersion instance

        Raises:
            HTTPException: 404 if source version not found
            HTTPException: 422 if label is invalid
            HTTPException: 409 if label already exists
        """
        # Get source version with scoping
        source_version = await self._get_version(system_id, version_id, current_user.org_id)

        # Validate new label format
        self._validate_label(request.label)

        # Check for duplicate label
        await self._check_duplicate_label(system_id, request.label)

        # Create cloned version
        cloned_version = SystemVersion(
            ai_system_id=system_id,
            label=request.label,
            status=VersionStatus.DRAFT,  # Always start as draft
            notes=source_version.notes,  # Copy notes
            created_by=current_user.id,
            # Do NOT copy: snapshot_hash, approved_by, approved_at, release_date
        )

        self.db.add(cloned_version)

        try:
            await self.db.flush()
        except IntegrityError:
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Version with label '{request.label}' already exists for this AI system",
            )

        # Log audit event
        await self.audit_service.log(
            org_id=current_user.org_id,
            user_id=current_user.id,
            action=AuditAction.VERSION_CREATE,
            entity_type="system_version",
            entity_id=cloned_version.id,
            diff_json={
                "ai_system_id": str(system_id),
                "label": request.label,
                "status": VersionStatus.DRAFT.value,
                "cloned_from": str(version_id),
            },
        )

        # Re-query with eager loading to ensure relationships are loaded
        query = (
            select(SystemVersion)
            .where(SystemVersion.id == cloned_version.id)
            .options(selectinload(SystemVersion.creator))
        )
        result = await self.db.execute(query)
        return result.scalar_one()

    def _is_mutable(self, version: SystemVersion) -> bool:
        """Check if a version is mutable (can be modified/deleted).

        A version is immutable if:
        - Status is APPROVED AND
        - Has exports (when exports table exists in Module E)

        For Phase 8, since exports table doesn't exist yet,
        all versions are mutable (placeholder implementation).

        Args:
            version: SystemVersion instance to check

        Returns:
            True if version can be modified/deleted, False if immutable
        """
        # TODO: When exports table exists (Module E), add check:
        # if version.status == VersionStatus.APPROVED and version.has_exports:
        #     return False
        # return True

        # For now: all versions are mutable (exports not implemented)
        return True

    async def delete(
        self,
        system_id: UUID,
        version_id: UUID,
        current_user: User,
    ) -> None:
        """Delete a system version.

        Args:
            system_id: AI System ID
            version_id: Version ID to delete
            current_user: User requesting deletion

        Raises:
            HTTPException: 404 if version not found
            HTTPException: 409 if version is immutable (approved with exports)
        """
        # Get version with scoping
        version = await self._get_version(system_id, version_id, current_user.org_id)

        # Check if version is mutable
        if not self._is_mutable(version):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot delete immutable version (approved with exports)",
            )

        # Store data for audit log before deletion
        version_label = version.label
        version_status = version.status

        # Delete the version
        await self.db.delete(version)
        await self.db.flush()

        # Log audit event
        await self.audit_service.log(
            org_id=current_user.org_id,
            user_id=current_user.id,
            action=AuditAction.VERSION_DELETE,
            entity_type="system_version",
            entity_id=version_id,
            diff_json={
                "ai_system_id": str(system_id),
                "label": version_label,
                "status": version_status.value,
            },
        )
