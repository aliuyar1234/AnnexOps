"""Contract tests for /systems/{id}/versions endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import create_access_token
from src.models.ai_system import AISystem
from src.models.organization import Organization
from src.models.user import User


@pytest.mark.asyncio
async def test_create_version_returns_201_with_valid_data(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """POST /systems/{id}/versions returns 201 with valid version data."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions",
        json={
            "label": "1.0.0",
            "notes": "Initial release version",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["label"] == "1.0.0"
    assert data["status"] == "draft"
    assert data["notes"] == "Initial release version"
    assert data["ai_system_id"] == str(test_ai_system.id)
    assert "id" in data
    assert "created_at" in data
    assert data["created_by"]["id"] == str(test_editor_user.id)


@pytest.mark.asyncio
async def test_create_version_returns_422_with_invalid_label(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """POST /systems/{id}/versions returns 422 with invalid label."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Test empty label
    response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions",
        json={
            "label": "",
            "notes": "Test version",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_version_returns_422_with_label_too_long(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """POST /systems/{id}/versions returns 422 when label exceeds 50 chars."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions",
        json={
            "label": "a" * 51,  # 51 characters
            "notes": "Test version",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_version_returns_409_with_duplicate_label(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """POST /systems/{id}/versions returns 409 for duplicate label in same system."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create first version
    response1 = await client.post(
        f"/api/systems/{test_ai_system.id}/versions",
        json={
            "label": "1.0.0",
            "notes": "First version",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response1.status_code == 201

    # Try to create duplicate
    response2 = await client.post(
        f"/api/systems/{test_ai_system.id}/versions",
        json={
            "label": "1.0.0",
            "notes": "Duplicate version",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response2.status_code == 409


@pytest.mark.asyncio
async def test_create_version_returns_403_for_viewer(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_viewer_user: User,
    test_ai_system: AISystem,
):
    """POST /systems/{id}/versions returns 403 for viewer role."""
    token = create_access_token({"sub": str(test_viewer_user.id)})

    response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions",
        json={
            "label": "1.0.0",
            "notes": "Should fail",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_version_returns_404_for_nonexistent_system(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """POST /systems/{id}/versions returns 404 for non-existent system."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    response = await client.post(
        "/api/systems/00000000-0000-0000-0000-000000000000/versions",
        json={
            "label": "1.0.0",
            "notes": "Should fail",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_versions_returns_200(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_viewer_user: User,
    test_ai_system: AISystem,
):
    """GET /systems/{id}/versions returns 200 with version list."""
    token = create_access_token({"sub": str(test_viewer_user.id)})

    response = await client.get(
        f"/api/systems/{test_ai_system.id}/versions",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_list_versions_with_status_filter(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """GET /systems/{id}/versions with status filter returns filtered results."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create a version
    await client.post(
        f"/api/systems/{test_ai_system.id}/versions",
        json={
            "label": "1.0.0",
            "notes": "Draft version",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    # List with filter
    response = await client.get(
        f"/api/systems/{test_ai_system.id}/versions?status=draft",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["status"] == "draft"


@pytest.mark.asyncio
async def test_list_versions_returns_404_for_nonexistent_system(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_viewer_user: User,
):
    """GET /systems/{id}/versions returns 404 for non-existent system."""
    token = create_access_token({"sub": str(test_viewer_user.id)})

    response = await client.get(
        "/api/systems/00000000-0000-0000-0000-000000000000/versions",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_change_status_returns_200_with_valid_transition(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """PATCH /systems/{id}/versions/{vid}/status returns 200 for valid transition."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create a version (starts as draft)
    create_response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions",
        json={"label": "1.0.0", "notes": "Test version"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_response.status_code == 201
    version_id = create_response.json()["id"]

    # Transition to review
    response = await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/{version_id}/status",
        json={"status": "review", "comment": "Ready for review"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "review"
    assert data["id"] == version_id


@pytest.mark.asyncio
async def test_change_status_returns_409_for_invalid_transition(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """PATCH /systems/{id}/versions/{vid}/status returns 409 for invalid transition."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create a version (starts as draft)
    create_response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions",
        json={"label": "1.0.0", "notes": "Test version"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_response.status_code == 201
    version_id = create_response.json()["id"]

    # Try invalid transition: draft -> approved (must go through review)
    response = await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/{version_id}/status",
        json={"status": "approved"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_change_status_returns_403_for_editor_approving(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """PATCH /systems/{id}/versions/{vid}/status returns 403 when editor tries to approve."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create a version and transition to review
    create_response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions",
        json={"label": "1.0.0", "notes": "Test version"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_response.status_code == 201
    version_id = create_response.json()["id"]

    # Transition to review first
    await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/{version_id}/status",
        json={"status": "review"},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Try to approve as editor (should fail)
    response = await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/{version_id}/status",
        json={"status": "approved"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_change_status_returns_200_for_admin_approving(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_admin_user: User,
    test_ai_system: AISystem,
):
    """PATCH /systems/{id}/versions/{vid}/status returns 200 when admin approves."""
    token = create_access_token({"sub": str(test_admin_user.id)})

    # Create a version and transition to review
    create_response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions",
        json={"label": "1.0.0", "notes": "Test version"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_response.status_code == 201
    version_id = create_response.json()["id"]

    # Transition to review first
    await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/{version_id}/status",
        json={"status": "review"},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Approve as admin (should succeed)
    response = await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/{version_id}/status",
        json={"status": "approved", "comment": "Approved for production"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "approved"


@pytest.mark.asyncio
async def test_change_status_returns_404_for_nonexistent_version(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """PATCH /systems/{id}/versions/{vid}/status returns 404 for non-existent version."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    response = await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/00000000-0000-0000-0000-000000000000/status",
        json={"status": "review"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_compare_versions_returns_200_with_valid_versions(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """GET /systems/{id}/versions/compare returns 200 with diff between two versions."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create first version
    response1 = await client.post(
        f"/api/systems/{test_ai_system.id}/versions",
        json={"label": "1.0.0", "notes": "Initial version"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response1.status_code == 201
    version1_id = response1.json()["id"]

    # Create second version with different data
    response2 = await client.post(
        f"/api/systems/{test_ai_system.id}/versions",
        json={"label": "1.1.0", "notes": "Updated version"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response2.status_code == 201
    version2_id = response2.json()["id"]

    # Compare versions
    response = await client.get(
        f"/api/systems/{test_ai_system.id}/versions/compare?from_version={version1_id}&to_version={version2_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "from_version" in data
    assert "to_version" in data
    assert "changes" in data
    assert "summary" in data
    assert data["from_version"]["id"] == version1_id
    assert data["to_version"]["id"] == version2_id
    assert isinstance(data["changes"], list)
    assert isinstance(data["summary"], dict)


@pytest.mark.asyncio
async def test_compare_versions_returns_400_for_cross_system_comparison(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """GET /systems/{id}/versions/compare returns 400 when versions are from different systems."""
    from tests.conftest import create_ai_system, create_version

    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create first version for test_ai_system
    version1 = await create_version(
        db=db,
        ai_system_id=test_ai_system.id,
        label="1.0.0",
        created_by=test_editor_user.id,
    )
    await db.commit()

    # Create another AI system
    system2 = await create_ai_system(
        db=db,
        org_id=test_org.id,
        name="Another System",
        owner_user_id=test_editor_user.id,
    )
    await db.commit()

    # Create version for second system
    version2 = await create_version(
        db=db,
        ai_system_id=system2.id,
        label="1.0.0",
        created_by=test_editor_user.id,
    )
    await db.commit()

    # Try to compare versions from different systems
    response = await client.get(
        f"/api/systems/{test_ai_system.id}/versions/compare?from_version={version1.id}&to_version={version2.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_compare_versions_returns_422_with_missing_parameters(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_viewer_user: User,
    test_ai_system: AISystem,
):
    """GET /systems/{id}/versions/compare returns 422 when query params are missing."""
    token = create_access_token({"sub": str(test_viewer_user.id)})

    # Missing both parameters
    response = await client.get(
        f"/api/systems/{test_ai_system.id}/versions/compare",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422

    # Missing to_version parameter
    response = await client.get(
        f"/api/systems/{test_ai_system.id}/versions/compare?from_version=00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_compare_versions_returns_404_for_nonexistent_version(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_viewer_user: User,
    test_ai_system: AISystem,
):
    """GET /systems/{id}/versions/compare returns 404 when version doesn't exist."""
    token = create_access_token({"sub": str(test_viewer_user.id)})

    response = await client.get(
        f"/api/systems/{test_ai_system.id}/versions/compare?from_version=00000000-0000-0000-0000-000000000000&to_version=00000000-0000-0000-0000-000000000001",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_version_by_id_returns_200_with_detail_response(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """GET /systems/{id}/versions/{vid} returns 200 with version detail."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create a version
    create_response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions",
        json={
            "label": "1.0.0",
            "notes": "Initial release",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_response.status_code == 201
    version_id = create_response.json()["id"]

    # Get the version by ID
    response = await client.get(
        f"/api/systems/{test_ai_system.id}/versions/{version_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == version_id
    assert data["label"] == "1.0.0"
    assert data["notes"] == "Initial release"
    assert data["status"] == "draft"
    assert data["ai_system_id"] == str(test_ai_system.id)
    assert "section_count" in data
    assert "evidence_count" in data
    assert data["section_count"] == 0  # Placeholder
    assert data["evidence_count"] == 0  # Placeholder
    assert "created_at" in data
    assert "updated_at" in data
    assert data["created_by"]["id"] == str(test_editor_user.id)


@pytest.mark.asyncio
async def test_get_version_by_id_returns_404_for_nonexistent_version(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_viewer_user: User,
    test_ai_system: AISystem,
):
    """GET /systems/{id}/versions/{vid} returns 404 for non-existent version."""
    token = create_access_token({"sub": str(test_viewer_user.id)})

    response = await client.get(
        f"/api/systems/{test_ai_system.id}/versions/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_version_by_id_returns_404_for_version_from_different_system(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """GET /systems/{id}/versions/{vid} returns 404 when version belongs to different system."""
    from tests.conftest import create_ai_system, create_version

    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create another system
    system2 = await create_ai_system(
        db=db,
        org_id=test_org.id,
        name="Other System",
        owner_user_id=test_editor_user.id,
    )
    await db.commit()

    # Create version for system2
    version2 = await create_version(
        db=db,
        ai_system_id=system2.id,
        label="1.0.0",
        created_by=test_editor_user.id,
    )
    await db.commit()

    # Try to get version from system2 using test_ai_system's path
    response = await client.get(
        f"/api/systems/{test_ai_system.id}/versions/{version2.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_version_returns_200_with_updated_data(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """PATCH /systems/{id}/versions/{vid} returns 200 with updated version data."""

    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create a version
    create_response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions",
        json={
            "label": "1.0.0",
            "notes": "Initial notes",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_response.status_code == 201
    version_id = create_response.json()["id"]

    # Update the version
    response = await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/{version_id}",
        json={
            "notes": "Updated release notes",
            "release_date": "2025-01-15",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == version_id
    assert data["notes"] == "Updated release notes"
    assert data["release_date"] == "2025-01-15"
    assert data["label"] == "1.0.0"  # Label unchanged


@pytest.mark.asyncio
async def test_update_version_returns_200_with_partial_update(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """PATCH /systems/{id}/versions/{vid} returns 200 when updating only release_date."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create a version
    create_response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions",
        json={
            "label": "2.0.0",
            "notes": "Original notes",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_response.status_code == 201
    version_id = create_response.json()["id"]

    # Update only release_date
    response = await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/{version_id}",
        json={
            "release_date": "2024-12-01",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["release_date"] == "2024-12-01"
    assert data["notes"] == "Original notes"  # Unchanged


@pytest.mark.asyncio
async def test_update_version_returns_403_for_viewer(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_viewer_user: User,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """PATCH /systems/{id}/versions/{vid} returns 403 for viewer role."""
    editor_token = create_access_token({"sub": str(test_editor_user.id)})
    viewer_token = create_access_token({"sub": str(test_viewer_user.id)})

    # Create a version as editor
    create_response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions",
        json={"label": "1.0.0", "notes": "Test"},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert create_response.status_code == 201
    version_id = create_response.json()["id"]

    # Try to update as viewer
    response = await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/{version_id}",
        json={"notes": "Unauthorized update"},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_update_version_returns_404_for_nonexistent_version(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """PATCH /systems/{id}/versions/{vid} returns 404 for non-existent version."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    response = await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/00000000-0000-0000-0000-000000000000",
        json={"notes": "Should fail"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_version_manifest_returns_200_with_manifest_structure(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """GET /systems/{id}/versions/{vid}/manifest returns 200 with complete manifest."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create a version
    create_response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions",
        json={
            "label": "1.0.0",
            "notes": "Release version",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_response.status_code == 201
    version_id = create_response.json()["id"]

    # Get the manifest
    response = await client.get(
        f"/api/systems/{test_ai_system.id}/versions/{version_id}/manifest",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()

    # Verify manifest structure (canonical export manifest)
    assert data["manifest_version"] == "1.0"
    assert "generated_at" in data
    assert "snapshot_hash" in data
    assert "org" in data
    assert "ai_system" in data
    assert "system_version" in data
    assert "high_risk_assessment" in data
    assert "annex_sections" in data
    assert "evidence_index" in data
    assert "mappings" in data

    # Verify org info
    assert data["org"]["id"] == str(test_org.id)
    assert data["org"]["name"] == test_org.name

    # Verify system info
    assert data["ai_system"]["id"] == str(test_ai_system.id)
    assert data["ai_system"]["name"] == test_ai_system.name
    assert data["ai_system"]["hr_use_case_type"] == test_ai_system.hr_use_case_type.value
    assert data["ai_system"]["intended_purpose"] == test_ai_system.intended_purpose

    # Verify version info
    assert data["system_version"]["id"] == version_id
    assert data["system_version"]["label"] == "1.0.0"
    assert data["system_version"]["status"] == "draft"

    # Version has no content yet => empty maps/lists
    assert data["high_risk_assessment"] is None
    assert isinstance(data["annex_sections"], dict)
    assert isinstance(data["evidence_index"], dict)
    assert isinstance(data["mappings"], list)
    assert len(data["annex_sections"]) == 0
    assert len(data["evidence_index"]) == 0
    assert len(data["mappings"]) == 0
    assert isinstance(data["snapshot_hash"], str)
    assert len(data["snapshot_hash"]) == 64


@pytest.mark.asyncio
async def test_get_version_manifest_returns_404_for_nonexistent_version(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_viewer_user: User,
    test_ai_system: AISystem,
):
    """GET /systems/{id}/versions/{vid}/manifest returns 404 for non-existent version."""
    token = create_access_token({"sub": str(test_viewer_user.id)})

    response = await client.get(
        f"/api/systems/{test_ai_system.id}/versions/00000000-0000-0000-0000-000000000000/manifest",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_version_manifest_returns_404_for_version_from_different_system(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """GET /systems/{id}/versions/{vid}/manifest returns 404 when version belongs to different system."""
    from tests.conftest import create_ai_system, create_version

    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create another system
    system2 = await create_ai_system(
        db=db,
        org_id=test_org.id,
        name="Different System",
        owner_user_id=test_editor_user.id,
    )
    await db.commit()

    # Create version for system2
    version2 = await create_version(
        db=db,
        ai_system_id=system2.id,
        label="1.0.0",
        created_by=test_editor_user.id,
    )
    await db.commit()

    # Try to get manifest for version2 using test_ai_system's path
    response = await client.get(
        f"/api/systems/{test_ai_system.id}/versions/{version2.id}/manifest",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_clone_version_returns_201_with_new_version(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """POST /systems/{id}/versions/{vid}/clone returns 201 with cloned version."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create a version to clone
    create_response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions",
        json={
            "label": "original-1.0",
            "notes": "Original version notes",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_response.status_code == 201
    original_version_id = create_response.json()["id"]

    # Clone the version
    response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions/{original_version_id}/clone",
        json={
            "label": "cloned-1.0",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["label"] == "cloned-1.0"
    assert data["status"] == "draft"
    assert data["notes"] == "Original version notes"  # Notes copied
    assert data["ai_system_id"] == str(test_ai_system.id)
    assert data["id"] != original_version_id  # New ID
    assert data["created_by"]["id"] == str(test_editor_user.id)


@pytest.mark.asyncio
async def test_clone_version_returns_422_with_invalid_label(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """POST /systems/{id}/versions/{vid}/clone returns 422 with invalid label."""
    from tests.conftest import create_version

    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create a version to clone
    version = await create_version(
        db=db,
        ai_system_id=test_ai_system.id,
        label="source-version",
        created_by=test_editor_user.id,
    )
    await db.commit()

    # Try to clone with invalid label (special characters)
    response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions/{version.id}/clone",
        json={
            "label": "invalid label with spaces!",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_clone_version_returns_409_with_duplicate_label(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """POST /systems/{id}/versions/{vid}/clone returns 409 for duplicate label."""
    from tests.conftest import create_version

    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create two versions
    version1 = await create_version(
        db=db,
        ai_system_id=test_ai_system.id,
        label="source-v1",
        created_by=test_editor_user.id,
    )
    await create_version(
        db=db,
        ai_system_id=test_ai_system.id,
        label="existing-label",
        created_by=test_editor_user.id,
    )
    await db.commit()

    # Try to clone version1 with label that already exists (version2's label)
    response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions/{version1.id}/clone",
        json={
            "label": "existing-label",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_clone_version_returns_403_for_viewer(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_viewer_user: User,
    test_ai_system: AISystem,
):
    """POST /systems/{id}/versions/{vid}/clone returns 403 for viewer role."""
    from tests.conftest import create_version

    token = create_access_token({"sub": str(test_viewer_user.id)})

    # Create a version
    version = await create_version(
        db=db,
        ai_system_id=test_ai_system.id,
        label="clone-source",
        created_by=test_viewer_user.id,
    )
    await db.commit()

    # Try to clone as viewer
    response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions/{version.id}/clone",
        json={
            "label": "cloned-version",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_clone_version_returns_404_for_nonexistent_version(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """POST /systems/{id}/versions/{vid}/clone returns 404 for non-existent version."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions/00000000-0000-0000-0000-000000000000/clone",
        json={
            "label": "cloned-version",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
