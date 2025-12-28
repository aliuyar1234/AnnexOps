"""Integration tests for Logging Collector (Module F)."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import create_access_token
from src.models.ai_system import AISystem
from src.models.system_version import SystemVersion
from src.models.user import User


@pytest.mark.asyncio
async def test_api_key_lifecycle_workflow(
    client: AsyncClient,
    db: AsyncSession,
    test_ai_system: AISystem,
    test_version: SystemVersion,
    test_editor_user: User,
    test_admin_user: User,
    sample_decision_event: dict,
):
    """Enable logging -> ingest -> revoke -> rejected."""
    editor_token = create_access_token({"sub": str(test_editor_user.id)})

    enable_response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}/logging/enable",
        json={"name": "Lifecycle Key"},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert enable_response.status_code == 201
    enable_data = enable_response.json()
    api_key = enable_data["api_key"]
    key_id = enable_data["key_id"]

    ingest_ok = await client.post(
        "/api/v1/logs",
        json=sample_decision_event,
        headers={"X-API-Key": api_key},
    )
    assert ingest_ok.status_code == 201

    admin_token = create_access_token({"sub": str(test_admin_user.id)})
    revoke = await client.delete(
        f"/api/logging/keys/{key_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert revoke.status_code == 204

    ingest_rejected = await client.post(
        "/api/v1/logs",
        json=sample_decision_event,
        headers={"X-API-Key": api_key},
    )
    assert ingest_rejected.status_code == 401


@pytest.mark.asyncio
async def test_valid_event_ingestion(
    client: AsyncClient,
    db: AsyncSession,
    test_ai_system: AISystem,
    test_version: SystemVersion,
    test_editor_user: User,
    sample_decision_event: dict,
):
    """Valid event is accepted and stored."""
    token = create_access_token({"sub": str(test_editor_user.id)})
    enable_response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}/logging/enable",
        json={"name": "Ingest Key"},
        headers={"Authorization": f"Bearer {token}"},
    )
    api_key = enable_response.json()["api_key"]

    response = await client.post(
        "/api/v1/logs",
        json=sample_decision_event,
        headers={"X-API-Key": api_key},
    )
    assert response.status_code == 201
    assert "id" in response.json()


@pytest.mark.asyncio
async def test_invalid_api_key_rejected(
    client: AsyncClient,
    db: AsyncSession,
    sample_decision_event: dict,
):
    """Invalid API key is rejected with 401."""
    response = await client.post(
        "/api/v1/logs",
        json=sample_decision_event,
        headers={"X-API-Key": "ak_invalid"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_schema_validation_errors_return_400(
    client: AsyncClient,
    db: AsyncSession,
    test_ai_system: AISystem,
    test_version: SystemVersion,
    test_editor_user: User,
):
    """Invalid event payload returns 400 with validation error details."""
    token = create_access_token({"sub": str(test_editor_user.id)})
    enable_response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}/logging/enable",
        json={"name": "Ingest Key"},
        headers={"Authorization": f"Bearer {token}"},
    )
    api_key = enable_response.json()["api_key"]

    # Missing required event_time
    response = await client.post(
        "/api/v1/logs",
        json={"event_id": "evt_1", "actor": "x", "subject": {"subject_type": "candidate", "subject_id_hash": "sha256:x"}, "model": {"model_id": "m", "model_version": "1"}, "input": {"input_hash": "sha256:i"}, "output": {"decision": "reject", "output_hash": "sha256:o"}},
        headers={"X-API-Key": api_key},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_time_range_filtering(
    client: AsyncClient,
    db: AsyncSession,
    test_ai_system: AISystem,
    test_version: SystemVersion,
    test_editor_user: User,
    test_viewer_user: User,
    sample_decision_event: dict,
):
    """List endpoint filters by start/end time."""
    token = create_access_token({"sub": str(test_editor_user.id)})
    enable_response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}/logging/enable",
        json={"name": "Ingest Key"},
        headers={"Authorization": f"Bearer {token}"},
    )
    api_key = enable_response.json()["api_key"]

    event1 = dict(sample_decision_event)
    event1["event_id"] = "evt_1"
    event1["event_time"] = "2025-12-01T00:00:00Z"

    event2 = dict(sample_decision_event)
    event2["event_id"] = "evt_2"
    event2["event_time"] = "2025-12-20T00:00:00Z"

    resp1 = await client.post("/api/v1/logs", json=event1, headers={"X-API-Key": api_key})
    assert resp1.status_code == 201
    resp2 = await client.post("/api/v1/logs", json=event2, headers={"X-API-Key": api_key})
    assert resp2.status_code == 201

    viewer_token = create_access_token({"sub": str(test_viewer_user.id)})
    response = await client.get(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}/logs?start_time=2025-12-10T00:00:00Z&end_time=2025-12-31T23:59:59Z",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["event_id"] == "evt_2"


@pytest.mark.asyncio
async def test_json_export(
    client: AsyncClient,
    db: AsyncSession,
    test_ai_system: AISystem,
    test_version: SystemVersion,
    test_editor_user: User,
    test_viewer_user: User,
    sample_decision_event: dict,
):
    """Export endpoint returns JSON file."""
    token = create_access_token({"sub": str(test_editor_user.id)})
    enable_response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}/logging/enable",
        json={"name": "Ingest Key"},
        headers={"Authorization": f"Bearer {token}"},
    )
    api_key = enable_response.json()["api_key"]

    ingest = await client.post("/api/v1/logs", json=sample_decision_event, headers={"X-API-Key": api_key})
    assert ingest.status_code == 201

    viewer_token = create_access_token({"sub": str(test_viewer_user.id)})
    export = await client.get(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}/logs/export?format=json",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert export.status_code == 200
    assert "application/json" in export.headers.get("content-type", "")
    assert "evt_123456" in export.text


@pytest.mark.asyncio
async def test_csv_export(
    client: AsyncClient,
    db: AsyncSession,
    test_ai_system: AISystem,
    test_version: SystemVersion,
    test_editor_user: User,
    test_viewer_user: User,
    sample_decision_event: dict,
):
    """Export endpoint returns CSV file."""
    token = create_access_token({"sub": str(test_editor_user.id)})
    enable_response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}/logging/enable",
        json={"name": "Ingest Key"},
        headers={"Authorization": f"Bearer {token}"},
    )
    api_key = enable_response.json()["api_key"]

    ingest = await client.post("/api/v1/logs", json=sample_decision_event, headers={"X-API-Key": api_key})
    assert ingest.status_code == 201

    viewer_token = create_access_token({"sub": str(test_viewer_user.id)})
    export = await client.get(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}/logs/export?format=csv",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert export.status_code == 200
    assert "text/csv" in export.headers.get("content-type", "")
    assert "event_id" in export.text


@pytest.mark.asyncio
async def test_expired_api_key_rejected(
    client: AsyncClient,
    db: AsyncSession,
    test_log_api_key: dict,
    sample_decision_event: dict,
):
    """Revoked/expired API key is rejected on ingest."""
    from src.models.log_api_key import LogApiKey

    key: LogApiKey = test_log_api_key["key"]
    key.revoked_at = datetime.now(UTC) - timedelta(days=1)
    await db.flush()

    response = await client.post(
        "/api/v1/logs",
        json=sample_decision_event,
        headers={"X-API-Key": test_log_api_key["api_key"]},
    )
    assert response.status_code == 401

