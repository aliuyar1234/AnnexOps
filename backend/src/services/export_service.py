"""Service layer for export operations."""

import csv
import io
import json
import zipfile
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.storage import get_storage_client
from src.models.ai_system import AISystem
from src.models.annex_section import AnnexSection
from src.models.enums import AuditAction
from src.models.evidence_mapping import EvidenceMapping
from src.models.export import Export
from src.models.system_version import SystemVersion
from src.models.user import User
from src.services.audit_service import AuditService
from src.services.completeness_service import get_completeness_report
from src.services.docx_generator import generate_annex_iv_document
from src.services.snapshot_service import SnapshotService
from src.services.storage_service import get_storage_service


class ExportService:
    """Service for export operations."""

    def __init__(self, db: AsyncSession):
        """Initialize export service.

        Args:
            db: Database session
        """
        self.db = db
        self.audit_service = AuditService(db)

    async def list_exports(
        self,
        version_id: UUID,
        org_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Export], int]:
        """List exports for a system version.

        Args:
            version_id: System version ID
            org_id: Organization ID (for authorization check)
            limit: Maximum items to return
            offset: Number of items to skip

        Returns:
            Tuple of (exports list, total count)

        Raises:
            HTTPException: 404 if version not found or doesn't belong to org
        """
        # Verify version exists and belongs to org
        version_query = (
            select(SystemVersion)
            .join(AISystem, SystemVersion.ai_system_id == AISystem.id)
            .where(
                SystemVersion.id == version_id,
                AISystem.org_id == org_id,
            )
        )
        result = await self.db.execute(version_query)
        version = result.scalar_one_or_none()

        if not version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Version not found",
            )

        # Get total count
        count_query = (
            select(func.count()).select_from(Export).where(Export.version_id == version_id)
        )
        count_result = await self.db.execute(count_query)
        total = count_result.scalar_one()

        # Get exports
        exports_query = (
            select(Export)
            .where(Export.version_id == version_id)
            .order_by(Export.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(exports_query)
        exports = result.scalars().all()

        return list(exports), total

    async def get_download_url(
        self,
        export_id: UUID,
        org_id: UUID,
    ) -> str:
        """Get presigned download URL for an export.

        Args:
            export_id: Export ID
            org_id: Organization ID (for authorization check)

        Returns:
            Presigned download URL (valid for 1 hour)

        Raises:
            HTTPException: 404 if export not found or doesn't belong to org
        """
        # Get export with version join for org check
        query = (
            select(Export)
            .join(SystemVersion, Export.version_id == SystemVersion.id)
            .join(AISystem, SystemVersion.ai_system_id == AISystem.id)
            .where(
                Export.id == export_id,
                AISystem.org_id == org_id,
            )
        )
        result = await self.db.execute(query)
        export = result.scalar_one_or_none()

        if not export:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Export not found",
            )

        # Generate presigned download URL
        storage_service = get_storage_service()
        download_url = storage_service.generate_download_url(
            export.storage_uri,
            expires_in=3600,
        )

        return download_url

    async def generate_export(
        self,
        version_id: UUID,
        org_id: UUID,
        user: User,
        include_diff: bool = False,
        compare_version_id: UUID | None = None,
    ) -> Export:
        """Generate an export package for a system version.

        Creates a ZIP file containing:
        - AnnexIV.docx: The main document
        - SystemManifest.json: Version metadata with snapshot hash
        - EvidenceIndex.json: All evidence items (sorted)
        - EvidenceIndex.csv: Evidence items in CSV format
        - CompletenessReport.json: Completeness scores and gaps
        - DiffReport.json: (optional) Changes from compare version

        Args:
            version_id: System version ID
            org_id: Organization ID
            user: User generating the export
            include_diff: Whether to include diff report
            compare_version_id: Version to compare against (if include_diff)

        Returns:
            Created Export record

        Raises:
            HTTPException: 404 if version not found
            HTTPException: 400 if include_diff but no compare_version_id
        """
        # Validate diff params
        if include_diff and not compare_version_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="compare_version_id required when include_diff is true",
            )

        # Get version with system
        version_query = (
            select(SystemVersion)
            .join(AISystem, SystemVersion.ai_system_id == AISystem.id)
            .options(selectinload(SystemVersion.ai_system))
            .where(
                SystemVersion.id == version_id,
                AISystem.org_id == org_id,
            )
        )
        result = await self.db.execute(version_query)
        version = result.scalar_one_or_none()

        if not version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Version not found",
            )

        ai_system = version.ai_system

        # Get all sections for this version
        sections_query = (
            select(AnnexSection)
            .where(AnnexSection.version_id == version_id)
            .order_by(AnnexSection.section_key)
        )
        sections_result = await self.db.execute(sections_query)
        sections = list(sections_result.scalars().all())

        # Get evidence items mapped to this version
        mappings_query = (
            select(EvidenceMapping)
            .options(selectinload(EvidenceMapping.evidence_item))
            .where(EvidenceMapping.version_id == version_id)
        )
        mappings_result = await self.db.execute(mappings_query)
        mappings = list(mappings_result.scalars().all())

        # Extract unique evidence items (sorted by ID for determinism)
        evidence_map = {}
        for mapping in mappings:
            if mapping.evidence_item:
                evidence_map[str(mapping.evidence_item.id)] = mapping.evidence_item
        evidence_items = sorted(evidence_map.values(), key=lambda e: str(e.id))

        # Get completeness report
        completeness = await get_completeness_report(self.db, version_id)

        # Generate snapshot hash
        snapshot_service = SnapshotService()
        manifest = snapshot_service.generate_manifest(version, ai_system)
        snapshot_hash = snapshot_service.compute_hash_from_manifest(manifest)

        # Prepare data for DOCX
        system_info = {
            "id": str(ai_system.id),
            "name": ai_system.name,
            "hr_use_case_type": ai_system.hr_use_case_type.value,
            "intended_purpose": ai_system.intended_purpose,
            "org_name": "",  # Could be populated if org relationship exists
        }
        version_info = {
            "id": str(version.id),
            "label": version.label,
            "status": version.status.value,
            "release_date": version.release_date.isoformat() if version.release_date else None,
        }
        sections_data = [
            {
                "section_key": s.section_key,
                "content": s.content or {},
                "evidence_refs": s.evidence_refs or [],
            }
            for s in sections
        ]
        evidence_data = [
            {
                "id": str(e.id),
                "title": e.title,
                "type": e.evidence_type,
            }
            for e in evidence_items
        ]

        # Generate DOCX
        docx_buffer = generate_annex_iv_document(
            system_info=system_info,
            version_info=version_info,
            sections=sections_data,
            evidence_items=evidence_data,
        )

        # Generate EvidenceIndex.json (sorted)
        evidence_index = [
            {
                "id": str(e.id),
                "title": e.title,
                "type": e.evidence_type,
                "description": e.description,
                "classification": e.classification,
                "tags": e.tags or [],
            }
            for e in evidence_items
        ]
        evidence_json = json.dumps(
            evidence_index, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        )

        # Generate EvidenceIndex.csv
        csv_buffer = io.StringIO()
        csv_writer = csv.DictWriter(
            csv_buffer,
            fieldnames=["id", "title", "type", "description", "classification", "tags"],
        )
        csv_writer.writeheader()
        for e in evidence_items:
            csv_writer.writerow(
                {
                    "id": str(e.id),
                    "title": e.title,
                    "type": e.evidence_type,
                    "description": e.description or "",
                    "classification": e.classification or "",
                    "tags": ",".join(e.tags or []),
                }
            )
        evidence_csv = csv_buffer.getvalue()

        # Generate CompletenessReport.json
        completeness_data = {
            "version_id": str(version_id),
            "overall_score": float(completeness.overall_score),
            "generated_at": datetime.now(UTC).isoformat() + "Z",
            "sections": [
                {
                    "section_key": s.section_key,
                    "title": s.title,
                    "score": float(s.score),
                    "evidence_count": s.evidence_count,
                    "field_completion": s.field_completion,
                    "gaps": s.gaps,
                }
                for s in completeness.sections
            ],
            "gaps": [
                {
                    "section_key": g.section_key,
                    "gap_type": g.gap_type,
                    "description": g.description,
                }
                for g in completeness.gaps
            ],
        }
        completeness_json = json.dumps(
            completeness_data, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        )

        # Generate SystemManifest.json
        manifest_json = snapshot_service.to_canonical_json(manifest)

        # Create ZIP package (sorted entries for determinism)
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # Add files in sorted order for determinism
            files_to_add = [
                ("AnnexIV.docx", docx_buffer.getvalue()),
                ("CompletenessReport.json", completeness_json.encode("utf-8")),
                ("EvidenceIndex.csv", evidence_csv.encode("utf-8")),
                ("EvidenceIndex.json", evidence_json.encode("utf-8")),
                ("SystemManifest.json", manifest_json.encode("utf-8")),
            ]

            # Add diff report if requested
            if include_diff and compare_version_id:
                diff_data = await self._generate_diff_report(version_id, compare_version_id, org_id)
                diff_json = json.dumps(
                    diff_data, sort_keys=True, separators=(",", ":"), ensure_ascii=True
                )
                files_to_add.append(("DiffReport.json", diff_json.encode("utf-8")))
                files_to_add.sort(key=lambda x: x[0])

            for filename, content in files_to_add:
                zf.writestr(filename, content)

        zip_buffer.seek(0)
        zip_content = zip_buffer.getvalue()
        file_size = len(zip_content)

        # Upload to MinIO
        storage_client = get_storage_client()
        export_id = uuid4()
        storage_uri = f"exports/{org_id}/{ai_system.id}/{version_id}/{export_id}.zip"

        storage_client._client.put_object(
            Bucket=storage_client._bucket,
            Key=storage_uri,
            Body=zip_content,
            ContentType="application/zip",
            Metadata={
                "snapshot-hash": snapshot_hash,
            },
        )

        # Create Export record
        export_record = Export(
            id=export_id,
            version_id=version_id,
            export_type="diff" if include_diff else "full",
            snapshot_hash=snapshot_hash,
            storage_uri=storage_uri,
            file_size=file_size,
            include_diff=include_diff,
            compare_version_id=compare_version_id,
            completeness_score=Decimal(str(completeness.overall_score)),
            created_by=user.id,
        )
        self.db.add(export_record)
        await self.db.flush()
        await self.db.refresh(export_record)

        # Audit logging
        await self.audit_service.log(
            org_id=org_id,
            user_id=user.id,
            action=AuditAction.EXPORT_CREATE,
            entity_type="export",
            entity_id=export_record.id,
            diff_json={
                "version_id": str(version_id),
                "export_type": export_record.export_type,
                "snapshot_hash": snapshot_hash,
                "file_size": file_size,
                "include_diff": include_diff,
                "compare_version_id": str(compare_version_id) if compare_version_id else None,
            },
        )

        return export_record

    async def _generate_diff_report(
        self,
        version_id: UUID,
        compare_version_id: UUID,
        org_id: UUID,
    ) -> dict:
        """Generate diff report between two versions.

        Args:
            version_id: Current version ID
            compare_version_id: Version to compare against
            org_id: Organization ID

        Returns:
            Dict with section and evidence changes
        """
        # Get both versions' sections
        current_sections = await self._get_sections_map(version_id)
        compare_sections = await self._get_sections_map(compare_version_id)

        # Get both versions' evidence mappings
        current_evidence = await self._get_evidence_ids(version_id)
        compare_evidence = await self._get_evidence_ids(compare_version_id)

        # Calculate changes
        section_changes = []
        all_keys = set(current_sections.keys()) | set(compare_sections.keys())

        for key in sorted(all_keys):
            current = current_sections.get(key, {})
            compare = compare_sections.get(key, {})

            if current != compare:
                section_changes.append(
                    {
                        "section_key": key,
                        "change_type": "modified"
                        if key in current_sections and key in compare_sections
                        else ("added" if key in current_sections else "removed"),
                        "current_content": current,
                        "previous_content": compare,
                    }
                )

        # Evidence changes
        added_evidence = list(current_evidence - compare_evidence)
        removed_evidence = list(compare_evidence - current_evidence)

        return {
            "version_id": str(version_id),
            "compare_version_id": str(compare_version_id),
            "generated_at": datetime.now(UTC).isoformat() + "Z",
            "section_changes": section_changes,
            "evidence_changes": {
                "added": sorted(added_evidence),
                "removed": sorted(removed_evidence),
            },
        }

    async def _get_sections_map(self, version_id: UUID) -> dict:
        """Get sections as a map keyed by section_key."""
        query = select(AnnexSection).where(AnnexSection.version_id == version_id)
        result = await self.db.execute(query)
        sections = result.scalars().all()
        return {s.section_key: s.content or {} for s in sections}

    async def _get_evidence_ids(self, version_id: UUID) -> set:
        """Get set of evidence IDs mapped to a version."""
        query = select(EvidenceMapping.evidence_id).where(EvidenceMapping.version_id == version_id)
        result = await self.db.execute(query)
        return {str(row[0]) for row in result.fetchall()}
