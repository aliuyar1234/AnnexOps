"""AI System service for CRUD operations."""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.ai_system import AISystem
from src.models.enums import AuditAction, HRUseCaseType
from src.models.user import User
from src.schemas.ai_system import CreateSystemRequest, UpdateSystemRequest
from src.services.audit_service import AuditService


class AISystemService:
    """Service for managing AI systems."""

    def __init__(self, db: AsyncSession):
        """Initialize AI system service.

        Args:
            db: Database session
        """
        self.db = db
        self.audit_service = AuditService(db)

    async def create(
        self,
        request: CreateSystemRequest,
        current_user: User,
    ) -> AISystem:
        """Create a new AI system.

        Args:
            request: System creation request
            current_user: User creating the system

        Returns:
            Created AISystem instance

        Raises:
            HTTPException: 409 if system name already exists in org
        """
        system = AISystem(
            org_id=current_user.org_id,
            name=request.name,
            description=request.description,
            hr_use_case_type=request.hr_use_case_type,
            intended_purpose=request.intended_purpose,
            deployment_type=request.deployment_type,
            decision_influence=request.decision_influence,
            owner_user_id=current_user.id,
            contact_name=request.contact_name,
            contact_email=request.contact_email,
        )

        self.db.add(system)

        try:
            await self.db.flush()
        except IntegrityError:
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"System with name '{request.name}' already exists in this organization",
            ) from None

        # Log audit event
        await self.audit_service.log(
            org_id=current_user.org_id,
            user_id=current_user.id,
            action=AuditAction.AI_SYSTEM_CREATE,
            entity_type="ai_system",
            entity_id=system.id,
        )

        # Reload with relationships
        await self.db.refresh(system)
        return system

    async def list(
        self,
        org_id: UUID,
        use_case_type: HRUseCaseType | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AISystem], int]:
        """List AI systems for an organization.

        Args:
            org_id: Organization ID to filter by
            use_case_type: Optional HR use case type filter
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            Tuple of (systems list, total count)
        """
        # Base query
        query = (
            select(AISystem)
            .where(AISystem.org_id == org_id)
            .options(selectinload(AISystem.owner))
            .order_by(AISystem.created_at.desc())
        )

        # Count query
        count_query = select(func.count()).select_from(AISystem).where(AISystem.org_id == org_id)

        # Apply filter
        if use_case_type:
            query = query.where(AISystem.hr_use_case_type == use_case_type)
            count_query = count_query.where(AISystem.hr_use_case_type == use_case_type)

        # Apply pagination
        query = query.limit(limit).offset(offset)

        # Execute queries
        result = await self.db.execute(query)
        systems = list(result.scalars().all())

        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        return systems, total

    async def get_by_id(
        self,
        system_id: UUID,
        org_id: UUID,
    ) -> AISystem | None:
        """Get an AI system by ID.

        Args:
            system_id: System ID to fetch
            org_id: Organization ID for scoping

        Returns:
            AISystem if found, None otherwise
        """
        query = (
            select(AISystem)
            .where(AISystem.id == system_id)
            .where(AISystem.org_id == org_id)
            .options(
                selectinload(AISystem.owner),
                selectinload(AISystem.assessments),
                selectinload(AISystem.attachments),
            )
        )

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def update(
        self,
        system_id: UUID,
        request: UpdateSystemRequest,
        current_user: User,
    ) -> AISystem:
        """Update an AI system.

        Args:
            system_id: System ID to update
            request: Update request with new values
            current_user: User performing the update

        Returns:
            Updated AISystem instance

        Raises:
            HTTPException: 404 if system not found
            HTTPException: 409 if version conflict or duplicate name
        """
        system = await self.get_by_id(system_id, current_user.org_id)
        if not system:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="System not found",
            )

        # Check optimistic locking
        if request.expected_version is not None:
            if system.version != request.expected_version:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"System was modified by another user. Expected version {request.expected_version}, current version {system.version}",
                )

        # Track changes for audit
        changes = {}

        # Apply updates
        if request.name is not None and request.name != system.name:
            changes["name"] = {"old": system.name, "new": request.name}
            system.name = request.name

        if request.description is not None and request.description != system.description:
            changes["description"] = {"old": system.description, "new": request.description}
            system.description = request.description

        if (
            request.hr_use_case_type is not None
            and request.hr_use_case_type != system.hr_use_case_type
        ):
            changes["hr_use_case_type"] = {
                "old": system.hr_use_case_type.value,
                "new": request.hr_use_case_type.value,
            }
            system.hr_use_case_type = request.hr_use_case_type

        if (
            request.intended_purpose is not None
            and request.intended_purpose != system.intended_purpose
        ):
            changes["intended_purpose"] = {
                "old": system.intended_purpose,
                "new": request.intended_purpose,
            }
            system.intended_purpose = request.intended_purpose

        if (
            request.deployment_type is not None
            and request.deployment_type != system.deployment_type
        ):
            changes["deployment_type"] = {
                "old": system.deployment_type.value,
                "new": request.deployment_type.value,
            }
            system.deployment_type = request.deployment_type

        if (
            request.decision_influence is not None
            and request.decision_influence != system.decision_influence
        ):
            changes["decision_influence"] = {
                "old": system.decision_influence.value,
                "new": request.decision_influence.value,
            }
            system.decision_influence = request.decision_influence

        if request.contact_name is not None and request.contact_name != system.contact_name:
            changes["contact_name"] = {"old": system.contact_name, "new": request.contact_name}
            system.contact_name = request.contact_name

        if request.contact_email is not None and request.contact_email != system.contact_email:
            changes["contact_email"] = {"old": system.contact_email, "new": request.contact_email}
            system.contact_email = request.contact_email

        # Increment version
        system.version += 1

        try:
            await self.db.flush()
        except IntegrityError:
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"System with name '{request.name}' already exists in this organization",
            ) from None

        # Log audit event
        if changes:
            await self.audit_service.log(
                org_id=current_user.org_id,
                user_id=current_user.id,
                action=AuditAction.AI_SYSTEM_UPDATE,
                entity_type="ai_system",
                entity_id=system.id,
                diff_json=changes,
            )

        await self.db.refresh(system)
        return system

    async def delete(
        self,
        system_id: UUID,
        current_user: User,
        confirm_with_versions: bool = False,
    ) -> None:
        """Delete an AI system.

        Args:
            system_id: System ID to delete
            current_user: User performing the deletion
            confirm_with_versions: Confirm deletion even if versions exist

        Raises:
            HTTPException: 404 if system not found
            HTTPException: 409 if system has exports or unconfirmed versions
        """
        system = await self.get_by_id(system_id, current_user.org_id)
        if not system:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="System not found",
            )

        # Check if system has versions (Module C) - placeholder check
        # In Module C, we would check if system_versions exist
        # For now, we skip this check

        # Log audit event before deletion
        await self.audit_service.log(
            org_id=current_user.org_id,
            user_id=current_user.id,
            action=AuditAction.AI_SYSTEM_DELETE,
            entity_type="ai_system",
            entity_id=system.id,
            diff_json={"name": system.name},
        )

        await self.db.delete(system)
        await self.db.flush()
