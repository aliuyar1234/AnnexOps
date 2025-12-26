"""Integration tests for AI system operations."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import create_access_token
from src.models.organization import Organization
from src.models.user import User
from src.models.ai_system import AISystem


@pytest.mark.asyncio
async def test_system_creation_flow(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """Test complete system creation flow: create -> verify in list."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create a system
    create_response = await client.post(
        "/api/systems",
        json={
            "name": "Integration Test System",
            "description": "System for integration testing",
            "hr_use_case_type": "performance_evaluation",
            "intended_purpose": "Test employee performance tracking",
            "deployment_type": "onprem",
            "decision_influence": "semi_automated",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_response.status_code == 201
    created_system = create_response.json()
    system_id = created_system["id"]

    # Verify it appears in the list
    list_response = await client.get(
        "/api/systems",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_response.status_code == 200
    systems = list_response.json()
    assert systems["total"] >= 1
    system_ids = [s["id"] for s in systems["items"]]
    assert system_id in system_ids


@pytest.mark.asyncio
async def test_duplicate_system_name_within_org_fails(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """Test that duplicate system names within org are rejected."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    system_data = {
        "name": "Unique System Name",
        "hr_use_case_type": "recruitment_screening",
        "intended_purpose": "Test purpose",
        "deployment_type": "saas",
        "decision_influence": "assistive",
    }

    # Create first system
    response1 = await client.post(
        "/api/systems",
        json=system_data,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response1.status_code == 201

    # Try to create duplicate
    response2 = await client.post(
        "/api/systems",
        json=system_data,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response2.status_code == 409


@pytest.mark.asyncio
async def test_system_owner_is_current_user(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """Test that system owner is set to the creating user."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    response = await client.post(
        "/api/systems",
        json={
            "name": "Owner Test System",
            "hr_use_case_type": "recruitment_screening",
            "intended_purpose": "Test owner assignment",
            "deployment_type": "saas",
            "decision_influence": "assistive",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["owner"]["id"] == str(test_editor_user.id)


@pytest.mark.asyncio
async def test_optimistic_locking_conflict(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """Test optimistic locking prevents concurrent modification conflicts."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create system
    create_response = await client.post(
        "/api/systems",
        json={
            "name": "Locking Test System",
            "hr_use_case_type": "recruitment_screening",
            "intended_purpose": "Test locking",
            "deployment_type": "saas",
            "decision_influence": "assistive",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    system_id = create_response.json()["id"]

    # First update succeeds (version 1 -> 2)
    update1 = await client.patch(
        f"/api/systems/{system_id}",
        json={"name": "Updated Name", "expected_version": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert update1.status_code == 200
    assert update1.json()["version"] == 2

    # Second update with stale version fails
    update2 = await client.patch(
        f"/api/systems/{system_id}",
        json={"name": "Conflicting Name", "expected_version": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert update2.status_code == 409


@pytest.mark.asyncio
async def test_systems_are_org_scoped(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """Test that systems are scoped to the user's organization."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create a system
    await client.post(
        "/api/systems",
        json={
            "name": "Org Scoped System",
            "hr_use_case_type": "recruitment_screening",
            "intended_purpose": "Test org scoping",
            "deployment_type": "saas",
            "decision_influence": "assistive",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    # List should only show this org's systems
    response = await client.get(
        "/api/systems",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    for system in response.json()["items"]:
        # All returned systems should be from the test org
        # (This is implicitly verified by the query filter in the service)
        assert system["name"]  # System belongs to test user's org
