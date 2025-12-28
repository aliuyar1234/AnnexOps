"""Service for managing Annex IV sections."""

from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.annex_section import AnnexSection
from src.models.enums import AnnexSectionKey, AuditAction, VersionStatus
from src.models.export import Export
from src.models.system_version import SystemVersion
from src.models.user import User
from src.services.audit_service import AuditService
from src.services.completeness_service import calculate_section_score


class SectionService:
    """Service for managing Annex IV sections."""

    def __init__(self, db: AsyncSession):
        """Initialize section service.

        Args:
            db: Database session
        """
        self.db = db
        self.audit_service = AuditService(db)

    async def list_sections(
        self,
        version_id: UUID,
        org_id: UUID,
    ) -> list[AnnexSection]:
        """List all sections for a version.

        Args:
            version_id: System version ID
            org_id: Organization ID (for access control)

        Returns:
            List of all 12 Annex IV sections

        Raises:
            HTTPException: If version not found or access denied
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

        # Get all sections for this version
        query = (
            select(AnnexSection)
            .where(AnnexSection.version_id == version_id)
            .options(selectinload(AnnexSection.editor))
            .order_by(AnnexSection.section_key)
        )

        result = await self.db.execute(query)
        sections = list(result.scalars().all())

        # If no sections exist, initialize them
        if not sections:
            sections = await self.initialize_sections(version_id)

        return sections

    async def get_by_key(
        self,
        version_id: UUID,
        section_key: str,
        org_id: UUID,
    ) -> AnnexSection | None:
        """Get a section by its key.

        Args:
            version_id: System version ID
            section_key: Section key (e.g., "ANNEX4.RISK_MANAGEMENT")
            org_id: Organization ID (for access control)

        Returns:
            AnnexSection if found, None otherwise

        Raises:
            HTTPException: If version not found or access denied
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

        # Get section
        query = (
            select(AnnexSection)
            .where(AnnexSection.version_id == version_id)
            .where(AnnexSection.section_key == section_key)
            .options(selectinload(AnnexSection.editor))
        )

        result = await self.db.execute(query)
        section = result.scalar_one_or_none()

        # If section doesn't exist, create it
        if not section:
            section = AnnexSection(
                version_id=version_id,
                section_key=section_key,
                content={},
                completeness_score=Decimal("0"),
                evidence_refs=[],
                llm_assisted=False,
            )
            self.db.add(section)
            await self.db.flush()
            await self.db.refresh(section)

        return section

    async def initialize_sections(self, version_id: UUID) -> list[AnnexSection]:
        """Initialize all 12 Annex IV sections for a new version.

        Args:
            version_id: System version ID

        Returns:
            List of created sections
        """
        sections = []

        for section_key in AnnexSectionKey:
            section = AnnexSection(
                version_id=version_id,
                section_key=section_key.value,
                content={},
                completeness_score=Decimal("0"),
                evidence_refs=[],
                llm_assisted=False,
            )
            self.db.add(section)
            sections.append(section)

        await self.db.flush()

        # Refresh to get IDs and relationships
        for section in sections:
            await self.db.refresh(section)

        return sections

    async def update_content(
        self,
        version_id: UUID,
        section_key: str,
        content: dict | None,
        evidence_refs: list[UUID] | None,
        current_user: User,
    ) -> AnnexSection:
        """Update section content and/or evidence references.

        Args:
            version_id: System version ID
            section_key: Section key (e.g., "ANNEX4.RISK_MANAGEMENT")
            content: New JSONB content (None to keep existing)
            evidence_refs: New evidence references (None to keep existing)
            current_user: User performing the update

        Returns:
            Updated AnnexSection

        Raises:
            HTTPException: If section or version not found
        """
        # Get section (will create if doesn't exist)
        section = await self.get_by_key(version_id, section_key, current_user.org_id)

        if not section:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Section not found",
            )

        # Check immutability: approved versions with exports cannot be edited
        version_query = select(SystemVersion).where(SystemVersion.id == version_id)
        version_result = await self.db.execute(version_query)
        version = version_result.scalar_one_or_none()

        if version and version.status == VersionStatus.APPROVED:
            # Check if version has any exports
            export_count_query = (
                select(func.count()).select_from(Export).where(Export.version_id == version_id)
            )
            export_result = await self.db.execute(export_count_query)
            export_count = export_result.scalar_one()

            if export_count > 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Cannot edit section: version is approved and has exports (immutable)",
                )

        # Track changes for audit
        changes = {}

        # Update content if provided
        if content is not None:
            old_content = section.content
            section.content = content
            changes["content"] = {"old": old_content, "new": content}

        # Update evidence refs if provided
        if evidence_refs is not None:
            old_refs = section.evidence_refs
            section.evidence_refs = evidence_refs
            changes["evidence_refs"] = {
                "old": [str(r) for r in old_refs],
                "new": [str(r) for r in evidence_refs],
            }

        # Update metadata
        section.last_edited_by = current_user.id

        # Recalculate completeness score
        section.completeness_score = Decimal(str(calculate_section_score(section)))

        await self.db.flush()

        # Log audit event
        await self.audit_service.log(
            org_id=current_user.org_id,
            user_id=current_user.id,
            action=AuditAction.SECTION_UPDATE,
            entity_type="annex_section",
            entity_id=section.id,
            diff_json={
                "section_key": section_key,
                "version_id": str(version_id),
                "changes": changes,
            },
        )

        await self.db.refresh(section)
        return section
