"""API routes for LLM Assist (Module G)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import require_role
from src.core.database import get_db
from src.models.ai_system import AISystem
from src.models.enums import AnnexSectionKey, UserRole
from src.models.llm_interaction import LlmInteraction
from src.models.system_version import SystemVersion
from src.models.user import User
from src.schemas.llm import (
    DraftRequest,
    DraftResponse,
    GapRequest,
    GapSuggestionResponse,
    LlmHistoryListResponse,
    LlmInteractionResponse,
    LlmStatusResponse,
    LlmUsageDay,
    LlmUsageResponse,
    LlmUsageTotals,
)
from src.services.draft_service import DraftService
from src.services.gap_service import GapService
from src.services.llm_service import LlmService

router = APIRouter()


@router.get(
    "/llm/status",
    response_model=LlmStatusResponse,
    summary="Get LLM status (admin only)",
    description="Reports whether LLM features are enabled and configured. Never returns secrets.",
)
async def get_llm_status(
    current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> LlmStatusResponse:
    service = LlmService()
    settings = service.settings
    return LlmStatusResponse(
        llm_enabled=settings.llm_enabled,
        llm_available=service.llm_available(),
        provider=settings.llm_provider,
        model=settings.llm_model,
        provider_configured=bool(settings.anthropic_api_key),
    )


@router.get(
    "/llm/usage",
    response_model=LlmUsageResponse,
    summary="Get LLM usage (admin only)",
    description="Aggregated usage for the current organization. Never includes prompts, outputs, or secrets.",
)
async def get_llm_usage(
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> LlmUsageResponse:
    cutoff = datetime.now(UTC) - timedelta(days=days)

    def _totals_row_to_model(row) -> LlmUsageTotals:
        interactions, input_tokens, output_tokens, avg_duration_ms = row
        input_tokens = int(input_tokens or 0)
        output_tokens = int(output_tokens or 0)
        avg_duration = float(avg_duration_ms) if avg_duration_ms is not None else None
        return LlmUsageTotals(
            interactions=int(interactions or 0),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            avg_duration_ms=avg_duration,
        )

    base_filters = [AISystem.org_id == current_user.org_id]

    totals_query = (
        select(
            func.count(LlmInteraction.id),
            func.coalesce(func.sum(LlmInteraction.input_tokens), 0),
            func.coalesce(func.sum(LlmInteraction.output_tokens), 0),
            func.avg(LlmInteraction.duration_ms),
        )
        .select_from(LlmInteraction)
        .join(SystemVersion, LlmInteraction.version_id == SystemVersion.id)
        .join(AISystem, SystemVersion.ai_system_id == AISystem.id)
        .where(*base_filters)
    )
    totals_row = (await db.execute(totals_query)).one()

    period_totals_query = totals_query.where(LlmInteraction.created_at >= cutoff)
    period_totals_row = (await db.execute(period_totals_query)).one()

    day_bucket = func.date_trunc("day", LlmInteraction.created_at).label("day")
    by_day_query = (
        select(
            day_bucket,
            func.count(LlmInteraction.id).label("interactions"),
            func.coalesce(func.sum(LlmInteraction.input_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(LlmInteraction.output_tokens), 0).label("output_tokens"),
        )
        .select_from(LlmInteraction)
        .join(SystemVersion, LlmInteraction.version_id == SystemVersion.id)
        .join(AISystem, SystemVersion.ai_system_id == AISystem.id)
        .where(*base_filters)
        .where(LlmInteraction.created_at >= cutoff)
        .group_by(day_bucket)
        .order_by(day_bucket.asc())
    )
    by_day_rows = (await db.execute(by_day_query)).all()
    by_day = []
    for row in by_day_rows:
        input_tokens = int(getattr(row, "input_tokens", 0) or 0)
        output_tokens = int(getattr(row, "output_tokens", 0) or 0)
        by_day.append(
            LlmUsageDay(
                day=row.day,
                interactions=int(getattr(row, "interactions", 0) or 0),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
            )
        )

    return LlmUsageResponse(
        all_time=_totals_row_to_model(totals_row),
        period_days=days,
        period=_totals_row_to_model(period_totals_row),
        by_day=by_day,
    )


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
