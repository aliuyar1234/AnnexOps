"""Evidence service for managing evidence items."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.enums import AuditAction, Classification, EvidenceType
from src.models.evidence_item import EvidenceItem
from src.models.evidence_mapping import EvidenceMapping
from src.models.user import User
from src.schemas.evidence import CreateEvidenceRequest
from src.services.audit_service import AuditService

# Maximum file size: 50MB
MAX_FILE_SIZE = 50 * 1024 * 1024

# Allowed MIME types
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # docx
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # xlsx
    "image/png",
    "image/jpeg",
    "text/plain",
    "text/markdown",
    "application/json",
}


class EvidenceService:
    """Service for managing evidence items."""

    def __init__(self, db: AsyncSession):
        """Initialize evidence service.

        Args:
            db: Database session
        """
        self.db = db
        self.audit_service = AuditService(db)

    def _validate_file_upload_metadata(self, type_metadata: dict) -> None:
        """Validate file upload metadata.

        Args:
            type_metadata: Upload metadata dict

        Raises:
            HTTPException: If validation fails
        """
        # Validate file size
        file_size = type_metadata.get("file_size", 0)
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024 * 1024)}MB",
            )

        # Validate MIME type
        mime_type = type_metadata.get("mime_type", "")
        if mime_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"File type '{mime_type}' is not allowed",
            )

    def _validate_upload_storage_uri(self, storage_uri: str, org_id: UUID) -> None:
        """Validate that a user-supplied storage URI is safe and org-scoped."""
        if not storage_uri or not isinstance(storage_uri, str):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="storage_uri is required",
            )
        if len(storage_uri) > 500:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="storage_uri is too long",
            )
        if storage_uri.startswith("/") or "\\" in storage_uri:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="storage_uri is invalid",
            )

        parts = storage_uri.split("/")
        if len(parts) != 5 or parts[0] != "evidence" or parts[1] != str(org_id):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="storage_uri is invalid for this organization",
            )

        year, month, filename = parts[2], parts[3], parts[4]
        if not (year.isdigit() and len(year) == 4):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="storage_uri has an invalid year segment",
            )
        if not month.isdigit():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="storage_uri has an invalid month segment",
            )
        month_int = int(month)
        if month_int < 1 or month_int > 12:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="storage_uri has an invalid month segment",
            )

        if "." not in filename:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="storage_uri has an invalid filename segment",
            )
        file_id, ext = filename.rsplit(".", 1)
        try:
            UUID(file_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="storage_uri has an invalid filename segment",
            ) from None
        if not ext.isalnum() or len(ext) > 16:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="storage_uri has an invalid file extension",
            )

    def _validate_url_metadata(self, type_metadata: dict) -> None:
        """Validate URL metadata.

        Args:
            type_metadata: URL metadata dict

        Raises:
            HTTPException: If validation fails
        """
        # URL validation is handled by Pydantic HttpUrl validator
        # This method is a placeholder for future business logic validation
        pass

    def _validate_git_metadata(self, type_metadata: dict) -> None:
        """Validate Git metadata.

        Args:
            type_metadata: Git metadata dict

        Raises:
            HTTPException: If validation fails
        """
        # Git metadata validation is handled by Pydantic validators
        # This method is a placeholder for future business logic validation
        pass

    def _validate_ticket_metadata(self, type_metadata: dict) -> None:
        """Validate Ticket metadata.

        Args:
            type_metadata: Ticket metadata dict

        Raises:
            HTTPException: If validation fails
        """
        # Ticket metadata validation is handled by Pydantic validators
        # This method is a placeholder for future business logic validation
        pass

    def _validate_note_metadata(self, type_metadata: dict) -> None:
        """Validate Note metadata.

        Args:
            type_metadata: Note metadata dict

        Raises:
            HTTPException: If validation fails
        """
        # Note metadata validation is handled by Pydantic validators
        # This method is a placeholder for future business logic validation
        pass

    async def create(
        self,
        request: CreateEvidenceRequest,
        current_user: User,
    ) -> tuple[EvidenceItem, UUID | None]:
        """Create an evidence item.

        Args:
            request: Evidence creation request
            current_user: User creating the evidence

        Returns:
            Tuple of (Created EvidenceItem, duplicate_of UUID or None)

        Raises:
            HTTPException: If validation fails
        """
        # Validate type-specific metadata
        if request.type == EvidenceType.UPLOAD:
            storage_uri = request.type_metadata.get("storage_uri")
            if storage_uri is not None:
                self._validate_upload_storage_uri(
                    str(storage_uri),
                    current_user.org_id,
                )
            self._validate_file_upload_metadata(request.type_metadata)
        elif request.type == EvidenceType.URL:
            self._validate_url_metadata(request.type_metadata)
        elif request.type == EvidenceType.GIT:
            self._validate_git_metadata(request.type_metadata)
        elif request.type == EvidenceType.TICKET:
            self._validate_ticket_metadata(request.type_metadata)
        elif request.type == EvidenceType.NOTE:
            self._validate_note_metadata(request.type_metadata)

        # Check for duplicate checksum (upload type only)
        duplicate_of = None
        if request.type == EvidenceType.UPLOAD:
            checksum = request.type_metadata.get("checksum_sha256")
            if checksum:
                # Look for existing evidence with same checksum in same org
                duplicate_query = (
                    select(EvidenceItem.id)
                    .where(EvidenceItem.org_id == current_user.org_id)
                    .where(EvidenceItem.type == EvidenceType.UPLOAD)
                    .where(EvidenceItem.type_metadata["checksum_sha256"].astext == checksum)
                    .limit(1)
                )
                duplicate_result = await self.db.execute(duplicate_query)
                duplicate_of = duplicate_result.scalar_one_or_none()

        # Create evidence item
        evidence = EvidenceItem(
            org_id=current_user.org_id,
            type=request.type,
            title=request.title,
            description=request.description,
            tags=request.tags,
            classification=request.classification,
            type_metadata=request.type_metadata,
            created_by=current_user.id,
        )

        self.db.add(evidence)
        await self.db.flush()

        # Log audit event
        await self.audit_service.log(
            org_id=current_user.org_id,
            user_id=current_user.id,
            action=AuditAction.EVIDENCE_CREATE,
            entity_type="evidence_item",
            entity_id=evidence.id,
            diff_json={
                "type": request.type.value,
                "title": request.title,
                "classification": request.classification.value,
                "duplicate_of": str(duplicate_of) if duplicate_of else None,
            },
        )

        await self.db.refresh(evidence)
        return evidence, duplicate_of

    async def get_by_id(
        self,
        evidence_id: UUID,
        org_id: UUID,
    ) -> EvidenceItem | None:
        """Get evidence item by ID.

        Args:
            evidence_id: Evidence ID
            org_id: Organization ID

        Returns:
            EvidenceItem if found, None otherwise
        """
        query = (
            select(EvidenceItem)
            .where(EvidenceItem.id == evidence_id)
            .where(EvidenceItem.org_id == org_id)
            .options(selectinload(EvidenceItem.creator))
        )

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_id_with_details(
        self,
        evidence_id: UUID,
        org_id: UUID,
    ) -> tuple[EvidenceItem | None, int, list]:
        """Get evidence item by ID with usage count and mapped versions.

        Args:
            evidence_id: Evidence ID
            org_id: Organization ID

        Returns:
            Tuple of (EvidenceItem, usage_count, mapped_versions_list)
            Returns (None, 0, []) if evidence not found
        """
        # Get the evidence item
        evidence = await self.get_by_id(evidence_id, org_id)
        if not evidence:
            return None, 0, []

        # Get usage count and mapped versions
        from src.models.ai_system import AISystem
        from src.models.system_version import SystemVersion

        # Query for mappings with version and system details
        mappings_query = (
            select(
                EvidenceMapping.version_id,
                SystemVersion.label,
                SystemVersion.ai_system_id,
                AISystem.name.label("system_name"),
            )
            .select_from(EvidenceMapping)
            .join(SystemVersion, EvidenceMapping.version_id == SystemVersion.id)
            .join(AISystem, SystemVersion.ai_system_id == AISystem.id)
            .where(EvidenceMapping.evidence_id == evidence_id)
            .distinct()
        )

        mappings_result = await self.db.execute(mappings_query)
        mappings_rows = mappings_result.all()

        # Build mapped versions list
        mapped_versions = []
        for row in mappings_rows:
            mapped_versions.append(
                {
                    "id": row.version_id,
                    "label": row.label,
                    "system_id": row.ai_system_id,
                    "system_name": row.system_name,
                }
            )

        # Count total mappings
        count_query = select(func.count(EvidenceMapping.id)).where(
            EvidenceMapping.evidence_id == evidence_id
        )
        count_result = await self.db.execute(count_query)
        usage_count = count_result.scalar() or 0

        return evidence, usage_count, mapped_versions

    async def list(
        self,
        org_id: UUID,
        evidence_type: EvidenceType | None = None,
        classification: Classification | None = None,
        tags: list[str] | None = None,
        search: str | None = None,
        orphaned: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[EvidenceItem], int]:
        """List evidence items for an organization with filtering and search.

        Args:
            org_id: Organization ID
            evidence_type: Optional filter by evidence type
            classification: Optional filter by classification level
            tags: Optional filter by tags (evidence must have ALL specified tags)
            search: Optional full-text search on title and description
            orphaned: Optional filter for orphaned evidence (True = no mappings, False = has mappings)
            limit: Maximum number of items to return (max 1000)
            offset: Number of items to skip

        Returns:
            Tuple of (list of evidence items, total count without pagination)
        """
        # Enforce max limit
        if limit > 1000:
            limit = 1000

        # Build base query
        query = (
            select(EvidenceItem)
            .where(EvidenceItem.org_id == org_id)
            .options(selectinload(EvidenceItem.creator))
        )

        # Apply type filter
        if evidence_type:
            query = query.where(EvidenceItem.type == evidence_type)

        # Apply classification filter
        if classification:
            query = query.where(EvidenceItem.classification == classification)

        # Apply tag filters (evidence must have ALL tags)
        if tags:
            for tag in tags:
                query = query.where(EvidenceItem.tags.contains([tag]))

        # Apply full-text search
        if search:
            # Create tsvector from title + description
            search_vector = func.to_tsvector(
                "english", EvidenceItem.title + " " + func.coalesce(EvidenceItem.description, "")
            )
            # Create tsquery from search term
            search_query = func.plainto_tsquery("english", search)
            # Apply search filter
            query = query.where(search_vector.op("@@")(search_query))

        # Apply orphaned filter
        if orphaned is not None:
            if orphaned:
                # Filter for evidence with NO mappings (orphaned)
                mapping_subquery = select(EvidenceMapping.evidence_id).where(
                    EvidenceMapping.evidence_id == EvidenceItem.id
                )
                query = query.where(~mapping_subquery.exists())
            else:
                # Filter for evidence with at least one mapping
                mapping_subquery = select(EvidenceMapping.evidence_id).where(
                    EvidenceMapping.evidence_id == EvidenceItem.id
                )
                query = query.where(mapping_subquery.exists())

        # Get total count before pagination
        count_query = select(func.count()).select_from(query.alias())
        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        # Apply ordering and pagination
        query = query.order_by(EvidenceItem.created_at.desc())
        query = query.limit(limit).offset(offset)

        # Execute query
        result = await self.db.execute(query)
        items = list(result.scalars().all())

        # Compute usage_count for each item
        if items:
            # Get all evidence IDs
            evidence_ids = [item.id for item in items]

            # Count mappings for each evidence item
            usage_query = (
                select(
                    EvidenceMapping.evidence_id, func.count(EvidenceMapping.id).label("usage_count")
                )
                .where(EvidenceMapping.evidence_id.in_(evidence_ids))
                .group_by(EvidenceMapping.evidence_id)
            )

            usage_result = await self.db.execute(usage_query)
            usage_map = {row.evidence_id: row.usage_count for row in usage_result}

            # Attach usage_count to each item
            for item in items:
                # Use getattr/setattr to add the attribute dynamically
                item.usage_count = usage_map.get(item.id, 0)

        return items, total

    async def update(
        self,
        evidence_id: UUID,
        updates: dict,
        current_user: User,
    ) -> EvidenceItem:
        """Update an evidence item.

        Args:
            evidence_id: Evidence ID
            updates: Fields to update (title, description, tags, classification, type_metadata)
            current_user: User performing the update

        Returns:
            Updated EvidenceItem

        Raises:
            HTTPException: If evidence not found or validation fails
        """
        evidence = await self.get_by_id(evidence_id, current_user.org_id)
        if not evidence:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Evidence not found",
            )

        # Validate type_metadata if provided
        if "type_metadata" in updates and updates["type_metadata"] is not None:
            from pydantic import ValidationError

            # Validate against the evidence's type
            try:
                if evidence.type == EvidenceType.UPLOAD:
                    from src.schemas.evidence import UploadMetadata

                    UploadMetadata(**updates["type_metadata"])
                    existing = evidence.type_metadata or {}
                    incoming = updates["type_metadata"]
                    if incoming.get("storage_uri") != existing.get("storage_uri"):
                        raise HTTPException(
                            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="storage_uri cannot be changed",
                        )
                    for key in ("checksum_sha256", "file_size", "mime_type"):
                        if incoming.get(key) != existing.get(key):
                            raise HTTPException(
                                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail=f"{key} cannot be changed",
                            )
                    self._validate_upload_storage_uri(
                        str(incoming.get("storage_uri", "")),
                        current_user.org_id,
                    )
                elif evidence.type == EvidenceType.URL:
                    from src.schemas.evidence import UrlMetadata

                    UrlMetadata(**updates["type_metadata"])
                elif evidence.type == EvidenceType.GIT:
                    from src.schemas.evidence import GitMetadata

                    GitMetadata(**updates["type_metadata"])
                elif evidence.type == EvidenceType.TICKET:
                    from src.schemas.evidence import TicketMetadata

                    TicketMetadata(**updates["type_metadata"])
                elif evidence.type == EvidenceType.NOTE:
                    from src.schemas.evidence import NoteMetadata

                    NoteMetadata(**updates["type_metadata"])
            except ValidationError as e:
                error_msgs = []
                for error in e.errors():
                    field = " -> ".join(str(loc) for loc in error["loc"])
                    msg = error["msg"]
                    error_msgs.append(f"{field}: {msg}")
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"type_metadata validation failed: {'; '.join(error_msgs)}",
                ) from None

        # Reject explicit nulls for non-nullable fields.
        for field in ("title", "tags", "classification", "type_metadata"):
            if field in updates and updates[field] is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"{field} cannot be null",
                )

        # Update fields
        for key, value in updates.items():
            if hasattr(evidence, key):
                setattr(evidence, key, value)

        await self.db.flush()

        # Log audit event
        await self.audit_service.log(
            org_id=current_user.org_id,
            user_id=current_user.id,
            action=AuditAction.EVIDENCE_UPDATE,
            entity_type="evidence_item",
            entity_id=evidence.id,
            diff_json=jsonable_encoder(updates),
        )

        await self.db.refresh(evidence)
        return evidence

    async def delete(
        self,
        evidence_id: UUID,
        current_user: User,
        force: bool = False,
    ) -> None:
        """Delete an evidence item.

        Args:
            evidence_id: Evidence ID
            current_user: User performing the deletion
            force: If True, delete all mappings first; if False, fail if mappings exist

        Raises:
            HTTPException: If evidence not found or has mappings without force=True
        """
        evidence = await self.get_by_id(evidence_id, current_user.org_id)
        if not evidence:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Evidence not found",
            )

        # Check for existing mappings
        mappings_count_query = select(func.count(EvidenceMapping.id)).where(
            EvidenceMapping.evidence_id == evidence_id
        )
        mappings_result = await self.db.execute(mappings_count_query)
        mappings_count = mappings_result.scalar() or 0

        if mappings_count > 0 and not force:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot delete evidence with {mappings_count} existing mapping(s). Use force=true to delete mappings and evidence.",
            )

        # If force=true and mappings exist, delete them first
        if force and mappings_count > 0:
            # Delete all mappings
            delete_mappings_query = select(EvidenceMapping).where(
                EvidenceMapping.evidence_id == evidence_id
            )
            mappings_result = await self.db.execute(delete_mappings_query)
            mappings_to_delete = mappings_result.scalars().all()

            for mapping in mappings_to_delete:
                await self.db.delete(mapping)

            # Log mapping deletions
            await self.audit_service.log(
                org_id=current_user.org_id,
                user_id=current_user.id,
                action=AuditAction.MAPPING_DELETE,
                entity_type="evidence_mapping",
                entity_id=evidence.id,
                diff_json={
                    "reason": "force_delete_evidence",
                    "mappings_deleted": mappings_count,
                },
            )

        # If upload type, delete file from storage
        if evidence.type == EvidenceType.UPLOAD:
            storage_uri = evidence.type_metadata.get("storage_uri")
            if storage_uri:
                from src.services.storage_service import get_storage_service

                storage_service = get_storage_service()
                try:
                    self._validate_upload_storage_uri(str(storage_uri), current_user.org_id)
                    storage_service.delete_file(str(storage_uri))
                except Exception:
                    # Log but don't fail the deletion if storage deletion fails
                    pass

        # Log audit event before deletion
        await self.audit_service.log(
            org_id=current_user.org_id,
            user_id=current_user.id,
            action=AuditAction.EVIDENCE_DELETE,
            entity_type="evidence_item",
            entity_id=evidence.id,
            diff_json={
                "type": evidence.type.value,
                "title": evidence.title,
                "force": force,
            },
        )

        # Delete from database
        await self.db.delete(evidence)
        await self.db.flush()
