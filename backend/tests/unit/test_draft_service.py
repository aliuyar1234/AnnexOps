"""Unit tests for draft service logic (Module G)."""

from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.evidence_item import EvidenceItem
from src.models.system_version import SystemVersion
from src.models.user import User
from src.services.llm_service import LlmService


@pytest.mark.asyncio
async def test_truncate_evidence_respects_limits():
    """Evidence truncation respects per-item and total token budgets."""
    from src.services.draft_service import truncate_evidence_texts

    llm = LlmService()
    long_text = ("word " * 2000).strip()
    evidence_texts = [long_text, long_text, long_text, long_text, long_text]

    truncated = truncate_evidence_texts(
        llm=llm,
        evidence_texts=evidence_texts,
        max_tokens_per_item=500,
        max_total_tokens=4000,
    )

    assert len(truncated) == len(evidence_texts)
    assert all(llm.count_tokens(t) <= 500 for t in truncated)
    assert sum(llm.count_tokens(t) for t in truncated) <= 4000


@pytest.mark.asyncio
async def test_no_llm_call_when_evidence_empty(
    db: AsyncSession,
    test_version: SystemVersion,
    test_editor_user: User,
    test_evidence_item: EvidenceItem,
):
    """Strict mode: empty evidence_ids must not call the LLM provider."""
    from src.services.draft_service import DraftService

    llm = LlmService()
    llm.generate = AsyncMock(side_effect=AssertionError("LLM call should not happen"))

    service = DraftService(db=db, llm_service=llm)
    response = await service.generate_draft(
        section_key="ANNEX4.RISK_MANAGEMENT",
        version_id=test_version.id,
        selected_evidence_ids=[],
        instructions=None,
        current_user=test_editor_user,
    )

    assert response.strict_mode is True
    assert response.cited_evidence_ids == []
