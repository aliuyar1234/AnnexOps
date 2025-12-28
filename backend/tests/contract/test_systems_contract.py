"""Contract tests for /systems endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import create_access_token
from src.models.organization import Organization
from src.models.user import User


@pytest.mark.asyncio
async def test_create_system_returns_201_with_valid_data(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """POST /systems returns 201 with valid system data."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    response = await client.post(
        "/api/systems",
        json={
            "name": "CV Screening Assistant",
            "description": "AI-powered resume screening",
            "hr_use_case_type": "recruitment_screening",
            "intended_purpose": "Assist recruiters by pre-filtering applications",
            "deployment_type": "saas",
            "decision_influence": "assistive",
            "contact_name": "Jane Doe",
            "contact_email": "jane@example.com",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "CV Screening Assistant"
    assert data["hr_use_case_type"] == "recruitment_screening"
    assert data["deployment_type"] == "saas"
    assert data["decision_influence"] == "assistive"
    assert data["version"] == 1
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_system_returns_422_with_missing_required_fields(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """POST /systems returns 422 when required fields are missing."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    response = await client.post(
        "/api/systems",
        json={
            "name": "Incomplete System",
            # Missing: hr_use_case_type, intended_purpose, deployment_type, decision_influence
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_system_returns_401_without_auth(
    client: AsyncClient,
    db: AsyncSession,
):
    """POST /systems returns 401 without authentication."""
    response = await client.post(
        "/api/systems",
        json={
            "name": "Test System",
            "hr_use_case_type": "recruitment_screening",
            "intended_purpose": "Test purpose",
            "deployment_type": "saas",
            "decision_influence": "assistive",
        },
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_systems_returns_200(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_viewer_user: User,
):
    """GET /systems returns 200 with system list."""
    token = create_access_token({"sub": str(test_viewer_user.id)})

    response = await client.get(
        "/api/systems",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_list_systems_with_use_case_filter(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """GET /systems with use_case_type filter returns filtered results."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create a system first
    await client.post(
        "/api/systems",
        json={
            "name": "Screening System",
            "hr_use_case_type": "recruitment_screening",
            "intended_purpose": "Screen candidates",
            "deployment_type": "saas",
            "decision_influence": "assistive",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    # List with filter
    response = await client.get(
        "/api/systems?use_case_type=recruitment_screening",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["hr_use_case_type"] == "recruitment_screening"


@pytest.mark.asyncio
async def test_get_system_returns_200(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """GET /systems/{id} returns 200 with system details."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create a system first
    create_response = await client.post(
        "/api/systems",
        json={
            "name": "Test System",
            "hr_use_case_type": "recruitment_screening",
            "intended_purpose": "Test purpose",
            "deployment_type": "saas",
            "decision_influence": "assistive",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    system_id = create_response.json()["id"]

    # Get the system
    response = await client.get(
        f"/api/systems/{system_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == system_id
    assert data["name"] == "Test System"


@pytest.mark.asyncio
async def test_get_system_returns_404_for_nonexistent(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_viewer_user: User,
):
    """GET /systems/{id} returns 404 for non-existent system."""
    token = create_access_token({"sub": str(test_viewer_user.id)})

    response = await client.get(
        "/api/systems/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_system_returns_200(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """PATCH /systems/{id} returns 200 with updated system."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create a system first
    create_response = await client.post(
        "/api/systems",
        json={
            "name": "Original Name",
            "hr_use_case_type": "recruitment_screening",
            "intended_purpose": "Original purpose",
            "deployment_type": "saas",
            "decision_influence": "assistive",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    system_id = create_response.json()["id"]

    # Update the system
    response = await client.patch(
        f"/api/systems/{system_id}",
        json={
            "name": "Updated Name",
            "expected_version": 1,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Name"
    assert data["version"] == 2


@pytest.mark.asyncio
async def test_update_system_returns_409_on_version_conflict(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """PATCH /systems/{id} returns 409 on version conflict."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create a system first
    create_response = await client.post(
        "/api/systems",
        json={
            "name": "Test System",
            "hr_use_case_type": "recruitment_screening",
            "intended_purpose": "Test purpose",
            "deployment_type": "saas",
            "decision_influence": "assistive",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    system_id = create_response.json()["id"]

    # Update with wrong version
    response = await client.patch(
        f"/api/systems/{system_id}",
        json={
            "name": "Conflicting Update",
            "expected_version": 99,  # Wrong version
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 409
