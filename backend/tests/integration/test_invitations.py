"""Integration tests for invitation flow.

Tests the complete invitation lifecycle: create, accept, and login
with proper validation, expiry, and audit logging.
"""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.audit_event import AuditEvent
from src.models.enums import AuditAction, UserRole
from src.models.invitation import Invitation
from src.models.organization import Organization
from src.models.user import User


@pytest.mark.asyncio
class TestInvitationFlow:
    """Integration tests for complete invitation flow."""

    async def test_complete_invitation_flow(
        self, client: AsyncClient, db: AsyncSession, test_org: Organization, test_admin_user: User
    ):
        """Test complete flow: create invitation, accept, login."""
        # Step 1: Admin creates invitation
        login_response = await client.post(
            "/api/auth/login", json={"email": "admin@test.com", "password": "TestPass123!"}
        )
        admin_token = login_response.json()["access_token"]

        invite_response = await client.post(
            "/api/auth/invite",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"email": "newuser@test.com", "role": "editor"},
        )

        assert invite_response.status_code == 201
        invite_data = invite_response.json()
        invitation_token = invite_data["token"]

        # Verify invitation is in database
        result = await db.execute(select(Invitation).where(Invitation.email == "newuser@test.com"))
        invitation = result.scalar_one_or_none()
        assert invitation is not None
        assert invitation.role == UserRole.EDITOR
        assert invitation.accepted_at is None
        assert invitation.expires_at > datetime.now(UTC)
        assert (invitation.expires_at - datetime.now(UTC)).days == 6  # ~7 days

        # Verify audit event for invitation creation
        result = await db.execute(
            select(AuditEvent).where(
                AuditEvent.action == AuditAction.INVITATION_CREATE,
                AuditEvent.entity_id == invitation.id,
            )
        )
        audit_event = result.scalar_one_or_none()
        assert audit_event is not None

        # Step 2: New user accepts invitation
        accept_response = await client.post(
            "/api/auth/accept-invite",
            json={"token": invitation_token, "password": "NewUserPass123!"},
        )

        assert accept_response.status_code == 201
        user_data = accept_response.json()
        assert user_data["email"] == "newuser@test.com"
        assert user_data["role"] == "editor"

        # Verify user is created
        result = await db.execute(select(User).where(User.email == "newuser@test.com"))
        new_user = result.scalar_one_or_none()
        assert new_user is not None
        assert new_user.role == UserRole.EDITOR
        assert new_user.is_active is True

        # Verify invitation is marked as accepted
        await db.refresh(invitation)
        assert invitation.accepted_at is not None

        # Verify audit event for invitation acceptance
        result = await db.execute(
            select(AuditEvent).where(
                AuditEvent.action == AuditAction.INVITATION_ACCEPT,
                AuditEvent.entity_id == invitation.id,
            )
        )
        audit_event = result.scalar_one_or_none()
        assert audit_event is not None

        # Step 3: New user can login
        new_user_login_response = await client.post(
            "/api/auth/login", json={"email": "newuser@test.com", "password": "NewUserPass123!"}
        )

        assert new_user_login_response.status_code == 200
        new_user_token = new_user_login_response.json()["access_token"]

        # Verify new user can access protected endpoints
        me_response = await client.get(
            "/api/me", headers={"Authorization": f"Bearer {new_user_token}"}
        )

        assert me_response.status_code == 200
        me_data = me_response.json()
        assert me_data["email"] == "newuser@test.com"
        assert me_data["role"] == "editor"

    async def test_duplicate_pending_invitation_prevented(
        self, client: AsyncClient, db: AsyncSession, test_admin_user: User
    ):
        """Test cannot create duplicate pending invitation for same email."""
        # Login as admin
        login_response = await client.post(
            "/api/auth/login", json={"email": "admin@test.com", "password": "TestPass123!"}
        )
        admin_token = login_response.json()["access_token"]

        # Create first invitation
        first_invite = await client.post(
            "/api/auth/invite",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"email": "duplicate@test.com", "role": "editor"},
        )
        assert first_invite.status_code == 201

        # Try to create second invitation for same email
        second_invite = await client.post(
            "/api/auth/invite",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"email": "duplicate@test.com", "role": "viewer"},
        )

        assert second_invite.status_code == 400
        assert "has already been invited" in second_invite.json()["detail"].lower()

    async def test_cannot_invite_existing_user(
        self, client: AsyncClient, db: AsyncSession, test_admin_user: User, test_editor_user: User
    ):
        """Test cannot invite user that already exists in organization."""
        # Login as admin
        login_response = await client.post(
            "/api/auth/login", json={"email": "admin@test.com", "password": "TestPass123!"}
        )
        admin_token = login_response.json()["access_token"]

        # Try to invite existing editor
        invite_response = await client.post(
            "/api/auth/invite",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"email": "editor@test.com", "role": "viewer"},
        )

        assert invite_response.status_code == 400
        assert "already exists" in invite_response.json()["detail"].lower()

    async def test_invitation_token_is_single_use(
        self, client: AsyncClient, db: AsyncSession, test_admin_user: User
    ):
        """Test invitation token can only be used once."""
        # Login as admin and create invitation
        login_response = await client.post(
            "/api/auth/login", json={"email": "admin@test.com", "password": "TestPass123!"}
        )
        admin_token = login_response.json()["access_token"]

        invite_response = await client.post(
            "/api/auth/invite",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"email": "singleuse@test.com", "role": "editor"},
        )
        token = invite_response.json()["token"]

        # Accept invitation
        first_accept = await client.post(
            "/api/auth/accept-invite", json={"token": token, "password": "FirstPass123!"}
        )
        assert first_accept.status_code == 201

        # Try to use same token again
        second_accept = await client.post(
            "/api/auth/accept-invite", json={"token": token, "password": "SecondPass123!"}
        )

        assert second_accept.status_code == 400
        assert "has already been accepted" in second_accept.json()["detail"].lower()

    async def test_invitation_expiry_check(
        self, client: AsyncClient, db: AsyncSession, test_org: Organization, test_admin_user: User
    ):
        """Test expired invitation cannot be accepted."""
        # Create expired invitation directly in database
        import hashlib
        import secrets

        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        expired_invitation = Invitation(
            org_id=test_org.id,
            email="expired@test.com",
            role=UserRole.EDITOR,
            token_hash=token_hash,
            invited_by=test_admin_user.id,
            expires_at=datetime.now(UTC) - timedelta(days=1),  # Expired 1 day ago
        )
        db.add(expired_invitation)
        await db.flush()

        # Try to accept expired invitation
        response = await client.post(
            "/api/auth/accept-invite", json={"token": token, "password": "NewUserPass123!"}
        )

        assert response.status_code == 400
        assert "expired" in response.json()["detail"].lower()

    async def test_invalid_token_rejected(self, client: AsyncClient):
        """Test invalid invitation token is rejected."""
        response = await client.post(
            "/api/auth/accept-invite",
            json={"token": "invalid_token_12345", "password": "NewUserPass123!"},
        )

        assert response.status_code in (400, 422)
        detail_text = str(response.json().get("detail", "")).lower()
        if response.status_code == 400:
            assert "invalid" in detail_text
        else:
            assert "token" in detail_text

    async def test_invitation_creates_user_with_correct_role(
        self, client: AsyncClient, db: AsyncSession, test_admin_user: User
    ):
        """Test accepted invitation creates user with assigned role."""
        # Login as admin
        login_response = await client.post(
            "/api/auth/login", json={"email": "admin@test.com", "password": "TestPass123!"}
        )
        admin_token = login_response.json()["access_token"]

        # Create invitation with viewer role
        invite_response = await client.post(
            "/api/auth/invite",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"email": "viewer@newtest.com", "role": "viewer"},
        )
        token = invite_response.json()["token"]

        # Accept invitation
        accept_response = await client.post(
            "/api/auth/accept-invite", json={"token": token, "password": "ViewerPass123!"}
        )

        assert accept_response.status_code == 201

        # Verify user has viewer role
        result = await db.execute(select(User).where(User.email == "viewer@newtest.com"))
        user = result.scalar_one_or_none()
        assert user is not None
        assert user.role == UserRole.VIEWER

    async def test_invitation_audit_logging(
        self, client: AsyncClient, db: AsyncSession, test_admin_user: User
    ):
        """Test invitation creates proper audit events."""
        # Login as admin
        login_response = await client.post(
            "/api/auth/login", json={"email": "admin@test.com", "password": "TestPass123!"}
        )
        admin_token = login_response.json()["access_token"]

        # Create invitation
        invite_response = await client.post(
            "/api/auth/invite",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"email": "audited@test.com", "role": "editor"},
        )
        token = invite_response.json()["token"]

        # Accept invitation
        await client.post(
            "/api/auth/accept-invite", json={"token": token, "password": "AuditPass123!"}
        )

        # Verify both audit events exist
        result = await db.execute(
            select(AuditEvent)
            .where(
                AuditEvent.action.in_(
                    [AuditAction.INVITATION_CREATE, AuditAction.INVITATION_ACCEPT]
                )
            )
            .order_by(AuditEvent.created_at)
        )
        audit_events = result.scalars().all()

        assert len(audit_events) >= 2
        assert any(e.action == AuditAction.INVITATION_CREATE for e in audit_events)
        assert any(e.action == AuditAction.INVITATION_ACCEPT for e in audit_events)


