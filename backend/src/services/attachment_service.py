"""Attachment service for file upload/download operations."""
import uuid
from uuid import UUID

from fastapi import HTTPException, status, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.ai_system import AISystem
from src.models.system_attachment import SystemAttachment
from src.models.enums import AuditAction
from src.models.user import User
from src.core.storage import get_storage_client
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
}


class AttachmentService:
    """Service for managing system attachments."""

    def __init__(self, db: AsyncSession):
        """Initialize attachment service.

        Args:
            db: Database session
        """
        self.db = db
        self.storage = get_storage_client()
        self.audit_service = AuditService(db)

    async def get_system(
        self,
        system_id: UUID,
        org_id: UUID,
    ) -> AISystem:
        """Get AI system by ID with org scoping.

        Args:
            system_id: System ID
            org_id: Organization ID

        Returns:
            AISystem if found

        Raises:
            HTTPException: 404 if not found
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
                detail="System not found",
            )
        return system

    def _get_extension(self, filename: str) -> str:
        """Extract extension from filename.

        Args:
            filename: Original filename

        Returns:
            File extension without dot
        """
        if "." in filename:
            return filename.rsplit(".", 1)[1].lower()
        return "bin"

    async def upload(
        self,
        system_id: UUID,
        file: UploadFile,
        title: str,
        description: str | None,
        current_user: User,
    ) -> SystemAttachment:
        """Upload a file attachment.

        Args:
            system_id: System ID
            file: Uploaded file
            title: Attachment title
            description: Optional description
            current_user: User uploading the file

        Returns:
            Created SystemAttachment

        Raises:
            HTTPException: 404 if system not found
            HTTPException: 413 if file too large
            HTTPException: 415 if unsupported media type
        """
        # Verify system exists
        system = await self.get_system(system_id, current_user.org_id)

        # Validate file size
        content = await file.read()
        file_size = len(content)
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)}MB",
            )

        # Validate MIME type
        content_type = file.content_type or "application/octet-stream"
        if content_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"File type '{content_type}' is not allowed",
            )

        # Reset file position
        await file.seek(0)

        # Generate file ID
        file_id = uuid.uuid4()
        extension = self._get_extension(file.filename or "file.bin")

        # Upload to storage
        storage_uri, checksum, _ = self.storage.upload_file(
            file.file,
            current_user.org_id,
            system_id,
            file_id,
            extension,
            content_type,
        )

        # Create database record
        attachment = SystemAttachment(
            ai_system_id=system_id,
            title=title,
            description=description,
            storage_uri=storage_uri,
            checksum_sha256=checksum,
            file_size=file_size,
            mime_type=content_type,
            uploaded_by=current_user.id,
        )

        self.db.add(attachment)
        await self.db.flush()

        # Log audit event
        await self.audit_service.log(
            org_id=current_user.org_id,
            user_id=current_user.id,
            action=AuditAction.ATTACHMENT_UPLOAD,
            entity_type="system_attachment",
            entity_id=attachment.id,
            diff_json={
                "system_id": str(system_id),
                "title": title,
                "file_size": file_size,
            },
        )

        await self.db.refresh(attachment)
        return attachment

    async def list(
        self,
        system_id: UUID,
        org_id: UUID,
    ) -> list[SystemAttachment]:
        """List attachments for a system.

        Args:
            system_id: System ID
            org_id: Organization ID

        Returns:
            List of attachments
        """
        # Verify system exists
        await self.get_system(system_id, org_id)

        query = (
            select(SystemAttachment)
            .where(SystemAttachment.ai_system_id == system_id)
            .options(selectinload(SystemAttachment.uploader))
            .order_by(SystemAttachment.created_at.desc())
        )

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_id(
        self,
        system_id: UUID,
        attachment_id: UUID,
        org_id: UUID,
    ) -> SystemAttachment | None:
        """Get attachment by ID.

        Args:
            system_id: System ID
            attachment_id: Attachment ID
            org_id: Organization ID

        Returns:
            SystemAttachment if found
        """
        # Verify system exists
        await self.get_system(system_id, org_id)

        query = (
            select(SystemAttachment)
            .where(SystemAttachment.id == attachment_id)
            .where(SystemAttachment.ai_system_id == system_id)
            .options(selectinload(SystemAttachment.uploader))
        )

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_download_url(
        self,
        system_id: UUID,
        attachment_id: UUID,
        org_id: UUID,
    ) -> str:
        """Get presigned download URL for attachment.

        Args:
            system_id: System ID
            attachment_id: Attachment ID
            org_id: Organization ID

        Returns:
            Presigned download URL

        Raises:
            HTTPException: 404 if attachment not found
        """
        attachment = await self.get_by_id(system_id, attachment_id, org_id)
        if not attachment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Attachment not found",
            )

        return self.storage.get_presigned_url(attachment.storage_uri)

    async def delete(
        self,
        system_id: UUID,
        attachment_id: UUID,
        current_user: User,
    ) -> None:
        """Delete an attachment.

        Args:
            system_id: System ID
            attachment_id: Attachment ID
            current_user: User performing deletion

        Raises:
            HTTPException: 404 if attachment not found
        """
        attachment = await self.get_by_id(system_id, attachment_id, current_user.org_id)
        if not attachment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Attachment not found",
            )

        # Log audit event before deletion
        await self.audit_service.log(
            org_id=current_user.org_id,
            user_id=current_user.id,
            action=AuditAction.ATTACHMENT_DELETE,
            entity_type="system_attachment",
            entity_id=attachment.id,
            diff_json={
                "system_id": str(system_id),
                "title": attachment.title,
            },
        )

        # Delete from storage
        self.storage.delete_file(attachment.storage_uri)

        # Delete from database
        await self.db.delete(attachment)
        await self.db.flush()
