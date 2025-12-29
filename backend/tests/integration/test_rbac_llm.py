"""Integration tests for LLM RBAC (Module G)."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import create_access_token
from src.models.ai_system import AISystem
from src.models.organization import Organization
from src.models.system_version import SystemVersion
from src.models.user import User


@pytest.mark.asyncio
async def test_viewer_cannot_generate_drafts(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_viewer_user: User,
    test_ai_system: AISystem,
    test_version: SystemVersion,
):
    """Viewer role must be forbidden from draft generation."""
    token = create_access_token({"sub": str(test_viewer_user.id)})

    response = await client.post(
        "/api/llm/sections/ANNEX4.RISK_MANAGEMENT/draft",
        json={
            "version_id": str(test_version.id),
            "selected_evidence_ids": [],
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_non_admin_cannot_access_llm_admin_endpoints(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_viewer_user: User,
):
    editor_token = create_access_token({"sub": str(test_editor_user.id)})
    viewer_token = create_access_token({"sub": str(test_viewer_user.id)})

    for token in (editor_token, viewer_token):
        status_resp = await client.get(
            "/api/llm/status",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert status_resp.status_code == 403

        usage_resp = await client.get(
            "/api/llm/usage?days=30",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert usage_resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_access_llm_admin_endpoints(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_admin_user: User,
):
    token = create_access_token({"sub": str(test_admin_user.id)})

    status_resp = await client.get(
        "/api/llm/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert "llm_enabled" in status_data
    assert "provider" in status_data

    usage_resp = await client.get(
        "/api/llm/usage?days=30",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert usage_resp.status_code == 200
    usage_data = usage_resp.json()
    assert usage_data["period_days"] == 30
    assert "all_time" in usage_data
    assert "period" in usage_data
