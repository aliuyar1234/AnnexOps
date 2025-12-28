"""Contract tests for LLM assist endpoints (Module G)."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import create_access_token
from src.models.ai_system import AISystem
from src.models.evidence_item import EvidenceItem
from src.models.organization import Organization
from src.models.system_version import SystemVersion
from src.models.user import User
from src.services.llm_service import LlmCompletion


@pytest.mark.asyncio
async def test_post_llm_draft_returns_200(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
    test_version: SystemVersion,
    test_evidence_item: EvidenceItem,
):
    """POST /llm/sections/{key}/draft returns 200 and DraftResponse shape."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    completion = LlmCompletion(
        text=f"## Draft\n\nSome text [Evidence: {test_evidence_item.id}]",
        model="claude-3-sonnet-20240229",
        input_tokens=123,
        output_tokens=45,
        duration_ms=10,
    )

    with patch(
        "src.services.llm_service.LlmService.llm_available",
        return_value=True,
    ), patch(
        "src.services.llm_service.LlmService.generate",
        new_callable=AsyncMock,
        return_value=completion,
    ):
        response = await client.post(
            "/api/llm/sections/ANNEX4.RISK_MANAGEMENT/draft",
            json={
                "version_id": str(test_version.id),
                "selected_evidence_ids": [str(test_evidence_item.id)],
                "instructions": "Focus on risk identification methodology",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    data = response.json()

    assert "draft_text" in data
    assert "cited_evidence_ids" in data
    assert "warnings" in data
    assert "model_info" in data
    assert "interaction_id" in data
    assert "strict_mode" in data

    assert data["strict_mode"] is False
    assert str(test_evidence_item.id) in data["cited_evidence_ids"]


@pytest.mark.asyncio
async def test_post_llm_gaps_returns_200(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
    test_version: SystemVersion,
):
    """POST /llm/sections/{key}/gaps returns 200 and GapSuggestionResponse shape."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    response = await client.post(
        "/api/llm/sections/ANNEX4.DATA_GOVERNANCE/gaps",
        json={"version_id": str(test_version.id)},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "suggestions" in data
    assert "disclaimer" in data


@pytest.mark.asyncio
async def test_get_llm_history_returns_200(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
    test_version: SystemVersion,
    test_llm_interaction,
):
    """GET /systems/{id}/versions/{vid}/llm-history returns 200 and list shape."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    response = await client.get(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}/llm-history",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1
