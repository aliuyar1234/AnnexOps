"""Integration tests for RBAC enforcement on systems."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import create_access_token
from src.models.ai_system import AISystem
from src.models.organization import Organization
from src.models.user import User


@pytest.mark.asyncio
async def test_viewer_cannot_create_system(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_viewer_user: User,
):
    """Test that viewer role cannot create systems."""
    token = create_access_token({"sub": str(test_viewer_user.id)})

    response = await client.post(
        "/api/systems",
        json={
            "name": "Viewer Test System",
            "hr_use_case_type": "recruitment_screening",
            "intended_purpose": "Test purpose",
            "deployment_type": "saas",
            "decision_influence": "assistive",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert "Insufficient permissions" in response.json()["detail"]


@pytest.mark.asyncio
async def test_editor_cannot_delete_system(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """Test that editor role cannot delete systems (admin only)."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    response = await client.delete(
        f"/api/systems/{test_ai_system.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert "Insufficient permissions" in response.json()["detail"]


@pytest.mark.asyncio
async def test_admin_can_delete_system(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_admin_user: User,
    test_editor_user: User,
):
    """Test that admin role can delete systems."""
    # Create a system first using editor
    editor_token = create_access_token({"sub": str(test_editor_user.id)})
    create_response = await client.post(
        "/api/systems",
        json={
            "name": "Admin Delete Test",
            "hr_use_case_type": "recruitment_screening",
            "intended_purpose": "Test for admin deletion",
            "deployment_type": "saas",
            "decision_influence": "assistive",
        },
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    system_id = create_response.json()["id"]

    # Delete using admin
    admin_token = create_access_token({"sub": str(test_admin_user.id)})
    response = await client.delete(
        f"/api/systems/{system_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 204

    # Verify deleted
    get_response = await client.get(
        f"/api/systems/{system_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_admin_can_perform_all_operations(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_admin_user: User,
):
    """Test that admin role can perform all system operations."""
    token = create_access_token({"sub": str(test_admin_user.id)})

    # Create
    create_response = await client.post(
        "/api/systems",
        json={
            "name": "Admin Full Access Test",
            "hr_use_case_type": "recruitment_screening",
            "intended_purpose": "Test admin full access",
            "deployment_type": "saas",
            "decision_influence": "assistive",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_response.status_code == 201
    system_id = create_response.json()["id"]

    # Read
    read_response = await client.get(
        f"/api/systems/{system_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert read_response.status_code == 200

    # Update
    update_response = await client.patch(
        f"/api/systems/{system_id}",
        json={"name": "Updated by Admin", "expected_version": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert update_response.status_code == 200

    # Delete
    delete_response = await client.delete(
        f"/api/systems/{system_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert delete_response.status_code == 204


@pytest.mark.asyncio
async def test_viewer_can_read_systems(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_viewer_user: User,
    test_ai_system: AISystem,
):
    """Test that viewer role can read systems."""
    token = create_access_token({"sub": str(test_viewer_user.id)})

    # List
    list_response = await client.get(
        "/api/systems",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_response.status_code == 200

    # Get by ID
    get_response = await client.get(
        f"/api/systems/{test_ai_system.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_response.status_code == 200


@pytest.mark.asyncio
async def test_viewer_cannot_update_system(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_viewer_user: User,
    test_ai_system: AISystem,
):
    """Test that viewer role cannot update systems."""
    token = create_access_token({"sub": str(test_viewer_user.id)})

    response = await client.patch(
        f"/api/systems/{test_ai_system.id}",
        json={"name": "Viewer Update Attempt", "expected_version": 1},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
