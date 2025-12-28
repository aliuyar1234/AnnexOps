"""Integration tests for Role-Based Access Control (RBAC)."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import create_access_token
from src.models.enums import UserRole
from src.models.organization import Organization
from src.models.user import User


@pytest.mark.asyncio
class TestRBACEnforcement:
    """Test RBAC enforcement for user management endpoints."""

    async def test_viewer_cannot_update_user(
        self,
        client: AsyncClient,
        db: AsyncSession,
        test_org: Organization,
        test_viewer_user: User,
        test_editor_user: User,
    ):
        """Test that viewer role cannot update users.

        Viewer should receive 403 when attempting to update any user.
        """
        # Login as viewer
        viewer_token = create_access_token({"sub": str(test_viewer_user.id)})

        # Attempt to update editor user
        response = await client.patch(
            f"/api/users/{test_editor_user.id}",
            headers={"Authorization": f"Bearer {viewer_token}"},
            json={"is_active": False}
        )

        # Should be forbidden
        assert response.status_code == 403
        assert "Only admins can change user roles or active status" in response.json()["detail"]

    async def test_viewer_cannot_delete_user(
        self,
        client: AsyncClient,
        db: AsyncSession,
        test_org: Organization,
        test_viewer_user: User,
        test_editor_user: User,
    ):
        """Test that viewer role cannot delete users.

        Viewer should receive 403 when attempting to delete any user.
        """
        # Login as viewer
        viewer_token = create_access_token({"sub": str(test_viewer_user.id)})

        # Attempt to delete editor user
        response = await client.delete(
            f"/api/users/{test_editor_user.id}",
            headers={"Authorization": f"Bearer {viewer_token}"}
        )

        # Should be forbidden
        assert response.status_code == 403
        assert "Insufficient permissions" in response.json()["detail"]

    async def test_editor_cannot_change_roles(
        self,
        client: AsyncClient,
        db: AsyncSession,
        test_org: Organization,
        test_editor_user: User,
        test_viewer_user: User,
    ):
        """Test that editor role cannot change user roles.

        Editor can update non-role fields but role changes require admin.
        """
        # Login as editor
        editor_token = create_access_token({"sub": str(test_editor_user.id)})

        # Attempt to change viewer's role
        response = await client.patch(
            f"/api/users/{test_viewer_user.id}",
            headers={"Authorization": f"Bearer {editor_token}"},
            json={"role": "admin"}
        )

        # Should be forbidden (only admin can change roles)
        assert response.status_code == 403

    async def test_editor_cannot_delete_user(
        self,
        client: AsyncClient,
        db: AsyncSession,
        test_org: Organization,
        test_editor_user: User,
        test_viewer_user: User,
    ):
        """Test that editor role cannot delete users.

        Delete is admin-only operation.
        """
        # Login as editor
        editor_token = create_access_token({"sub": str(test_editor_user.id)})

        # Attempt to delete viewer
        response = await client.delete(
            f"/api/users/{test_viewer_user.id}",
            headers={"Authorization": f"Bearer {editor_token}"}
        )

        # Should be forbidden
        assert response.status_code == 403

    async def test_viewer_can_list_users(
        self,
        client: AsyncClient,
        db: AsyncSession,
        test_org: Organization,
        test_viewer_user: User,
    ):
        """Test that viewer can list users (read permission).

        All authenticated users should be able to list users in their org.
        """
        # Login as viewer
        viewer_token = create_access_token({"sub": str(test_viewer_user.id)})

        # List users
        response = await client.get(
            "/api/users",
            headers={"Authorization": f"Bearer {viewer_token}"}
        )

        # Should succeed
        assert response.status_code == 200
        users = response.json()
        assert len(users) > 0

    async def test_viewer_can_get_user_details(
        self,
        client: AsyncClient,
        db: AsyncSession,
        test_org: Organization,
        test_viewer_user: User,
        test_editor_user: User,
    ):
        """Test that viewer can get user details (read permission).

        All authenticated users should be able to view user details.
        """
        # Login as viewer
        viewer_token = create_access_token({"sub": str(test_viewer_user.id)})

        # Get editor details
        response = await client.get(
            f"/api/users/{test_editor_user.id}",
            headers={"Authorization": f"Bearer {viewer_token}"}
        )

        # Should succeed
        assert response.status_code == 200
        user = response.json()
        assert user["email"] == test_editor_user.email


@pytest.mark.asyncio
class TestRoleHierarchy:
    """Test that role hierarchy works correctly (admin > editor > reviewer > viewer)."""

    async def test_admin_can_list_users(
        self,
        client: AsyncClient,
        db: AsyncSession,
        test_org: Organization,
        test_admin_user: User,
    ):
        """Test that admin can list users."""
        admin_token = create_access_token({"sub": str(test_admin_user.id)})

        response = await client.get(
            "/api/users",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200

    async def test_admin_can_get_user(
        self,
        client: AsyncClient,
        db: AsyncSession,
        test_org: Organization,
        test_admin_user: User,
        test_viewer_user: User,
    ):
        """Test that admin can get user details."""
        admin_token = create_access_token({"sub": str(test_admin_user.id)})

        response = await client.get(
            f"/api/users/{test_viewer_user.id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200

    async def test_admin_can_update_user(
        self,
        client: AsyncClient,
        db: AsyncSession,
        test_org: Organization,
        test_admin_user: User,
        test_viewer_user: User,
    ):
        """Test that admin can update users including role changes."""
        admin_token = create_access_token({"sub": str(test_admin_user.id)})

        # Update viewer's role to editor
        response = await client.patch(
            f"/api/users/{test_viewer_user.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"role": "editor"}
        )

        assert response.status_code == 200
        user = response.json()
        assert user["role"] == "editor"

    async def test_admin_can_deactivate_user(
        self,
        client: AsyncClient,
        db: AsyncSession,
        test_org: Organization,
        test_admin_user: User,
        test_editor_user: User,
    ):
        """Test that admin can deactivate users."""
        admin_token = create_access_token({"sub": str(test_admin_user.id)})

        # Deactivate editor
        response = await client.patch(
            f"/api/users/{test_editor_user.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"is_active": False}
        )

        assert response.status_code == 200
        user = response.json()
        assert user["is_active"] is False

    async def test_admin_can_delete_user(
        self,
        client: AsyncClient,
        db: AsyncSession,
        test_org: Organization,
        test_admin_user: User,
        test_viewer_user: User,
    ):
        """Test that admin can delete users."""
        admin_token = create_access_token({"sub": str(test_admin_user.id)})

        # Delete viewer
        response = await client.delete(
            f"/api/users/{test_viewer_user.id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 204

    async def test_filter_users_by_role(
        self,
        client: AsyncClient,
        db: AsyncSession,
        test_org: Organization,
        test_admin_user: User,
        test_editor_user: User,
        test_viewer_user: User,
    ):
        """Test filtering users by role."""
        admin_token = create_access_token({"sub": str(test_admin_user.id)})

        # Filter for editors only
        response = await client.get(
            "/api/users?role=editor",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        users = response.json()
        # Should only return editor
        assert len(users) == 1
        assert users[0]["role"] == "editor"


@pytest.mark.asyncio
class TestLastAdminProtection:
    """Test protection against deleting or demoting the last admin (FR-A09)."""

    async def test_cannot_delete_last_admin(
        self,
        client: AsyncClient,
        db: AsyncSession,
        test_org: Organization,
        test_admin_user: User,
    ):
        """Test that the last admin in an org cannot be deleted.

        Should return 400 with appropriate error message.
        """
        admin_token = create_access_token({"sub": str(test_admin_user.id)})

        # Attempt to delete the only admin
        response = await client.delete(
            f"/api/users/{test_admin_user.id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        # Should be rejected
        assert response.status_code == 400
        assert "last admin" in response.json()["detail"].lower()

    async def test_cannot_demote_last_admin(
        self,
        client: AsyncClient,
        db: AsyncSession,
        test_org: Organization,
        test_admin_user: User,
    ):
        """Test that the last admin cannot be demoted to non-admin role.

        Should return 400 with appropriate error message.
        """
        admin_token = create_access_token({"sub": str(test_admin_user.id)})

        # Attempt to demote the only admin
        response = await client.patch(
            f"/api/users/{test_admin_user.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"role": "editor"}
        )

        # Should be rejected
        assert response.status_code == 400
        assert "last admin" in response.json()["detail"].lower()

    async def test_can_delete_admin_when_multiple_exist(
        self,
        client: AsyncClient,
        db: AsyncSession,
        test_org: Organization,
        test_admin_user: User,
    ):
        """Test that an admin can be deleted when there are other admins.

        Should succeed when org has multiple admins.
        """
        # Create a second admin
        from tests.conftest import create_user

        second_admin = await create_user(
            db,
            test_org.id,
            "admin2@test.com",
            role=UserRole.ADMIN
        )
        await db.commit()

        admin_token = create_access_token({"sub": str(test_admin_user.id)})

        # Delete the second admin (first admin still exists)
        response = await client.delete(
            f"/api/users/{second_admin.id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        # Should succeed
        assert response.status_code == 204

    async def test_can_demote_admin_when_multiple_exist(
        self,
        client: AsyncClient,
        db: AsyncSession,
        test_org: Organization,
        test_admin_user: User,
    ):
        """Test that an admin can be demoted when there are other admins.

        Should succeed when org has multiple admins.
        """
        # Create a second admin
        from tests.conftest import create_user

        second_admin = await create_user(
            db,
            test_org.id,
            "admin2@test.com",
            role=UserRole.ADMIN
        )
        await db.commit()

        admin_token = create_access_token({"sub": str(test_admin_user.id)})

        # Demote the second admin (first admin still exists)
        response = await client.patch(
            f"/api/users/{second_admin.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"role": "editor"}
        )

        # Should succeed
        assert response.status_code == 200
        user = response.json()
        assert user["role"] == "editor"

    async def test_can_deactivate_last_admin(
        self,
        client: AsyncClient,
        db: AsyncSession,
        test_org: Organization,
        test_admin_user: User,
    ):
        """Test that the last admin can be deactivated (soft lock, not delete).

        Deactivation is allowed, only hard delete is prevented.
        """
        admin_token = create_access_token({"sub": str(test_admin_user.id)})

        # Deactivate the only admin
        response = await client.patch(
            f"/api/users/{test_admin_user.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"is_active": False}
        )

        # Should succeed (deactivation is allowed, deletion is not)
        assert response.status_code == 200
        user = response.json()
        assert user["is_active"] is False
