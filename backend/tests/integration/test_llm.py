"""Integration tests for LLM assist endpoints (Module G)."""

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
async def test_draft_generation_with_citations(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
    test_version: SystemVersion,
    test_evidence_item: EvidenceItem,
):
    """Draft generation returns cited_evidence_ids for selected evidence."""
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
    assert data["strict_mode"] is False
    assert str(test_evidence_item.id) in data["cited_evidence_ids"]
    assert data["draft_text"]
    assert data["interaction_id"]


@pytest.mark.asyncio
async def test_strict_mode_no_evidence(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
    test_version: SystemVersion,
):
    """Strict mode triggers with empty evidence and never calls the LLM."""
    from src.core.prompts import NEEDS_EVIDENCE_PLACEHOLDER

    token = create_access_token({"sub": str(test_editor_user.id)})

    with patch(
        "src.services.llm_service.LlmService.generate",
        new_callable=AsyncMock,
        side_effect=AssertionError("LLM call should not happen"),
    ):
        response = await client.post(
            "/api/llm/sections/ANNEX4.RISK_MANAGEMENT/draft",
            json={
                "version_id": str(test_version.id),
                "selected_evidence_ids": [],
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["strict_mode"] is True
    assert data["draft_text"] == NEEDS_EVIDENCE_PLACEHOLDER
    assert data["warnings"] == ["strict_mode_activated"]
    assert data["model_info"] is None
    assert data["interaction_id"]


@pytest.mark.asyncio
async def test_strict_mode_output_has_no_claims(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
    test_version: SystemVersion,
):
    """Strict mode output must be placeholder-only (no system claims)."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    response = await client.post(
        "/api/llm/sections/ANNEX4.RISK_MANAGEMENT/draft",
        json={
            "version_id": str(test_version.id),
            "selected_evidence_ids": [],
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["strict_mode"] is True
    assert data["draft_text"].startswith("[NEEDS EVIDENCE:")


@pytest.mark.asyncio
async def test_gap_suggestions(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
    test_version: SystemVersion,
):
    """Gap suggestions return artifact guidance without system claims."""
    from src.core.prompts import GAP_SUGGESTIONS_DISCLAIMER

    token = create_access_token({"sub": str(test_editor_user.id)})

    response = await client.post(
        "/api/llm/sections/ANNEX4.DATA_GOVERNANCE/gaps",
        json={"version_id": str(test_version.id)},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["disclaimer"] == GAP_SUGGESTIONS_DISCLAIMER
    assert isinstance(data["suggestions"], list)


@pytest.mark.asyncio
async def test_llm_history_retrieval(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
    test_version: SystemVersion,
    test_evidence_item: EvidenceItem,
):
    """History returns previously logged interactions."""
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
        draft_response = await client.post(
            "/api/llm/sections/ANNEX4.RISK_MANAGEMENT/draft",
            json={
                "version_id": str(test_version.id),
                "selected_evidence_ids": [str(test_evidence_item.id)],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    assert draft_response.status_code == 200

    history = await client.get(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}/llm-history",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert history.status_code == 200
    data = history.json()
    assert data["total"] >= 1
    assert data["items"][0]["version_id"] == str(test_version.id)


@pytest.mark.asyncio
async def test_offline_mode(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
    test_version: SystemVersion,
    test_evidence_item: EvidenceItem,
):
    """Offline mode returns a graceful response and no provider call."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    with patch(
        "src.services.llm_service.LlmService.llm_available",
        return_value=False,
    ):
        response = await client.post(
            "/api/llm/sections/ANNEX4.RISK_MANAGEMENT/draft",
            json={
                "version_id": str(test_version.id),
                "selected_evidence_ids": [str(test_evidence_item.id)],
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["warnings"] == ["llm_unavailable"]
    assert data["model_info"] is None


@pytest.mark.asyncio
async def test_llm_api_error_handling(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
    test_version: SystemVersion,
    test_evidence_item: EvidenceItem,
):
    """Provider errors return a user-friendly response."""
    from fastapi import HTTPException

    token = create_access_token({"sub": str(test_editor_user.id)})

    with patch(
        "src.services.llm_service.LlmService.llm_available",
        return_value=True,
    ), patch(
        "src.services.llm_service.LlmService.generate",
        new_callable=AsyncMock,
        side_effect=HTTPException(status_code=502, detail="LLM provider error"),
    ):
        response = await client.post(
            "/api/llm/sections/ANNEX4.RISK_MANAGEMENT/draft",
            json={
                "version_id": str(test_version.id),
                "selected_evidence_ids": [str(test_evidence_item.id)],
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 502
    assert response.json()["detail"] == "LLM provider error"
