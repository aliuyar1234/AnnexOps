"""Integration tests for version creation and listing."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import create_access_token
from src.models.organization import Organization
from src.models.user import User
from src.models.ai_system import AISystem
from tests.conftest import create_ai_system


@pytest.mark.asyncio
async def test_version_creation_flow(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """Test complete version creation flow: create -> verify in list."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create a version
    create_response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions",
        json={
            "label": "v1.0.0",
            "notes": "Initial production release",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_response.status_code == 201
    created_version = create_response.json()
    version_id = created_version["id"]

    # Verify it appears in the list
    list_response = await client.get(
        f"/api/systems/{test_ai_system.id}/versions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_response.status_code == 200
    versions = list_response.json()
    assert versions["total"] >= 1
    version_ids = [v["id"] for v in versions["items"]]
    assert version_id in version_ids

    # Verify version has draft status
    created_version_in_list = next(v for v in versions["items"] if v["id"] == version_id)
    assert created_version_in_list["status"] == "draft"
    assert created_version_in_list["label"] == "v1.0.0"


@pytest.mark.asyncio
async def test_duplicate_label_within_system_fails(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """Test that duplicate labels within same system are rejected."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    version_data = {
        "label": "duplicate-label",
        "notes": "Test version",
    }

    # Create first version
    response1 = await client.post(
        f"/api/systems/{test_ai_system.id}/versions",
        json=version_data,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response1.status_code == 201

    # Try to create duplicate in same system
    response2 = await client.post(
        f"/api/systems/{test_ai_system.id}/versions",
        json=version_data,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response2.status_code == 409


@pytest.mark.asyncio
async def test_same_label_in_different_systems_allowed(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """Test that same label can be used in different AI systems."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create a second AI system
    system2 = await create_ai_system(
        db=db,
        org_id=test_org.id,
        name="Second System",
        owner_user_id=test_editor_user.id,
    )
    await db.commit()

    version_data = {
        "label": "1.0.0",
        "notes": "Same label, different system",
    }

    # Create version in first system
    response1 = await client.post(
        f"/api/systems/{test_ai_system.id}/versions",
        json=version_data,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response1.status_code == 201

    # Create version with same label in second system - should succeed
    response2 = await client.post(
        f"/api/systems/{system2.id}/versions",
        json=version_data,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response2.status_code == 201


@pytest.mark.asyncio
async def test_version_creator_is_current_user(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """Test that version creator is set to the creating user."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions",
        json={
            "label": "creator-test",
            "notes": "Testing creator assignment",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["created_by"]["id"] == str(test_editor_user.id)


@pytest.mark.asyncio
async def test_label_validation_patterns(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """Test version label validation accepts valid patterns."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    valid_labels = [
        "1.0.0",
        "v2.3.4",
        "2024-Q1",
        "release_1.0",
        "beta-2",
        "1.0.0-rc.1",
    ]

    for i, label in enumerate(valid_labels):
        response = await client.post(
            f"/api/systems/{test_ai_system.id}/versions",
            json={
                "label": label,
                "notes": f"Test valid label pattern {i}",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201, f"Label '{label}' should be valid"


@pytest.mark.asyncio
async def test_versions_are_system_scoped(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """Test that versions are scoped to their AI system."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create a second AI system
    system2 = await create_ai_system(
        db=db,
        org_id=test_org.id,
        name="Scoping Test System",
        owner_user_id=test_editor_user.id,
    )
    await db.commit()

    # Create version in first system
    await client.post(
        f"/api/systems/{test_ai_system.id}/versions",
        json={
            "label": "scoped-1.0",
            "notes": "Version for system 1",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    # Create version in second system
    await client.post(
        f"/api/systems/{system2.id}/versions",
        json={
            "label": "scoped-2.0",
            "notes": "Version for system 2",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    # List versions for first system
    response1 = await client.get(
        f"/api/systems/{test_ai_system.id}/versions",
        headers={"Authorization": f"Bearer {token}"},
    )
    system1_labels = [v["label"] for v in response1.json()["items"]]
    assert "scoped-1.0" in system1_labels
    assert "scoped-2.0" not in system1_labels

    # List versions for second system
    response2 = await client.get(
        f"/api/systems/{system2.id}/versions",
        headers={"Authorization": f"Bearer {token}"},
    )
    system2_labels = [v["label"] for v in response2.json()["items"]]
    assert "scoped-2.0" in system2_labels
    assert "scoped-1.0" not in system2_labels


@pytest.mark.asyncio
async def test_status_filter_works(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """Test that status filter correctly filters versions."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create versions (all will be draft initially)
    await client.post(
        f"/api/systems/{test_ai_system.id}/versions",
        json={"label": "draft-1", "notes": "Draft version"},
        headers={"Authorization": f"Bearer {token}"},
    )

    # List with draft filter
    response = await client.get(
        f"/api/systems/{test_ai_system.id}/versions?status=draft",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    for version in data["items"]:
        assert version["status"] == "draft"


@pytest.mark.asyncio
async def test_version_comparison_flow(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """Test complete version comparison flow: create two versions, compare them."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create first version
    v1_response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions",
        json={"label": "v1.0.0", "notes": "First version"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert v1_response.status_code == 201
    v1_id = v1_response.json()["id"]

    # Create second version with different data
    v2_response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions",
        json={"label": "v2.0.0", "notes": "Second version"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert v2_response.status_code == 201
    v2_id = v2_response.json()["id"]

    # Compare versions
    compare_response = await client.get(
        f"/api/systems/{test_ai_system.id}/versions/compare?from_version={v1_id}&to_version={v2_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert compare_response.status_code == 200
    diff_data = compare_response.json()

    # Verify response structure
    assert "from_version" in diff_data
    assert "to_version" in diff_data
    assert "changes" in diff_data
    assert "summary" in diff_data

    # Verify version summaries
    assert diff_data["from_version"]["id"] == v1_id
    assert diff_data["from_version"]["label"] == "v1.0.0"
    assert diff_data["from_version"]["status"] == "draft"

    assert diff_data["to_version"]["id"] == v2_id
    assert diff_data["to_version"]["label"] == "v2.0.0"
    assert diff_data["to_version"]["status"] == "draft"

    # Verify changes detected
    assert isinstance(diff_data["changes"], list)
    assert len(diff_data["changes"]) > 0

    # Should detect label and notes changes at minimum
    changed_fields = [c["field"] for c in diff_data["changes"]]
    assert "label" in changed_fields
    assert "notes" in changed_fields

    # Verify summary
    assert "added" in diff_data["summary"]
    assert "removed" in diff_data["summary"]
    assert "modified" in diff_data["summary"]


@pytest.mark.asyncio
async def test_version_comparison_detects_status_changes(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_admin_user: User,
    test_ai_system: AISystem,
):
    """Test that version comparison detects status changes."""
    token = create_access_token({"sub": str(test_admin_user.id)})

    # Create version (draft)
    v1_response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions",
        json={"label": "status-test", "notes": "Test version"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert v1_response.status_code == 201
    v1_id = v1_response.json()["id"]

    # Transition to review
    await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/{v1_id}/status",
        json={"status": "review"},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Create another version
    v2_response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions",
        json={"label": "status-test-2", "notes": "Test version"},
        headers={"Authorization": f"Bearer {token}"},
    )
    v2_id = v2_response.json()["id"]

    # Compare: v1 (review) vs v2 (draft)
    compare_response = await client.get(
        f"/api/systems/{test_ai_system.id}/versions/compare?from_version={v1_id}&to_version={v2_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert compare_response.status_code == 200
    diff_data = compare_response.json()

    # Should detect status change
    status_change = next(
        (c for c in diff_data["changes"] if c["field"] == "status"),
        None,
    )
    assert status_change is not None
    assert status_change["old_value"] == "review"
    assert status_change["new_value"] == "draft"


@pytest.mark.asyncio
async def test_cross_system_version_comparison_rejected(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """Test that comparing versions from different systems is rejected."""
    from tests.conftest import create_ai_system, create_version

    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create version for first system
    v1 = await create_version(
        db=db,
        ai_system_id=test_ai_system.id,
        label="cross-test-1",
        created_by=test_editor_user.id,
    )
    await db.commit()

    # Create second system
    system2 = await create_ai_system(
        db=db,
        org_id=test_org.id,
        name="Second System for Cross Test",
        owner_user_id=test_editor_user.id,
    )
    await db.commit()

    # Create version for second system
    v2 = await create_version(
        db=db,
        ai_system_id=system2.id,
        label="cross-test-2",
        created_by=test_editor_user.id,
    )
    await db.commit()

    # Try to compare versions from different systems
    response = await client.get(
        f"/api/systems/{test_ai_system.id}/versions/compare?from_version={v1.id}&to_version={v2.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    # Should return error - either 400 (bad request) or 404 (version not found for this system)
    assert response.status_code in [400, 404]
    error_data = response.json()
    assert "detail" in error_data


@pytest.mark.asyncio
async def test_version_update_with_release_date(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """Test updating version with release date (past and future dates allowed)."""
    from datetime import date, timedelta

    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create a version
    create_response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions",
        json={"label": "release-test", "notes": "Pre-release"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_response.status_code == 201
    version_id = create_response.json()["id"]

    # Update with future release date (pre-announced release)
    future_date = (date.today() + timedelta(days=30)).isoformat()
    update_response = await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/{version_id}",
        json={
            "release_date": future_date,
            "notes": "Scheduled for future release",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["release_date"] == future_date
    assert update_response.json()["notes"] == "Scheduled for future release"

    # Update with past release date (already released)
    past_date = (date.today() - timedelta(days=10)).isoformat()
    update_response2 = await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/{version_id}",
        json={
            "release_date": past_date,
            "notes": "Released in production",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert update_response2.status_code == 200
    assert update_response2.json()["release_date"] == past_date

    # Verify persistence by getting the version
    get_response = await client.get(
        f"/api/systems/{test_ai_system.id}/versions/{version_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_response.status_code == 200
    assert get_response.json()["release_date"] == past_date
    assert get_response.json()["notes"] == "Released in production"


@pytest.mark.asyncio
async def test_version_update_notes_only(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """Test updating version notes without changing release date."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create a version with release date
    create_response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions",
        json={"label": "notes-update-test", "notes": "Initial"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_response.status_code == 201
    version_id = create_response.json()["id"]

    # Set release date
    await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/{version_id}",
        json={"release_date": "2025-06-01"},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Update only notes
    update_response = await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/{version_id}",
        json={"notes": "Updated changelog"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert update_response.status_code == 200
    data = update_response.json()
    assert data["notes"] == "Updated changelog"
    assert data["release_date"] == "2025-06-01"  # Unchanged


@pytest.mark.asyncio
async def test_version_detail_includes_counts(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_viewer_user: User,
    test_ai_system: AISystem,
):
    """Test that version detail response includes section_count and evidence_count."""
    from tests.conftest import create_version

    token = create_access_token({"sub": str(test_viewer_user.id)})

    # Create a version directly
    version = await create_version(
        db=db,
        ai_system_id=test_ai_system.id,
        label="count-test",
        created_by=test_viewer_user.id,
    )
    await db.commit()

    # Get version detail
    response = await client.get(
        f"/api/systems/{test_ai_system.id}/versions/{version.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "section_count" in data
    assert "evidence_count" in data
    # Placeholders for future modules
    assert data["section_count"] == 0
    assert data["evidence_count"] == 0


@pytest.mark.asyncio
async def test_version_update_creates_audit_log(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """Test that version updates are logged in audit trail."""
    from sqlalchemy import select
    from src.models.audit_event import AuditEvent
    from src.models.enums import AuditAction

    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create a version
    create_response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions",
        json={"label": "audit-test", "notes": "Original"},
        headers={"Authorization": f"Bearer {token}"},
    )
    version_id = create_response.json()["id"]

    # Update the version
    await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/{version_id}",
        json={
            "notes": "Updated for audit",
            "release_date": "2025-02-01",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    # Check audit log
    query = select(AuditEvent).where(
        AuditEvent.action == AuditAction.VERSION_UPDATE,
        AuditEvent.entity_id == version_id,
    )
    result = await db.execute(query)
    audit_entry = result.scalar_one_or_none()

    assert audit_entry is not None
    assert audit_entry.user_id == test_editor_user.id
    assert audit_entry.org_id == test_org.id
    assert audit_entry.entity_type == "system_version"


@pytest.mark.asyncio
async def test_version_cloning_flow(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """Test complete version cloning flow: create source, clone, verify data copied."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create a source version
    create_response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions",
        json={
            "label": "source-v1",
            "notes": "Source version notes",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_response.status_code == 201
    source_version = create_response.json()
    source_id = source_version["id"]

    # Clone the version
    clone_response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions/{source_id}/clone",
        json={
            "label": "cloned-v1",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert clone_response.status_code == 201
    cloned_version = clone_response.json()

    # Verify cloned version
    assert cloned_version["id"] != source_id  # New ID
    assert cloned_version["label"] == "cloned-v1"  # New label
    assert cloned_version["status"] == "draft"  # Always draft
    assert cloned_version["notes"] == "Source version notes"  # Notes copied
    assert cloned_version["ai_system_id"] == source_version["ai_system_id"]
    assert cloned_version["created_by"]["id"] == str(test_editor_user.id)

    # Verify both versions exist in the list
    list_response = await client.get(
        f"/api/systems/{test_ai_system.id}/versions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_response.status_code == 200
    versions_data = list_response.json()
    version_ids = [v["id"] for v in versions_data["items"]]
    assert source_id in version_ids
    assert cloned_version["id"] in version_ids


@pytest.mark.asyncio
async def test_version_deletion_by_admin(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_admin_user: User,
    test_ai_system: AISystem,
):
    """Test that admin can delete a version."""
    from tests.conftest import create_version

    token = create_access_token({"sub": str(test_admin_user.id)})

    # Create a version
    version = await create_version(
        db=db,
        ai_system_id=test_ai_system.id,
        label="delete-test",
        created_by=test_admin_user.id,
    )
    await db.commit()
    version_id = version.id

    # Delete the version
    delete_response = await client.delete(
        f"/api/systems/{test_ai_system.id}/versions/{version_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert delete_response.status_code == 204

    # Verify version is deleted (GET should return 404)
    get_response = await client.get(
        f"/api/systems/{test_ai_system.id}/versions/{version_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_version_deletion_rejected_for_editor(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """Test that editor cannot delete a version (admin only)."""
    from tests.conftest import create_version

    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create a version
    version = await create_version(
        db=db,
        ai_system_id=test_ai_system.id,
        label="delete-forbidden",
        created_by=test_editor_user.id,
    )
    await db.commit()

    # Try to delete as editor
    delete_response = await client.delete(
        f"/api/systems/{test_ai_system.id}/versions/{version.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert delete_response.status_code == 403


@pytest.mark.asyncio
async def test_version_deletion_rejected_for_immutable_version(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_admin_user: User,
    test_ai_system: AISystem,
):
    """Test that immutable versions cannot be deleted.

    NOTE: For Phase 8, since exports table doesn't exist yet,
    approved versions are still mutable. This test is a placeholder
    for when exports are implemented in Module E.
    """
    token = create_access_token({"sub": str(test_admin_user.id)})

    # Create and approve a version
    create_response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions",
        json={
            "label": "immutable-test",
            "notes": "Will be approved",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_response.status_code == 201
    version_id = create_response.json()["id"]

    # Transition to review
    await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/{version_id}/status",
        json={"status": "review"},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Approve the version
    await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/{version_id}/status",
        json={"status": "approved"},
        headers={"Authorization": f"Bearer {token}"},
    )

    # For now, this should succeed since exports don't exist
    # When exports are implemented, this should return 409
    delete_response = await client.delete(
        f"/api/systems/{test_ai_system.id}/versions/{version_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    # Currently allows deletion (no exports)
    # TODO: Change to assert 409 when exports table exists
    assert delete_response.status_code == 204
