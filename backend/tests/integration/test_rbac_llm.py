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
