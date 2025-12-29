"""API routes for system attachments."""

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import require_role
from src.core.database import get_db
from src.models.enums import UserRole
from src.models.user import User
from src.schemas.ai_system import UserSummary
from src.schemas.attachment import AttachmentResponse
from src.services.attachment_service import AttachmentService

router = APIRouter()


def _attachment_to_response(attachment) -> AttachmentResponse:
    """Convert SystemAttachment model to response."""
    return AttachmentResponse(
        id=attachment.id,
        title=attachment.title,
        description=attachment.description,
        file_size=attachment.file_size,
        mime_type=attachment.mime_type,
        uploaded_by=UserSummary(
            id=attachment.uploader.id,
            email=attachment.uploader.email,
        )
        if attachment.uploader
        else None,
        created_at=attachment.created_at,
    )


@router.post(
    "/{system_id}/attachments",
    response_model=AttachmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload attachment",
)
async def upload_attachment(
    system_id: UUID,
    file: UploadFile = File(...),
    title: str = Form(..., min_length=1, max_length=255),
    description: str | None = Form(None, max_length=5000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.EDITOR)),
) -> AttachmentResponse:
    """Upload a file attachment to a system.

    Requires Editor or Admin role.
    Maximum file size: 50MB.
    """
    service = AttachmentService(db)
    attachment = await service.upload(
        system_id,
        file,
        title,
        description,
        current_user,
    )
    await db.commit()
    return _attachment_to_response(attachment)


@router.get(
    "/{system_id}/attachments",
    response_model=list[AttachmentResponse],
    summary="List attachments",
)
async def list_attachments(
    system_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.VIEWER)),
) -> list[AttachmentResponse]:
    """List all attachments for a system."""
    service = AttachmentService(db)
    attachments = await service.list(system_id, current_user.org_id)
    return [_attachment_to_response(a) for a in attachments]


@router.get(
    "/{system_id}/attachments/{attachment_id}/download",
    summary="Download attachment",
)
async def download_attachment(
    system_id: UUID,
    attachment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.VIEWER)),
) -> RedirectResponse:
    """Get download URL for an attachment.

    Redirects to a presigned URL for the file.
    """
    service = AttachmentService(db)
    download_url = await service.get_download_url(
        system_id,
        attachment_id,
        current_user.org_id,
    )
    return RedirectResponse(url=download_url, status_code=status.HTTP_302_FOUND)


@router.delete(
    "/{system_id}/attachments/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete attachment",
)
async def delete_attachment(
    system_id: UUID,
    attachment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.EDITOR)),
) -> None:
    """Delete an attachment.

    Requires Editor or Admin role.
    """
    service = AttachmentService(db)
    await service.delete(system_id, attachment_id, current_user)
    await db.commit()