@pytest.mark.asyncio
class TestInvitationPermissions:
    """Integration tests for invitation permission enforcement."""

    async def test_only_admin_can_create_invitations(
        self, client: AsyncClient, test_editor_user: User, test_viewer_user: User
    ):
        """Test only admins can create invitations."""
        # Try as editor
        editor_login = await client.post(
            "/api/auth/login", json={"email": "editor@test.com", "password": "TestPass123!"}
        )
        editor_token = editor_login.json()["access_token"]

        editor_invite = await client.post(
            "/api/auth/invite",
            headers={"Authorization": f"Bearer {editor_token}"},
            json={"email": "test@test.com", "role": "viewer"},
        )
        assert editor_invite.status_code == 403

        # Try as viewer
        viewer_login = await client.post(
            "/api/auth/login", json={"email": "viewer@test.com", "password": "TestPass123!"}
        )
        viewer_token = viewer_login.json()["access_token"]

        viewer_invite = await client.post(
            "/api/auth/invite",
            headers={"Authorization": f"Bearer {viewer_token}"},
            json={"email": "test@test.com", "role": "viewer"},
        )
        assert viewer_invite.status_code == 403

    async def test_accept_invite_does_not_require_authentication(
        self, client: AsyncClient, test_admin_user: User
    ):
        """Test accepting invitation does not require being logged in."""
        # Create invitation as admin
        login_response = await client.post(
            "/api/auth/login", json={"email": "admin@test.com", "password": "TestPass123!"}
        )
        admin_token = login_response.json()["access_token"]

        invite_response = await client.post(
            "/api/auth/invite",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"email": "public@test.com", "role": "viewer"},
        )
        token = invite_response.json()["token"]

        # Accept invitation without any authentication
        accept_response = await client.post(
            "/api/auth/accept-invite", json={"token": token, "password": "PublicPass123!"}
        )

        assert accept_response.status_code == 201
