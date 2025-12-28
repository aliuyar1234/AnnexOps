"""Draft generation service with strict mode (Module G)."""

from __future__ import annotations

import re
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.prompts import NEEDS_EVIDENCE_PLACEHOLDER, SYSTEM_PROMPT
from src.models.ai_system import AISystem
from src.models.evidence_item import EvidenceItem
from src.models.llm_interaction import LlmInteraction
from src.models.system_version import SystemVersion
from src.models.user import User
from src.schemas.llm import DraftResponse
from src.services.llm_service import LlmService
from src.services.section_service import SectionService

MAX_EVIDENCE_TOKENS_PER_ITEM = 500
MAX_EVIDENCE_TOKENS_TOTAL = 4000
MAX_PROMPT_TOKENS = 8000
MAX_OUTPUT_TOKENS = 1024

_CITATION_RE = re.compile(r"\[Evidence:\s*([0-9a-fA-F-]{36})\]")


def truncate_evidence_texts(
    *,
    llm: LlmService,
    evidence_texts: list[str],
    max_tokens_per_item: int,
    max_total_tokens: int,
) -> list[str]:
    """Truncate evidence texts to per-item and total token budgets.

    Returns a list of the same length as evidence_texts; items beyond the
    remaining budget are truncated to empty strings.
    """
    per_item_truncated = [
        llm.truncate_to_tokens(text, max_tokens_per_item) for text in evidence_texts
    ]

    remaining = max_total_tokens
    result: list[str] = []
    for text in per_item_truncated:
        if remaining <= 0:
            result.append("")
            continue

        truncated = llm.truncate_to_tokens(text, remaining)
        remaining -= llm.count_tokens(truncated)
        result.append(truncated)

    return result


def _extract_cited_evidence_ids(text: str) -> list[UUID]:
    cited: list[UUID] = []
    seen: set[UUID] = set()

    for raw in _CITATION_RE.findall(text or ""):
        try:
            evidence_id = UUID(raw)
        except ValueError:
            continue
        if evidence_id in seen:
            continue
        seen.add(evidence_id)
        cited.append(evidence_id)

    return cited


def _evidence_to_prompt_text(evidence: EvidenceItem) -> str:
    metadata = evidence.type_metadata or {}
    content = ""

    if evidence.type.value == "note":
        content = str(metadata.get("content", ""))
    elif evidence.type.value == "url":
        content = f"URL: {metadata.get('url', '')}".strip()
    elif evidence.type.value == "git":
        content = (
            f"Repo: {metadata.get('repo_url', '')}\n"
            f"File: {metadata.get('file_path', '')}\n"
            f"Commit: {metadata.get('commit_hash', '')}"
        ).strip()
    elif evidence.type.value == "ticket":
        content = (
            f"Ticket: {metadata.get('ticket_id', '')}\n"
            f"URL: {metadata.get('ticket_url', '')}"
        ).strip()
    elif evidence.type.value == "upload":
        content = (
            f"File: {metadata.get('original_filename', '')}\n"
            f"MIME: {metadata.get('mime_type', '')}"
        ).strip()

    return (
        f"Evidence ID: {evidence.id}\n"
        f"Title: {evidence.title}\n"
        f"Type: {evidence.type.value}\n"
        f"Classification: {evidence.classification.value}\n"
        f"Content:\n{content}"
    ).strip()


