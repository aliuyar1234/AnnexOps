"""Integration tests for authentication flow.

Tests the complete authentication flow including login, logout,
token refresh, and account lockout mechanisms.
"""
import asyncio
import pytest
from datetime import datetime, timedelta, timezone
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.models.user import User
from src.models.organization import Organization
from src.models.audit_event import AuditEvent
from src.models.enums import AuditAction


@pytest.mark.asyncio
class TestLoginFlow:
    """Integration tests for login flow."""

    async def test_successful_login_flow(
        self,
        client: AsyncClient,
        db: AsyncSession,
        test_admin_user: User
    ):
        """Test complete successful login flow."""
        # Login with valid credentials
        response = await client.post(
            "/api/auth/login",
            json={
                "email": "admin@test.com",
                "password": "TestPass123!"
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Verify token is returned
        assert "access_token" in data
        assert data["token_type"] == "bearer"

        # Verify refresh token cookie is set
        assert "refresh_token" in response.cookies

        # Verify user's last_login_at is updated
        await db.refresh(test_admin_user)
        assert test_admin_user.last_login_at is not None
        assert (datetime.now(timezone.utc) - test_admin_user.last_login_at).seconds < 10

        # Verify failed login attempts are reset
        assert test_admin_user.failed_login_attempts == 0

        # Verify audit event is created
        result = await db.execute(
            select(AuditEvent).where(
                AuditEvent.action == AuditAction.USER_LOGIN,
                AuditEvent.user_id == test_admin_user.id
            )
        )
        audit_event = result.scalar_one_or_none()
        assert audit_event is not None

    async def test_login_with_invalid_password(
        self,
        client: AsyncClient,
        db: AsyncSession,
        test_admin_user: User
    ):
        """Test login with invalid password increments failure counter."""
        # Attempt login with wrong password
        response = await client.post(
            "/api/auth/login",
            json={
                "email": "admin@test.com",
                "password": "WrongPassword123!"
            }
        )

        assert response.status_code == 401

        # Verify failed login attempts are incremented
        await db.refresh(test_admin_user)
        assert test_admin_user.failed_login_attempts == 1
        assert test_admin_user.last_login_at is None

    async def test_login_with_nonexistent_user(
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
        assert "detail" in response.json()

    async def test_login_with_inactive_account(
        self,
        client: AsyncClient,
        db: AsyncSession,
        test_admin_user: User
    ):
        """Test login with inactive account is rejected."""
        # Deactivate user
        test_admin_user.is_active = False
        await db.flush()

        # Attempt login
        response = await client.post(
            "/api/auth/login",
            json={
                "email": "admin@test.com",
                "password": "TestPass123!"
            }
        )

        assert response.status_code == 403
        assert "inactive" in response.json()["detail"].lower()


@pytest.mark.asyncio
class TestAccountLockout:
    """Integration tests for account lockout mechanism."""

    async def test_account_lockout_after_5_failures(
        self,
        client: AsyncClient,
        db: AsyncSession,
        test_admin_user: User
    ):
        """Test account is locked after 5 failed login attempts."""
        # Make 5 failed login attempts
        for i in range(5):
            response = await client.post(
                "/api/auth/login",
                json={
                    "email": "admin@test.com",
                    "password": "WrongPassword"
                }
            )
            assert response.status_code == 401

        # Verify account is locked
        await db.refresh(test_admin_user)
        assert test_admin_user.failed_login_attempts == 5
        assert test_admin_user.locked_until is not None
        assert test_admin_user.locked_until > datetime.now(timezone.utc)

        # Attempt login with correct password (should be locked)
        response = await client.post(
            "/api/auth/login",
            json={
                "email": "admin@test.com",
                "password": "TestPass123!"
            }
        )

        assert response.status_code == 423
        assert "locked" in response.json()["detail"].lower()

        # Verify audit event for lockout (may have multiple if lockout logged on each attempt)
        result = await db.execute(
            select(AuditEvent).where(
                AuditEvent.action == AuditAction.USER_LOCKOUT,
                AuditEvent.user_id == test_admin_user.id
            )
        )
        audit_events = result.scalars().all()
        assert len(audit_events) >= 1

    async def test_exponential_backoff_lockout(
        self,
        client: AsyncClient,
        db: AsyncSession,
        test_admin_user: User
    ):
        """Test lockout duration increases exponentially."""
        # First lockout (5 failures)
        for _ in range(5):
            await client.post(
                "/api/auth/login",
                json={"email": "admin@test.com", "password": "WrongPass123!"}
            )

        await db.refresh(test_admin_user)
        first_lockout = test_admin_user.locked_until
        assert first_lockout is not None

        # Duration should be ~1 minute for first lockout
        lockout_duration = (first_lockout - datetime.now(timezone.utc)).total_seconds()
        assert 55 < lockout_duration < 70  # ~1 minute with some tolerance

        # Unlock account and lock again
        test_admin_user.locked_until = None
        test_admin_user.failed_login_attempts = 5  # Simulate second lockout
        await db.flush()

        # Trigger second lockout
        for _ in range(5):
            await client.post(
                "/api/auth/login",
                json={"email": "admin@test.com", "password": "WrongPass123!"}
            )

        await db.refresh(test_admin_user)
        second_lockout = test_admin_user.locked_until
        assert second_lockout is not None

        # Duration should be ~2 minutes for second lockout
        lockout_duration = (second_lockout - datetime.now(timezone.utc)).total_seconds()
        assert 115 < lockout_duration < 130  # ~2 minutes

    async def test_successful_login_resets_failure_counter(
        self,
        client: AsyncClient,
        db: AsyncSession,
        test_admin_user: User
    ):
        """Test successful login resets failed login attempts."""
        # Make 3 failed attempts
        for _ in range(3):
            await client.post(
                "/api/auth/login",
                json={"email": "admin@test.com", "password": "WrongPass123!"}
            )

        await db.refresh(test_admin_user)
        assert test_admin_user.failed_login_attempts == 3

        # Successful login
        response = await client.post(
            "/api/auth/login",
            json={
                "email": "admin@test.com",
                "password": "TestPass123!"
            }
        )
        assert response.status_code == 200

        # Verify counter is reset
        await db.refresh(test_admin_user)
        assert test_admin_user.failed_login_attempts == 0

    async def test_lockout_expires_after_duration(
        self,
        client: AsyncClient,
        db: AsyncSession,
        test_admin_user: User
    ):
        """Test account is unlocked after lockout duration expires."""
        # Set locked_until to past time
        test_admin_user.locked_until = datetime.now(timezone.utc) - timedelta(minutes=1)
        test_admin_user.failed_login_attempts = 5
        await db.flush()

        # Attempt login (should succeed as lockout expired)
        response = await client.post(
            "/api/auth/login",
            json={
                "email": "admin@test.com",
                "password": "TestPass123!"
            }
        )

        assert response.status_code == 200


@pytest.mark.asyncio
class TestTokenRefresh:
    """Integration tests for token refresh flow."""

    async def test_refresh_token_flow(
        self,
        client: AsyncClient,
        test_admin_user: User
    ):
        """Test complete token refresh flow."""
        # Login to get refresh token
        login_response = await client.post(
            "/api/auth/login",
            json={
                "email": "admin@test.com",
                "password": "TestPass123!"
            }
        )
        assert login_response.status_code == 200
        original_access_token = login_response.json()["access_token"]
        refresh_token = login_response.cookies.get("refresh_token")

        # Wait 1 second to ensure different token expiration time
        await asyncio.sleep(1)

        # Refresh token
        refresh_response = await client.post(
            "/api/auth/refresh",
            cookies={"refresh_token": refresh_token}
        )

        assert refresh_response.status_code == 200
        new_access_token = refresh_response.json()["access_token"]

        # Verify new token is different
        assert new_access_token != original_access_token

        # Verify new token works
        me_response = await client.get(
            "/api/me",
            headers={"Authorization": f"Bearer {new_access_token}"}
        )
        assert me_response.status_code == 200

    async def test_refresh_with_invalid_token(
        self,
        client: AsyncClient
    ):
        """Test refresh with invalid token is rejected."""
        response = await client.post(
            "/api/auth/refresh",
            cookies={"refresh_token": "invalid_token"}
        )
        assert response.status_code == 401


@pytest.mark.asyncio
class TestLogoutFlow:
    """Integration tests for logout flow."""

    async def test_logout_clears_refresh_token(
        self,
        client: AsyncClient,
        db: AsyncSession,
        test_admin_user: User
    ):
        """Test logout clears refresh token cookie."""
        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={
                "email": "admin@test.com",
                "password": "TestPass123!"
            }
        )
        access_token = login_response.json()["access_token"]

        # Logout
        logout_response = await client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"}
        )

        assert logout_response.status_code == 200

        # Verify refresh token cookie is cleared
        if "refresh_token" in logout_response.cookies:
            assert logout_response.cookies["refresh_token"] == ""

        # Verify audit event for logout
        result = await db.execute(
            select(AuditEvent).where(
                AuditEvent.action == AuditAction.USER_LOGOUT,
                AuditEvent.user_id == test_admin_user.id
            )
        )
        audit_event = result.scalar_one_or_none()
        assert audit_event is not None


@pytest.mark.asyncio
class TestCurrentUser:
    """Integration tests for current user endpoint."""

    async def test_get_current_user_with_valid_token(
        self,
        client: AsyncClient,
        test_admin_user: User
    ):
        """Test GET /me returns current user info."""
        # Login
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
        assert data["email"] == "admin@test.com"
        assert data["role"] == "admin"
        assert data["is_active"] is True

    async def test_get_current_user_with_expired_token(
        self,
        client: AsyncClient
    ):
        """Test GET /me with expired token returns 401."""
        # Use an invalid/expired token
        response = await client.get(
            "/api/me",
            headers={"Authorization": "Bearer expired_token"}
        )
        assert response.status_code == 401

    async def test_get_current_user_without_token(
        self,
        client: AsyncClient
    ):
        """Test GET /me without token returns 401."""
        response = await client.get("/api/me")
        # Can be 401 or 403 depending on implementation
        assert response.status_code in [401, 403]
