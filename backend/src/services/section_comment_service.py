"""Service for managing section review comments."""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.ai_system import AISystem
from src.models.section_comment import SectionComment
from src.models.system_version import SystemVersion
from src.models.user import User


class SectionCommentService:
    """Service for creating and listing section comments."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _ensure_version_access(self, version_id: UUID, org_id: UUID) -> None:
        query = (
            select(SystemVersion.id)
            .join(AISystem, SystemVersion.ai_system_id == AISystem.id)
            .where(SystemVersion.id == version_id)
            .where(AISystem.org_id == org_id)
        )
        version = await self.db.scalar(query)
        if not version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Version not found",
            )

    async def list(
        self,
        *,
        version_id: UUID,
        section_key: str,
        org_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[SectionComment], int]:
        """List comments for a given section within a version."""
        await self._ensure_version_access(version_id, org_id)

        count_query = (
            select(func.count())
            .select_from(SectionComment)
            .where(SectionComment.version_id == version_id)
            .where(SectionComment.section_key == section_key)
        )
        total = int((await self.db.scalar(count_query)) or 0)

        query = (
            select(SectionComment)
            .where(SectionComment.version_id == version_id)
            .where(SectionComment.section_key == section_key)
            .options(selectinload(SectionComment.author))
            .order_by(SectionComment.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def create(
        self,
        *,
        version_id: UUID,
        section_key: str,
        comment: str,
        current_user: User,
    ) -> SectionComment:
        """Create a new comment for a section."""
        await self._ensure_version_access(version_id, current_user.org_id)

        item = SectionComment(
            version_id=version_id,
            section_key=section_key,
            user_id=current_user.id,
            comment=comment,
        )
        self.db.add(item)
        await self.db.flush()
        await self.db.refresh(item)
        return item

