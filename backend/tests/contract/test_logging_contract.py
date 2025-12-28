"""Contract tests for Logging Collector (Module F) endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import create_access_token
from src.models.ai_system import AISystem
from src.models.organization import Organization
from src.models.system_version import SystemVersion
from src.models.user import User


@pytest.mark.asyncio
async def test_enable_logging_returns_201_with_api_key(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_ai_system: AISystem,
    test_version: SystemVersion,
    test_editor_user: User,
):
    """POST /systems/{id}/versions/{vid}/logging/enable returns key shown once."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}/logging/enable",
        json={"name": "Production Pipeline"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert "key_id" in data
    assert data["api_key"].startswith("ak_")
    assert data["endpoint"].endswith("/api/v1/logs")


@pytest.mark.asyncio
async def test_revoke_api_key_returns_204(
    client: AsyncClient,
    db: AsyncSession,
    test_ai_system: AISystem,
    test_version: SystemVersion,
    test_editor_user: User,
    test_admin_user: User,
):
    """DELETE /logging/keys/{key_id} returns 204."""
    editor_token = create_access_token({"sub": str(test_editor_user.id)})

    enable_response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}/logging/enable",
        json={"name": "Production Pipeline"},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert enable_response.status_code == 201
    key_id = enable_response.json()["key_id"]

    admin_token = create_access_token({"sub": str(test_admin_user.id)})
    revoke_response = await client.delete(
        f"/api/logging/keys/{key_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert revoke_response.status_code == 204


@pytest.mark.asyncio
async def test_ingest_log_returns_201(
    client: AsyncClient,
    db: AsyncSession,
    test_ai_system: AISystem,
    test_version: SystemVersion,
    test_editor_user: User,
    sample_decision_event: dict,
):
    """POST /v1/logs returns 201 for valid event + api key."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    enable_response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}/logging/enable",
        json={"name": "Ingest Key"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert enable_response.status_code == 201
    api_key = enable_response.json()["api_key"]

    ingest_response = await client.post(
        "/api/v1/logs",
        json=sample_decision_event,
        headers={"X-API-Key": api_key},
    )
    assert ingest_response.status_code == 201
    data = ingest_response.json()
    assert "id" in data


@pytest.mark.asyncio
async def test_list_logs_returns_200(
    client: AsyncClient,
    db: AsyncSession,
    test_ai_system: AISystem,
    test_version: SystemVersion,
    test_editor_user: User,
    test_viewer_user: User,
    sample_decision_event: dict,
):
    """GET /systems/{id}/versions/{vid}/logs returns 200 for viewer role."""
    editor_token = create_access_token({"sub": str(test_editor_user.id)})

    enable_response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}/logging/enable",
        json={"name": "Ingest Key"},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    api_key = enable_response.json()["api_key"]

    ingest_response = await client.post(
        "/api/v1/logs",
        json=sample_decision_event,
        headers={"X-API-Key": api_key},
    )
    assert ingest_response.status_code == 201

    viewer_token = create_access_token({"sub": str(test_viewer_user.id)})
    response = await client.get(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}/logs",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_export_logs_returns_200(
    client: AsyncClient,
    db: AsyncSession,
    test_ai_system: AISystem,
    test_version: SystemVersion,
    test_editor_user: User,
    test_viewer_user: User,
    sample_decision_event: dict,
):
    """GET /systems/{id}/versions/{vid}/logs/export returns file content."""
    editor_token = create_access_token({"sub": str(test_editor_user.id)})
    enable_response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}/logging/enable",
        json={"name": "Ingest Key"},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    api_key = enable_response.json()["api_key"]

    ingest_response = await client.post(
        "/api/v1/logs",
        json=sample_decision_event,
        headers={"X-API-Key": api_key},
    )
    assert ingest_response.status_code == 201

    viewer_token = create_access_token({"sub": str(test_viewer_user.id)})
    response = await client.get(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}/logs/export?format=json",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert response.status_code == 200
