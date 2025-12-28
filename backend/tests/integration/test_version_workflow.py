"""Integration tests for version status workflow."""

from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import create_access_token
from src.models.ai_system import AISystem
from src.models.organization import Organization
from src.models.user import User


@pytest.mark.asyncio
async def test_draft_to_review_to_approved_flow(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_admin_user: User,
    test_ai_system: AISystem,
):
    """Test complete workflow: draft -> review -> approved."""
    token = create_access_token({"sub": str(test_admin_user.id)})

    # Create a version (starts as draft)
    create_response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions",
        json={"label": "workflow-test", "notes": "Testing workflow"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_response.status_code == 201
    version_id = create_response.json()["id"]
    assert create_response.json()["status"] == "draft"

    # Transition to review
    review_response = await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/{version_id}/status",
        json={"status": "review", "comment": "Ready for review"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert review_response.status_code == 200
    assert review_response.json()["status"] == "review"

    # Transition to approved
    approved_response = await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/{version_id}/status",
        json={"status": "approved", "comment": "Approved for production"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert approved_response.status_code == 200
    data = approved_response.json()
    assert data["status"] == "approved"


@pytest.mark.asyncio
async def test_review_can_go_back_to_draft(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """Test that review status can transition back to draft."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create a version and transition to review
    create_response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions",
        json={"label": "back-to-draft", "notes": "Testing backwards transition"},
        headers={"Authorization": f"Bearer {token}"},
    )
    version_id = create_response.json()["id"]

    # Move to review
    await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/{version_id}/status",
        json={"status": "review"},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Move back to draft
    response = await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/{version_id}/status",
        json={"status": "draft", "comment": "Needs more work"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "draft"


@pytest.mark.asyncio
async def test_invalid_transition_rejected(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """Test that invalid status transitions are rejected with 409."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create a version (draft)
    create_response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions",
        json={"label": "invalid-transition", "notes": "Testing invalid transitions"},
        headers={"Authorization": f"Bearer {token}"},
    )
    version_id = create_response.json()["id"]

    # Try invalid transition: draft -> approved (must go through review)
    response = await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/{version_id}/status",
        json={"status": "approved"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409
    assert (
        "invalid" in response.json()["detail"].lower()
        or "transition" in response.json()["detail"].lower()
    )


@pytest.mark.asyncio
async def test_approved_is_terminal_state(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_admin_user: User,
    test_ai_system: AISystem,
):
    """Test that approved versions cannot transition to any other state."""
    token = create_access_token({"sub": str(test_admin_user.id)})

    # Create version and move to approved
    create_response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions",
        json={"label": "terminal-test", "notes": "Testing terminal state"},
        headers={"Authorization": f"Bearer {token}"},
    )
    version_id = create_response.json()["id"]

    # Move to review
    await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/{version_id}/status",
        json={"status": "review"},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Move to approved
    await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/{version_id}/status",
        json={"status": "approved"},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Try to move back to draft - should fail
    response1 = await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/{version_id}/status",
        json={"status": "draft"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response1.status_code == 409

    # Try to move back to review - should fail
    response2 = await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/{version_id}/status",
        json={"status": "review"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response2.status_code == 409


@pytest.mark.asyncio
async def test_admin_only_approve(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_admin_user: User,
    test_ai_system: AISystem,
):
    """Test that only admin can approve versions, editors cannot."""
    editor_token = create_access_token({"sub": str(test_editor_user.id)})
    admin_token = create_access_token({"sub": str(test_admin_user.id)})

    # Editor creates version and moves to review
    create_response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions",
        json={"label": "admin-only", "notes": "Testing admin approval"},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    version_id = create_response.json()["id"]

    await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/{version_id}/status",
        json={"status": "review"},
        headers={"Authorization": f"Bearer {editor_token}"},
    )

    # Editor tries to approve - should fail with 403
    editor_approve_response = await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/{version_id}/status",
        json={"status": "approved"},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert editor_approve_response.status_code == 403

    # Admin approves - should succeed
    admin_approve_response = await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/{version_id}/status",
        json={"status": "approved", "comment": "Admin approval"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert admin_approve_response.status_code == 200
    assert admin_approve_response.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_approved_by_and_approved_at_set_on_approval(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_admin_user: User,
    test_ai_system: AISystem,
):
    """Test that approved_by and approved_at are set when version is approved."""
    token = create_access_token({"sub": str(test_admin_user.id)})

    # Create version
    create_response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions",
        json={"label": "approval-metadata", "notes": "Testing approval metadata"},
        headers={"Authorization": f"Bearer {token}"},
    )
    version_id = create_response.json()["id"]

    # Move to review
    await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/{version_id}/status",
        json={"status": "review"},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Approve
    await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/{version_id}/status",
        json={"status": "approved"},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Verify approved_by and approved_at are set by querying the version
    # We'll need to add these fields to the response schema
    from sqlalchemy import select

    from src.models.system_version import SystemVersion

    query = select(SystemVersion).where(SystemVersion.id == version_id)
    result = await db.execute(query)
    version = result.scalar_one()

    assert version.approved_by == test_admin_user.id
    assert version.approved_at is not None
    assert version.approved_at == date.today()


@pytest.mark.asyncio
async def test_audit_log_created_for_status_change(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """Test that audit log entries are created for status changes."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create version
    create_response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions",
        json={"label": "audit-test", "notes": "Testing audit logging"},
        headers={"Authorization": f"Bearer {token}"},
    )
    version_id = create_response.json()["id"]

    # Change status
    await client.patch(
        f"/api/systems/{test_ai_system.id}/versions/{version_id}/status",
        json={"status": "review", "comment": "Ready for review"},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Verify audit log entry exists
    from sqlalchemy import select

    from src.models.audit_event import AuditEvent
    from src.models.enums import AuditAction

    query = (
        select(AuditEvent)
        .where(AuditEvent.action == AuditAction.VERSION_STATUS_CHANGE)
        .where(AuditEvent.entity_id == version_id)
    )
    result = await db.execute(query)
    audit_entry = result.scalar_one_or_none()

    assert audit_entry is not None
    assert audit_entry.user_id == test_editor_user.id
    assert audit_entry.org_id == test_org.id
    assert "comment" in audit_entry.diff_json
    assert audit_entry.diff_json["comment"] == "Ready for review"
