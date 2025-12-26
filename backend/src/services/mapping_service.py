"""Mapping service for managing evidence mappings."""
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError

from src.models.evidence_mapping import EvidenceMapping
from src.models.evidence_item import EvidenceItem
from src.models.system_version import SystemVersion
from src.models.enums import AuditAction, MappingTargetType, MappingStrength
from src.models.user import User
from src.schemas.mapping import CreateMappingRequest
from src.services.audit_service import AuditService


class MappingService:
    """Service for managing evidence mappings."""

    def __init__(self, db: AsyncSession):
        """Initialize mapping service.

        Args:
            db: Database session
        """
        self.db = db
        self.audit_service = AuditService(db)

    async def create(
        self,
        version_id: UUID,
        request: CreateMappingRequest,
        current_user: User,
    ) -> EvidenceMapping:
        """Create an evidence mapping.

        Args:
            version_id: System version ID
            request: Mapping creation request
            current_user: User creating the mapping

        Returns:
            Created EvidenceMapping

        Raises:
            HTTPException: If validation fails or mapping already exists
        """
        # Verify version exists and belongs to user's organization
        version_query = (
            select(SystemVersion)
            .join(SystemVersion.ai_system)
            .where(SystemVersion.id == version_id)
            .where(SystemVersion.ai_system.has(org_id=current_user.org_id))
        )
        version_result = await self.db.execute(version_query)
        version = version_result.scalar_one_or_none()

        if not version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Version not found",
            )

        # Verify evidence exists and belongs to same organization
        evidence_query = (
            select(EvidenceItem)
            .where(EvidenceItem.id == request.evidence_id)
            .where(EvidenceItem.org_id == current_user.org_id)
        )
        evidence_result = await self.db.execute(evidence_query)
        evidence = evidence_result.scalar_one_or_none()

        if not evidence:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Evidence not found",
            )

        # Create mapping
        mapping = EvidenceMapping(
            evidence_id=request.evidence_id,
            version_id=version_id,
            target_type=request.target_type,
            target_key=request.target_key,
            strength=request.strength,
            notes=request.notes,
            created_by=current_user.id,
        )

        self.db.add(mapping)

        try:
            await self.db.flush()
        except IntegrityError as e:
            # Check if unique constraint violation
            if "uq_evidence_version_target" in str(e):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Evidence already mapped to {request.target_type.value}:{request.target_key}",
                )
            raise

        # Log audit event
        await self.audit_service.log(
            org_id=current_user.org_id,
            user_id=current_user.id,
            action=AuditAction.MAPPING_CREATE,
            entity_type="evidence_mapping",
            entity_id=mapping.id,
            diff_json={
                "evidence_id": str(request.evidence_id),
                "version_id": str(version_id),
                "target_type": request.target_type.value,
                "target_key": request.target_key,
            },
        )

        await self.db.refresh(mapping)
        return mapping

    async def list(
        self,
        version_id: UUID,
        org_id: UUID,
        target_type: MappingTargetType | None = None,
        target_key: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EvidenceMapping]:
        """List evidence mappings for a version.

        Args:
            version_id: System version ID
            org_id: Organization ID (for access control)
            target_type: Optional filter by target type
            target_key: Optional filter by target key (exact match or prefix)
            limit: Maximum number of items to return
            offset: Number of items to skip

        Returns:
            List of evidence mappings with nested evidence items

        Raises:
            HTTPException: If version not found
        """
        # Verify version exists and belongs to organization
        version_query = (
            select(SystemVersion)
            .join(SystemVersion.ai_system)
            .where(SystemVersion.id == version_id)
            .where(SystemVersion.ai_system.has(org_id=org_id))
        )
        version_result = await self.db.execute(version_query)
        version = version_result.scalar_one_or_none()

        if not version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Version not found",
            )

        # Build query with filters
        query = (
            select(EvidenceMapping)
            .where(EvidenceMapping.version_id == version_id)
            .options(
                selectinload(EvidenceMapping.evidence_item).selectinload(EvidenceItem.creator)
            )
            .order_by(EvidenceMapping.created_at.desc())
        )

        if target_type:
            query = query.where(EvidenceMapping.target_type == target_type)

        if target_key:
            # Support both exact match and prefix search
            if target_key.endswith("*"):
                # Prefix search
                prefix = target_key[:-1]
                query = query.where(EvidenceMapping.target_key.startswith(prefix))
            else:
                # Exact match
                query = query.where(EvidenceMapping.target_key == target_key)

        query = query.limit(limit).offset(offset)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_id(
        self,
        mapping_id: UUID,
        version_id: UUID,
        org_id: UUID,
    ) -> EvidenceMapping | None:
        """Get mapping by ID.

        Args:
            mapping_id: Mapping ID
            version_id: Version ID (for access control)
            org_id: Organization ID (for access control)

        Returns:
            EvidenceMapping if found, None otherwise
        """
        query = (
            select(EvidenceMapping)
            .join(EvidenceMapping.system_version)
            .join(SystemVersion.ai_system)
            .where(EvidenceMapping.id == mapping_id)
            .where(EvidenceMapping.version_id == version_id)
            .where(SystemVersion.ai_system.has(org_id=org_id))
            .options(
                selectinload(EvidenceMapping.evidence_item).selectinload(EvidenceItem.creator)
            )
        )

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def delete(
        self,
        mapping_id: UUID,
        version_id: UUID,
        current_user: User,
    ) -> None:
        """Delete an evidence mapping.

        Args:
            mapping_id: Mapping ID
            version_id: Version ID (for access control)
            current_user: User performing the deletion

        Raises:
            HTTPException: If mapping not found
        """
        mapping = await self.get_by_id(mapping_id, version_id, current_user.org_id)
        if not mapping:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mapping not found",
            )

        # Log audit event before deletion
        await self.audit_service.log(
            org_id=current_user.org_id,
            user_id=current_user.id,
            action=AuditAction.MAPPING_DELETE,
            entity_type="evidence_mapping",
            entity_id=mapping.id,
            diff_json={
                "evidence_id": str(mapping.evidence_id),
                "version_id": str(mapping.version_id),
                "target_type": mapping.target_type.value,
                "target_key": mapping.target_key,
            },
        )

        # Delete from database
        await self.db.delete(mapping)
        await self.db.flush()
