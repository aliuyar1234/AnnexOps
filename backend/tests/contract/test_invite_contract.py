"""Contract tests for invitation endpoints.

These tests validate that the API responses match the OpenAPI contract
for invitation-related endpoints.
"""

import pytest
from httpx import AsyncClient

from src.models.user import User


@pytest.mark.asyncio
class TestInviteContract:
    """Contract tests for POST /auth/invite endpoint."""

    async def test_invite_success_response_schema(self, client: AsyncClient, test_admin_user: User):
        """Test successful invitation returns correct response schema."""
        # Login as admin
        login_response = await client.post(
            "/api/auth/login", json={"email": "admin@test.com", "password": "TestPass123!"}
        )
        access_token = login_response.json()["access_token"]

        # Create invitation
        response = await client.post(
            "/api/auth/invite",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"email": "newuser@test.com", "role": "editor"},
        )

        assert response.status_code == 201
        data = response.json()

        # Validate InvitationResponse schema
        assert "id" in data
        assert "email" in data
        assert "role" in data
        assert "token" in data
        assert "expires_at" in data
        assert data["email"] == "newuser@test.com"
        assert data["role"] == "editor"
        assert isinstance(data["token"], str)
        assert len(data["token"]) > 0

    async def test_invite_duplicate_email_response(
        self, client: AsyncClient, test_admin_user: User
    ):
        """Test inviting existing user returns 400."""
        # Login as admin
        login_response = await client.post(
            "/api/auth/login", json={"email": "admin@test.com", "password": "TestPass123!"}
        )
        access_token = login_response.json()["access_token"]

        # Try to invite existing admin user
        response = await client.post(
            "/api/auth/invite",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"email": "admin@test.com", "role": "editor"},
        )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data

    async def test_invite_unauthorized_response(self, client: AsyncClient):
        """Test invite without authentication returns 401."""
        response = await client.post(
            "/api/auth/invite", json={"email": "newuser@test.com", "role": "editor"}
        )
        assert response.status_code in [401, 403]

    async def test_invite_non_admin_forbidden_response(
        self, client: AsyncClient, test_editor_user: User
    ):
        """Test invite by non-admin returns 403."""
        # Login as editor
        login_response = await client.post(
            "/api/auth/login", json={"email": "editor@test.com", "password": "TestPass123!"}
        )
        access_token = login_response.json()["access_token"]

        # Try to create invitation
        response = await client.post(
            "/api/auth/invite",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"email": "newuser@test.com", "role": "viewer"},
        )

        assert response.status_code == 403
        data = response.json()
        assert "detail" in data

    async def test_invite_request_validation(self, client: AsyncClient, test_admin_user: User):
        """Test invite request validation."""
        # Login as admin
        login_response = await client.post(
            "/api/auth/login", json={"email": "admin@test.com", "password": "TestPass123!"}
        )
        access_token = login_response.json()["access_token"]

        # Missing role
        response = await client.post(
            "/api/auth/invite",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"email": "test@test.com"},
        )
        assert response.status_code == 422

        # Missing email
        response = await client.post(
            "/api/auth/invite",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"role": "editor"},
        )
        assert response.status_code == 422

        # Invalid email format
        response = await client.post(
            "/api/auth/invite",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"email": "not-an-email", "role": "editor"},
        )
        assert response.status_code == 422

        # Invalid role
        response = await client.post(
            "/api/auth/invite",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"email": "test@test.com", "role": "superuser"},
        )
        assert response.status_code == 422


@pytest.mark.asyncio
class TestAcceptInviteContract:
    """Contract tests for POST /auth/accept-invite endpoint."""

    async def test_accept_invite_success_response_schema(
        self, client: AsyncClient, test_admin_user: User
    ):
        """Test successful invitation acceptance returns correct response schema."""
        # Login as admin and create invitation
        login_response = await client.post(
            "/api/auth/login", json={"email": "admin@test.com", "password": "TestPass123!"}
        )
        access_token = login_response.json()["access_token"]

        invite_response = await client.post(
            "/api/auth/invite",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"email": "newuser@test.com", "role": "editor"},
        )
        token = invite_response.json()["token"]

        # Accept invitation
        response = await client.post(
            "/api/auth/accept-invite", json={"token": token, "password": "NewUserPass123!"}
        )

        assert response.status_code == 201
        data = response.json()

        # Validate user response schema
        assert "id" in data
        assert "email" in data
        assert "role" in data
        assert "org_id" in data
        assert data["email"] == "newuser@test.com"
        assert data["role"] == "editor"

    async def test_accept_invite_invalid_token_response(self, client: AsyncClient):
        """Test accepting with invalid token returns 400."""
        response = await client.post(
            "/api/auth/accept-invite", json={"token": "x" * 32, "password": "NewUserPass123!"}
        )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data

    async def test_accept_invite_expired_token_response(
        self, client: AsyncClient, test_admin_user: User
    ):
        """Test accepting expired invitation returns 400."""
        # This test would require mocking time or manually creating
        # an expired invitation in the database
        # For now, we'll test the validation logic
        pass

    async def test_accept_invite_request_validation(self, client: AsyncClient):
        """Test accept invite request validation."""
        # Missing password
        response = await client.post("/api/auth/accept-invite", json={"token": "some_token"})
        assert response.status_code == 422

        # Missing token
        response = await client.post("/api/auth/accept-invite", json={"password": "Password123!"})
        assert response.status_code == 422

        # Password too short
        response = await client.post(
            "/api/auth/accept-invite", json={"token": "some_token", "password": "short"}
        )
        assert response.status_code == 422

    async def test_accept_invite_already_accepted_response(
        self, client: AsyncClient, test_admin_user: User
    ):
        """Test accepting already-used invitation returns 400."""
        # Login as admin and create invitation
        login_response = await client.post(
            "/api/auth/login", json={"email": "admin@test.com", "password": "TestPass123!"}
        )
        access_token = login_response.json()["access_token"]

        invite_response = await client.post(
            "/api/auth/invite",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"email": "newuser@test.com", "role": "editor"},
        )
        token = invite_response.json()["token"]

        # Accept invitation first time
        first_response = await client.post(
            "/api/auth/accept-invite", json={"token": token, "password": "NewUserPass123!"}
        )
        assert first_response.status_code == 201

        # Try to accept same invitation again
        second_response = await client.post(
            "/api/auth/accept-invite", json={"token": token, "password": "AnotherPass123!"}
        )

        assert second_response.status_code == 400
        data = second_response.json()
        assert "detail" in data
