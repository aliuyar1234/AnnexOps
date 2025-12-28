"""Contract tests for authentication endpoints.

These tests validate that the API responses match the OpenAPI contract
defined in specs/001-org-auth/contracts/openapi.yaml
"""
import pytest
from httpx import AsyncClient

from src.models.organization import Organization
from src.models.user import User


@pytest.mark.asyncio
class TestLoginContract:
    """Contract tests for POST /auth/login endpoint."""

    async def test_login_success_response_schema(
        self,
        client: AsyncClient,
        test_org: Organization,
        test_admin_user: User
    ):
        """Test successful login returns correct response schema."""
        response = await client.post(
            "/api/auth/login",
            json={
                "email": "admin@test.com",
                "password": "TestPass123!"
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Validate TokenResponse schema
        assert "access_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"
        assert isinstance(data["access_token"], str)
        assert len(data["access_token"]) > 0

        # Validate refresh token cookie is set
        assert "refresh_token" in response.cookies
        cookie = response.cookies["refresh_token"]
        assert cookie is not None
        assert len(cookie) > 0

    async def test_login_invalid_credentials_response(
        self,
        client: AsyncClient,
        test_admin_user: User
    ):
        """Test login with invalid credentials returns 401."""
        response = await client.post(
            "/api/auth/login",
            json={
                "email": "admin@test.com",
                "password": "WrongPassword123!"
            }
        )

        assert response.status_code == 401
        data = response.json()

        # Validate ErrorResponse schema
        assert "detail" in data
        assert isinstance(data["detail"], str)

    async def test_login_nonexistent_user_response(
        self,
        client: AsyncClient
    ):
        """Test login with non-existent user returns 401."""
        response = await client.post(
            "/api/auth/login",
            json={
                "email": "nonexistent@test.com",
                "password": "TestPass123!"
            }
        )

        assert response.status_code == 401
        data = response.json()
        assert "detail" in data

    async def test_login_locked_account_response(
        self,
        client: AsyncClient,
        test_admin_user: User
    ):
        """Test login with locked account returns 423."""
        # Lock the account by making 5 failed attempts
        for _ in range(5):
            await client.post(
                "/api/auth/login",
                json={
                    "email": "admin@test.com",
                    "password": "WrongPassword"
                }
            )

        # Attempt login with correct password (should be locked)
        response = await client.post(
            "/api/auth/login",
            json={
                "email": "admin@test.com",
                "password": "TestPass123!"
            }
        )

        assert response.status_code == 423
        data = response.json()
        assert "detail" in data
        assert "locked" in data["detail"].lower()

    async def test_login_request_validation(
        self,
        client: AsyncClient
    ):
        """Test login request validation."""
        # Missing password
        response = await client.post(
            "/api/auth/login",
            json={"email": "test@test.com"}
        )
        assert response.status_code == 422

        # Missing email
        response = await client.post(
            "/api/auth/login",
            json={"password": "TestPass123!"}
        )
        assert response.status_code == 422

        # Invalid email format
        response = await client.post(
            "/api/auth/login",
            json={"email": "not-an-email", "password": "TestPass123!"}
        )
        assert response.status_code == 422


@pytest.mark.asyncio
class TestRefreshContract:
    """Contract tests for POST /auth/refresh endpoint."""

    async def test_refresh_success_response_schema(
        self,
        client: AsyncClient,
        test_admin_user: User
    ):
        """Test successful token refresh returns correct response schema."""
        # First login to get refresh token
        login_response = await client.post(
            "/api/auth/login",
            json={
                "email": "admin@test.com",
                "password": "TestPass123!"
            }
        )
        assert login_response.status_code == 200

        # Extract refresh token from cookies
        refresh_token = login_response.cookies.get("refresh_token")
        assert refresh_token is not None

        # Refresh token
        client.cookies.set("refresh_token", refresh_token)
        response = await client.post("/api/auth/refresh")

        assert response.status_code == 200
        data = response.json()

        # Validate TokenResponse schema
        assert "access_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"
        assert isinstance(data["access_token"], str)
        assert len(data["access_token"]) > 0

    async def test_refresh_invalid_token_response(
        self,
        client: AsyncClient
    ):
        """Test refresh with invalid token returns 401."""
        client.cookies.set("refresh_token", "invalid_token")
        response = await client.post("/api/auth/refresh")

        assert response.status_code == 401
        data = response.json()
        assert "detail" in data

    async def test_refresh_missing_token_response(
        self,
        client: AsyncClient
    ):
        """Test refresh without token returns 401."""
        response = await client.post("/api/auth/refresh")

        assert response.status_code == 401
        data = response.json()
        assert "detail" in data


@pytest.mark.asyncio
class TestLogoutContract:
    """Contract tests for POST /auth/logout endpoint."""

    async def test_logout_success_response(
        self,
        client: AsyncClient,
        test_admin_user: User
    ):
        """Test successful logout response."""
        # First login
        login_response = await client.post(
            "/api/auth/login",
            json={
                "email": "admin@test.com",
                "password": "TestPass123!"
            }
        )
        access_token = login_response.json()["access_token"]

        # Logout
        response = await client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "message" in data

        # Verify refresh token cookie is cleared
        if "refresh_token" in response.cookies:
            assert response.cookies["refresh_token"] == ""

    async def test_logout_unauthorized_response(
        self,
        client: AsyncClient
    ):
        """Test logout without authentication returns 401."""
        response = await client.post("/api/auth/logout")
        assert response.status_code == 401 or response.status_code == 403


@pytest.mark.asyncio
class TestCurrentUserContract:
    """Contract tests for GET /me endpoint."""

    async def test_get_current_user_success_response_schema(
        self,
        client: AsyncClient,
        test_admin_user: User
    ):
        """Test GET /me returns correct UserResponse schema."""
        # First login
        login_response = await client.post(
            "/api/auth/login",
            json={
                "email": "admin@test.com",
                "password": "TestPass123!"
            }
        )
        access_token = login_response.json()["access_token"]

        # Get current user
        response = await client.get(
            "/api/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )

        assert response.status_code == 200
        data = response.json()

        # Validate UserResponse schema
        assert "id" in data
        assert "email" in data
        assert "role" in data
        assert "is_active" in data
        assert "created_at" in data

        # Validate data types and values
        assert data["email"] == "admin@test.com"
        assert data["role"] == "admin"
        assert data["is_active"] is True

    async def test_get_current_user_unauthorized_response(
        self,
        client: AsyncClient
    ):
        """Test GET /me without authentication returns 401."""
        response = await client.get("/api/me")
        assert response.status_code == 401 or response.status_code == 403

    async def test_get_current_user_invalid_token_response(
        self,
        client: AsyncClient
    ):
        """Test GET /me with invalid token returns 401."""
        response = await client.get(
            "/api/me",
            headers={"Authorization": "Bearer invalid_token"}
        )
        assert response.status_code == 401