class DraftService:
    """Service for generating evidence-based drafts with strict mode enforcement."""

    def __init__(self, db: AsyncSession, llm_service: LlmService | None = None):
        self.db = db
        self.llm_service = llm_service or LlmService()

    async def generate_draft(
        self,
        *,
        section_key: str,
        version_id: UUID,
        selected_evidence_ids: list[UUID],
        instructions: str | None,
        current_user: User,
    ) -> DraftResponse:
        """Generate a draft for a section based on user-selected evidence."""
        # STRICT MODE FIRST: no evidence = no LLM call (Module G critical guardrail)
        if not selected_evidence_ids:
            section_service = SectionService(self.db)
            section = await section_service.get_by_key(
                version_id=version_id,
                section_key=section_key,
                org_id=current_user.org_id,
            )
            if not section:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Section not found",
                )

            interaction = LlmInteraction(
                version_id=version_id,
                section_key=section_key,
                user_id=current_user.id,
                selected_evidence_ids=[],
                prompt=f"[STRICT MODE] No evidence selected for section {section_key}",
                response=NEEDS_EVIDENCE_PLACEHOLDER,
                cited_evidence_ids=[],
                model=self.llm_service.settings.llm_model,
                input_tokens=0,
                output_tokens=0,
                strict_mode=True,
                duration_ms=0,
            )
            self.db.add(interaction)
            await self.db.flush()

            return DraftResponse(
                draft_text=NEEDS_EVIDENCE_PLACEHOLDER,
                cited_evidence_ids=[],
                warnings=["strict_mode_activated"],
                strict_mode=True,
                model_info=None,
                interaction_id=interaction.id,
            )

        # Validate version access and section existence
        section_service = SectionService(self.db)
        section = await section_service.get_by_key(
            version_id=version_id,
            section_key=section_key,
            org_id=current_user.org_id,
        )
        if not section:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Section not found",
            )

        # Offline mode / unavailable provider: graceful degradation
        if not self.llm_service.llm_available():
            interaction = LlmInteraction(
                version_id=version_id,
                section_key=section_key,
                user_id=current_user.id,
                selected_evidence_ids=selected_evidence_ids,
                prompt="[OFFLINE MODE] LLM unavailable; draft not generated",
                response="[LLM UNAVAILABLE: LLM features are disabled. Please edit this section manually.]",
                cited_evidence_ids=[],
                model=self.llm_service.settings.llm_model,
                input_tokens=0,
                output_tokens=0,
                strict_mode=False,
                duration_ms=0,
            )
            self.db.add(interaction)
            await self.db.flush()

            return DraftResponse(
                draft_text="[LLM UNAVAILABLE: LLM features are disabled. Please edit this section manually.]",
                cited_evidence_ids=[],
                warnings=["llm_unavailable"],
                strict_mode=False,
                model_info=None,
                interaction_id=interaction.id,
            )

        evidence_result = await self.db.execute(
            select(EvidenceItem).where(
                EvidenceItem.org_id == current_user.org_id,
                EvidenceItem.id.in_(selected_evidence_ids),
            )
        )
        evidence_items = list(evidence_result.scalars().all())
        evidence_by_id = {e.id: e for e in evidence_items}

        missing = [eid for eid in selected_evidence_ids if eid not in evidence_by_id]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or more evidence items not found",
            )

        ordered_evidence = [evidence_by_id[eid] for eid in selected_evidence_ids]
        evidence_blocks = [_evidence_to_prompt_text(e) for e in ordered_evidence]
        evidence_blocks = truncate_evidence_texts(
            llm=self.llm_service,
            evidence_texts=evidence_blocks,
            max_tokens_per_item=MAX_EVIDENCE_TOKENS_PER_ITEM,
            max_total_tokens=MAX_EVIDENCE_TOKENS_TOTAL,
        )

        user_prompt_parts = [
            f"Section: {section_key}",
            "Evidence items (use ONLY these; cite as [Evidence: <ID>]):",
        ]
        user_prompt_parts.extend(f"\n---\n{block}" for block in evidence_blocks if block)

        if instructions:
            user_prompt_parts.append(f"\nUser instructions: {instructions}")

        user_prompt_parts.append(
            "\nOutput markdown text with inline citations, and end with a list of cited evidence IDs."
        )
        user_prompt = "\n".join(user_prompt_parts).strip()

        full_prompt = SYSTEM_PROMPT + "\n\n" + user_prompt
        if self.llm_service.count_tokens(full_prompt) > MAX_PROMPT_TOKENS:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="Request too large for LLM context window",
            )

        completion = await self.llm_service.generate(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            max_output_tokens=MAX_OUTPUT_TOKENS,
        )

        cited_ids = _extract_cited_evidence_ids(completion.text)
        selected_set = set(selected_evidence_ids)
        cited_filtered = [eid for eid in cited_ids if eid in selected_set]

        interaction = LlmInteraction(
            version_id=version_id,
            section_key=section_key,
            user_id=current_user.id,
            selected_evidence_ids=selected_evidence_ids,
            prompt=full_prompt,
            response=completion.text,
            cited_evidence_ids=cited_filtered,
            model=completion.model,
            input_tokens=completion.input_tokens,
            output_tokens=completion.output_tokens,
            strict_mode=False,
            duration_ms=completion.duration_ms,
        )
        self.db.add(interaction)
        await self.db.flush()

        return DraftResponse(
            draft_text=completion.text,
            cited_evidence_ids=cited_filtered,
            warnings=[],
            strict_mode=False,
            model_info=completion.model,
            interaction_id=interaction.id,
        )

    async def list_interactions(
        self,
        *,
        version_id: UUID,
        current_user: User,
    ) -> list[LlmInteraction]:
        """List LLM interactions for a version (org-scoped)."""
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

        result = await self.db.execute(
            select(LlmInteraction)
            .where(LlmInteraction.version_id == version_id)
            .order_by(LlmInteraction.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_interaction_by_id(
        self,
        *,
        interaction_id: UUID,
        current_user: User,
    ) -> LlmInteraction | None:
        """Get a single interaction by ID (org-scoped)."""
        result = await self.db.execute(
            select(LlmInteraction)
            .join(LlmInteraction.system_version)
            .join(SystemVersion.ai_system)
            .where(LlmInteraction.id == interaction_id)
            .where(AISystem.org_id == current_user.org_id)
        )
        return result.scalar_one_or_none()
