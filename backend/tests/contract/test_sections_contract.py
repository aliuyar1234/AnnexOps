"""Contract tests for Annex IV section endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import create_access_token
from src.models.ai_system import AISystem
from src.models.organization import Organization
from src.models.system_version import SystemVersion
from src.models.user import User


@pytest.mark.asyncio
async def test_list_sections_returns_200(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_viewer_user: User,
    test_ai_system: AISystem,
    test_version: SystemVersion,
):
    """GET /systems/{id}/versions/{vid}/sections returns 200 with all 12 sections."""
    token = create_access_token({"sub": str(test_viewer_user.id)})

    response = await client.get(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}/sections",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] == 12
    assert len(data["items"]) == 12

    # Verify structure of first section
    section = data["items"][0]
    assert "id" in section
    assert "version_id" in section
    assert "section_key" in section
    assert "title" in section
    assert "content" in section
    assert "completeness_score" in section
    assert "evidence_refs" in section
    assert "llm_assisted" in section
    assert "last_edited_by" in section
    assert "updated_at" in section


@pytest.mark.asyncio
async def test_list_sections_returns_401_without_auth(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_ai_system: AISystem,
    test_version: SystemVersion,
):
    """GET /systems/{id}/versions/{vid}/sections returns 401 without authentication."""
    response = await client.get(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}/sections",
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_sections_returns_404_for_nonexistent_version(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_viewer_user: User,
    test_ai_system: AISystem,
):
    """GET /systems/{id}/versions/{vid}/sections returns 404 for nonexistent version."""
    from uuid import uuid4

    token = create_access_token({"sub": str(test_viewer_user.id)})

    response = await client.get(
        f"/api/systems/{test_ai_system.id}/versions/{uuid4()}/sections",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_section_returns_200(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_viewer_user: User,
    test_ai_system: AISystem,
    test_version: SystemVersion,
):
    """GET /systems/{id}/versions/{vid}/sections/{key} returns 200 with section details."""
    token = create_access_token({"sub": str(test_viewer_user.id)})

    response = await client.get(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}/sections/ANNEX4.RISK_MANAGEMENT",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["section_key"] == "ANNEX4.RISK_MANAGEMENT"
    assert data["title"] == "Risk Management System"
    assert "id" in data
    assert "version_id" in data
    assert "content" in data
    assert "completeness_score" in data
    assert "evidence_refs" in data


@pytest.mark.asyncio
async def test_get_section_returns_404_for_nonexistent_version(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_viewer_user: User,
    test_ai_system: AISystem,
):
    """GET /systems/{id}/versions/{vid}/sections/{key} returns 404 for nonexistent version."""
    from uuid import uuid4

    token = create_access_token({"sub": str(test_viewer_user.id)})

    response = await client.get(
        f"/api/systems/{test_ai_system.id}/versions/{uuid4()}/sections/ANNEX4.RISK_MANAGEMENT",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_section_returns_200(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
    test_version: SystemVersion,
):
    """PATCH /systems/{id}/versions/{vid}/sections/{key} returns 200 with updated section."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    update_data = {
        "content": {
            "risk_management_system_description": "Our comprehensive risk management approach...",
            "identified_risks": ["Risk 1", "Risk 2"],
        }
    }

    response = await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}/sections/ANNEX4.RISK_MANAGEMENT",
        json=update_data,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["section_key"] == "ANNEX4.RISK_MANAGEMENT"
    assert data["content"] == update_data["content"]
    assert data["last_edited_by"] == str(test_editor_user.id)
    assert float(data["completeness_score"]) > 0


@pytest.mark.asyncio
async def test_update_section_with_evidence_refs_returns_200(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
    test_version: SystemVersion,
):
    """PATCH /systems/{id}/versions/{vid}/sections/{key} with evidence_refs returns 200."""
    from uuid import uuid4

    token = create_access_token({"sub": str(test_editor_user.id)})

    evidence_id_1 = uuid4()
    evidence_id_2 = uuid4()

    update_data = {
        "content": {
            "risk_management_system_description": "Updated content",
        },
        "evidence_refs": [str(evidence_id_1), str(evidence_id_2)],
    }

    response = await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}/sections/ANNEX4.RISK_MANAGEMENT",
        json=update_data,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["evidence_refs"]) == 2
    assert str(evidence_id_1) in data["evidence_refs"]
    assert str(evidence_id_2) in data["evidence_refs"]


@pytest.mark.asyncio
async def test_update_section_returns_403_for_viewer_role(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_viewer_user: User,
    test_ai_system: AISystem,
    test_version: SystemVersion,
):
    """PATCH /systems/{id}/versions/{vid}/sections/{key} returns 403 for VIEWER role."""
    token = create_access_token({"sub": str(test_viewer_user.id)})

    update_data = {
        "content": {
            "risk_management_system_description": "Unauthorized update",
        }
    }

    response = await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}/sections/ANNEX4.RISK_MANAGEMENT",
        json=update_data,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_update_section_returns_404_for_nonexistent_version(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """PATCH /systems/{id}/versions/{vid}/sections/{key} returns 404 for nonexistent version."""
    from uuid import uuid4

    token = create_access_token({"sub": str(test_editor_user.id)})

    update_data = {
        "content": {
            "risk_management_system_description": "Update",
        }
    }

    response = await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/{uuid4()}/sections/ANNEX4.RISK_MANAGEMENT",
        json=update_data,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
