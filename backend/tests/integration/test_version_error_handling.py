"""Integration tests for version error handling (404 and validation)."""

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import create_access_token
from src.models.ai_system import AISystem
from src.models.organization import Organization
from src.models.user import User
from tests.conftest import create_ai_system, create_version


@pytest.mark.asyncio
async def test_get_nonexistent_version_returns_404(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """Test that getting a non-existent version returns 404."""
    token = create_access_token({"sub": str(test_editor_user.id)})
    fake_version_id = uuid4()

    response = await client.get(
        f"/api/systems/{test_ai_system.id}/versions/{fake_version_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
    assert "Version not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_update_nonexistent_version_returns_404(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """Test that updating a non-existent version returns 404."""
    token = create_access_token({"sub": str(test_editor_user.id)})
    fake_version_id = uuid4()

    response = await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/{fake_version_id}",
        json={"notes": "Update attempt"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
    assert "Version not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_delete_nonexistent_version_returns_404(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_admin_user: User,
    test_ai_system: AISystem,
):
    """Test that deleting a non-existent version returns 404."""
    token = create_access_token({"sub": str(test_admin_user.id)})
    fake_version_id = uuid4()

    response = await client.delete(
        f"/api/systems/{test_ai_system.id}/versions/{fake_version_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
    assert "Version not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_change_status_nonexistent_version_returns_404(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """Test that changing status of a non-existent version returns 404."""
    token = create_access_token({"sub": str(test_editor_user.id)})
    fake_version_id = uuid4()

    response = await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/{fake_version_id}/status",
        json={"status": "review"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
    assert "Version not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_clone_nonexistent_version_returns_404(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """Test that cloning a non-existent version returns 404."""
    token = create_access_token({"sub": str(test_editor_user.id)})
    fake_version_id = uuid4()

    response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions/{fake_version_id}/clone",
        json={"label": "v1.0.0-clone"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
    assert "Version not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_version_from_different_system_returns_404(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """Test that accessing a version from a different system returns 404."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create a second AI system
    system2 = await create_ai_system(
        db,
        org_id=test_org.id,
        name="Second System",
        owner_user_id=test_editor_user.id,
    )

    # Create a version for the second system
    version2 = await create_version(
        db,
        ai_system_id=system2.id,
        label="v1.0.0",
        created_by=test_editor_user.id,
    )
    await db.commit()

    # Try to access version2 via system1's endpoint (should fail with 404)
    response = await client.get(
        f"/api/systems/{test_ai_system.id}/versions/{version2.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
    assert "Version not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_update_version_from_different_system_returns_404(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """Test that updating a version via wrong system ID returns 404."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create a second AI system
    system2 = await create_ai_system(
        db,
        org_id=test_org.id,
        name="Second System",
        owner_user_id=test_editor_user.id,
    )

    # Create a version for the second system
    version2 = await create_version(
        db,
        ai_system_id=system2.id,
        label="v1.0.0",
        created_by=test_editor_user.id,
    )
    await db.commit()

    # Try to update version2 via system1's endpoint (should fail with 404)
    response = await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/{version2.id}",
        json={"notes": "Update attempt"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
    assert "Version not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_delete_version_from_different_system_returns_404(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_admin_user: User,
    test_ai_system: AISystem,
):
    """Test that deleting a version via wrong system ID returns 404."""
    token = create_access_token({"sub": str(test_admin_user.id)})

    # Create a second AI system
    system2 = await create_ai_system(
        db,
        org_id=test_org.id,
        name="Second System",
        owner_user_id=test_admin_user.id,
    )

    # Create a version for the second system
    version2 = await create_version(
        db,
        ai_system_id=system2.id,
        label="v1.0.0",
        created_by=test_admin_user.id,
    )
    await db.commit()

    # Try to delete version2 via system1's endpoint (should fail with 404)
    response = await client.delete(
        f"/api/systems/{test_ai_system.id}/versions/{version2.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
    assert "Version not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_nonexistent_system_returns_404(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """Test that accessing versions for a non-existent system returns 404."""
    token = create_access_token({"sub": str(test_editor_user.id)})
    fake_system_id = uuid4()

    # List versions for non-existent system
    response = await client.get(
        f"/api/systems/{fake_system_id}/versions",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
    assert "AI system not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_version_for_nonexistent_system_returns_404(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """Test that creating a version for a non-existent system returns 404."""
    token = create_access_token({"sub": str(test_editor_user.id)})
    fake_system_id = uuid4()

    response = await client.post(
        f"/api/systems/{fake_system_id}/versions",
        json={
            "label": "v1.0.0",
            "notes": "Test version",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
    assert "AI system not found" in response.json()["detail"]
