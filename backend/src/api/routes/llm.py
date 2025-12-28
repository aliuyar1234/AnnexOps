"""API routes for LLM Assist (Module G)."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import require_role
from src.core.database import get_db
from src.models.ai_system import AISystem
from src.models.enums import AnnexSectionKey, UserRole
from src.models.system_version import SystemVersion
from src.models.user import User
from src.schemas.llm import (
    DraftRequest,
    DraftResponse,
    GapRequest,
    GapSuggestionResponse,
    LlmHistoryListResponse,
    LlmInteractionResponse,
)
from src.services.draft_service import DraftService
from src.services.gap_service import GapService

router = APIRouter()


@router.post(
    "/llm/sections/{section_key}/draft",
    response_model=DraftResponse,
    summary="Generate a section draft from evidence",
    description="Generate an Annex IV section draft using user-selected evidence only. Requires Editor role or higher.",
)
async def generate_section_draft(
    section_key: str,
    request: DraftRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.EDITOR)),
) -> DraftResponse:
    """Generate a draft for an Annex IV section."""
    valid_keys = {k.value for k in AnnexSectionKey}
    if section_key not in valid_keys:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Section not found",
        )

    service = DraftService(db=db)
    response = await service.generate_draft(
        section_key=section_key,
        version_id=request.version_id,
        selected_evidence_ids=request.selected_evidence_ids,
        instructions=request.instructions,
        current_user=current_user,
    )
    await db.commit()
    return response


@router.post(
    "/llm/sections/{section_key}/gaps",
    response_model=GapSuggestionResponse,
    summary="Suggest evidence gaps for a section",
    description="Suggest what artifacts to provide for missing section fields. Requires Editor role or higher.",
)
async def suggest_section_gaps(
    section_key: str,
    request: GapRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.EDITOR)),
) -> GapSuggestionResponse:
    valid_keys = {k.value for k in AnnexSectionKey}
    if section_key not in valid_keys:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Section not found",
        )

    service = GapService(db=db)
    response = await service.suggest_gaps(
        section_key=section_key,
        version_id=request.version_id,
        current_user=current_user,
    )
    await db.commit()
    return response


def _interaction_to_response(interaction) -> LlmInteractionResponse:
    return LlmInteractionResponse(
        id=interaction.id,
        version_id=interaction.version_id,
        section_key=interaction.section_key,
        user_id=interaction.user_id,
        selected_evidence_ids=interaction.selected_evidence_ids or [],
        cited_evidence_ids=interaction.cited_evidence_ids or [],
        prompt=interaction.prompt,
        response=interaction.response,
        model=interaction.model,
        input_tokens=interaction.input_tokens,
        output_tokens=interaction.output_tokens,
        strict_mode=interaction.strict_mode,
        duration_ms=interaction.duration_ms,
        created_at=interaction.created_at,
    )


@router.get(
    "/systems/{system_id}/versions/{version_id}/llm-history",
    response_model=LlmHistoryListResponse,
    summary="List LLM interaction history for a version",
    description="Compliance/audit endpoint for reviewing prompts and outputs. Requires Reviewer role or higher.",
)
async def list_llm_history(
    system_id: UUID,
    version_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.REVIEWER)),
) -> LlmHistoryListResponse:
    version_result = await db.execute(
        select(SystemVersion)
        .join(SystemVersion.ai_system)
        .where(SystemVersion.id == version_id)
        .where(SystemVersion.ai_system_id == system_id)
        .where(AISystem.org_id == current_user.org_id)
    )
    version = version_result.scalar_one_or_none()
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Version not found",
        )

    service = DraftService(db=db)
    interactions = await service.list_interactions(version_id=version_id, current_user=current_user)
    return LlmHistoryListResponse(
        items=[_interaction_to_response(i) for i in interactions],
        total=len(interactions),
    )
