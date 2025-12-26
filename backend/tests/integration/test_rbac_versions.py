"""Integration tests for RBAC enforcement on system versions."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import create_access_token
from src.models.organization import Organization
from src.models.user import User
from src.models.ai_system import AISystem
from src.models.system_version import SystemVersion
from src.models.enums import VersionStatus


@pytest.mark.asyncio
async def test_viewer_cannot_create_version(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_viewer_user: User,
    test_ai_system: AISystem,
):
    """Test that viewer role cannot create versions (403)."""
    token = create_access_token({"sub": str(test_viewer_user.id)})

    response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions",
        json={
            "label": "v1.0.0",
            "notes": "Viewer attempt to create version",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert "Insufficient permissions" in response.json()["detail"]


@pytest.mark.asyncio
async def test_editor_cannot_approve_version(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
    test_version: SystemVersion,
):
    """Test that editor role cannot approve versions (403)."""
    # First transition to review status (editor can do this)
    editor_token = create_access_token({"sub": str(test_editor_user.id)})

    review_response = await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}/status",
        json={
            "status": "review",
            "comment": "Ready for review",
        },
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert review_response.status_code == 200

    # Now try to approve (should fail with 403)
    approve_response = await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}/status",
        json={
            "status": "approved",
            "comment": "Approving as editor",
        },
        headers={"Authorization": f"Bearer {editor_token}"},
    )

    assert approve_response.status_code == 403
    assert "Only administrators can approve versions" in approve_response.json()["detail"]


@pytest.mark.asyncio
async def test_admin_can_perform_all_version_operations(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_admin_user: User,
    test_ai_system: AISystem,
):
    """Test that admin role can perform all version operations."""
    token = create_access_token({"sub": str(test_admin_user.id)})

    # Create version
    create_response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions",
        json={
            "label": "v1.0.0",
            "notes": "Admin created version",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_response.status_code == 201
    version_id = create_response.json()["id"]

    # Read version
    read_response = await client.get(
        f"/api/systems/{test_ai_system.id}/versions/{version_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert read_response.status_code == 200

    # Update version
    update_response = await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/{version_id}",
        json={"notes": "Updated by admin"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert update_response.status_code == 200

    # Transition to review
    review_response = await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/{version_id}/status",
        json={"status": "review"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert review_response.status_code == 200

    # Approve version (admin only)
    approve_response = await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/{version_id}/status",
        json={"status": "approved"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert approve_response.status_code == 200

    # Clone version
    clone_response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions/{version_id}/clone",
        json={"label": "v1.0.0-clone"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert clone_response.status_code == 201
    cloned_version_id = clone_response.json()["id"]

    # Delete cloned version (admin only, and it's in draft status so not immutable)
    delete_response = await client.delete(
        f"/api/systems/{test_ai_system.id}/versions/{cloned_version_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert delete_response.status_code == 204


@pytest.mark.asyncio
async def test_viewer_can_read_versions(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_viewer_user: User,
    test_ai_system: AISystem,
    test_version: SystemVersion,
):
    """Test that viewer role can read versions."""
    token = create_access_token({"sub": str(test_viewer_user.id)})

    # List versions
    list_response = await client.get(
        f"/api/systems/{test_ai_system.id}/versions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_response.status_code == 200
    assert list_response.json()["total"] >= 1

    # Get version by ID
    get_response = await client.get(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_response.status_code == 200


@pytest.mark.asyncio
async def test_viewer_cannot_update_version(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_viewer_user: User,
    test_ai_system: AISystem,
    test_version: SystemVersion,
):
    """Test that viewer role cannot update versions."""
    token = create_access_token({"sub": str(test_viewer_user.id)})

    response = await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}",
        json={"notes": "Viewer update attempt"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert "Insufficient permissions" in response.json()["detail"]


@pytest.mark.asyncio
async def test_viewer_cannot_change_status(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_viewer_user: User,
    test_ai_system: AISystem,
    test_version: SystemVersion,
):
    """Test that viewer role cannot change version status."""
    token = create_access_token({"sub": str(test_viewer_user.id)})

    response = await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}/status",
        json={"status": "review"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert "Insufficient permissions" in response.json()["detail"]


@pytest.mark.asyncio
async def test_viewer_cannot_clone_version(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_viewer_user: User,
    test_ai_system: AISystem,
    test_version: SystemVersion,
):
    """Test that viewer role cannot clone versions."""
    token = create_access_token({"sub": str(test_viewer_user.id)})

    response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}/clone",
        json={"label": "v1.0.0-clone"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert "Insufficient permissions" in response.json()["detail"]


@pytest.mark.asyncio
async def test_viewer_cannot_delete_version(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_viewer_user: User,
    test_ai_system: AISystem,
    test_version: SystemVersion,
):
    """Test that viewer role cannot delete versions."""
    token = create_access_token({"sub": str(test_viewer_user.id)})

    response = await client.delete(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert "Insufficient permissions" in response.json()["detail"]


@pytest.mark.asyncio
async def test_editor_cannot_delete_version(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
    test_version: SystemVersion,
):
    """Test that editor role cannot delete versions (admin only)."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    response = await client.delete(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert "Insufficient permissions" in response.json()["detail"]


@pytest.mark.asyncio
async def test_editor_can_create_update_clone(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """Test that editor role can create, update, and clone versions."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create version
    create_response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions",
        json={
            "label": "v2.0.0",
            "notes": "Editor created version",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_response.status_code == 201
    version_id = create_response.json()["id"]

    # Update version
    update_response = await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/{version_id}",
        json={"notes": "Updated by editor"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert update_response.status_code == 200

    # Clone version
    clone_response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions/{version_id}/clone",
        json={"label": "v2.0.0-clone"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert clone_response.status_code == 201
