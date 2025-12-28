"""Contract tests for organization endpoints.

These tests validate the API contract defined in specs/001-org-auth/contracts/openapi.yaml
for organization endpoints.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import create_access_token
from src.models.enums import UserRole
from src.models.organization import Organization
from src.models.user import User


@pytest.mark.asyncio
async def test_create_organization_bootstrap_success(
    client: AsyncClient,
    db: AsyncSession,
    bootstrap_headers: dict[str, str],
):
    """Test POST /organizations creates organization with admin user (bootstrap).

    Contract: POST /organizations
    - Request: { name, admin_email, admin_password }
    - Response: 201 { id, name, created_at }
    - Condition: Only works when NO organization exists
    """
    # Arrange
    payload = {
        "name": "Acme Corporation",
        "admin_email": "admin@acme.com",
        "admin_password": "SecurePass123!"
    }

    # Act
    response = await client.post("/api/organizations", json=payload, headers=bootstrap_headers)

    # Assert
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["name"] == "Acme Corporation"
    assert "created_at" in data

    # Verify organization exists in database
    from sqlalchemy import select
    result = await db.execute(
        select(Organization).where(Organization.name == "Acme Corporation")
    )
    org = result.scalar_one_or_none()
    assert org is not None

    # Verify admin user was created
    result = await db.execute(
        select(User).where(User.org_id == org.id, User.email == "admin@acme.com")
    )
    admin = result.scalar_one_or_none()
    assert admin is not None
    assert admin.role == UserRole.ADMIN
    assert admin.is_active is True


@pytest.mark.asyncio
async def test_create_organization_already_exists_fails(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    bootstrap_headers: dict[str, str],
):
    """Test POST /organizations fails when organization already exists.

    Contract: POST /organizations
    - Response: 409 Conflict if organization already exists (single-tenant MVP)
    """
    # Arrange
    payload = {
        "name": "Another Corporation",
        "admin_email": "admin@another.com",
        "admin_password": "SecurePass123!"
    }

    # Act
    response = await client.post("/api/organizations", json=payload, headers=bootstrap_headers)

    # Assert
    assert response.status_code == 409
    error = response.json()
    assert "detail" in error


@pytest.mark.asyncio
async def test_create_organization_validation_fails(
    client: AsyncClient,
    bootstrap_headers: dict[str, str],
):
    """Test POST /organizations fails with invalid data.

    Contract: POST /organizations
    - Response: 400 for validation errors
    """
    # Test missing required fields
    response = await client.post("/api/organizations", json={}, headers=bootstrap_headers)
    assert response.status_code == 422  # FastAPI validation error

    # Test invalid email
    payload = {
        "name": "Test Corp",
        "admin_email": "not-an-email",
        "admin_password": "SecurePass123!"
    }
    response = await client.post("/api/organizations", json=payload, headers=bootstrap_headers)
    assert response.status_code == 422

    # Test short password
    payload = {
        "name": "Test Corp",
        "admin_email": "admin@test.com",
        "admin_password": "short"
    }
    response = await client.post("/api/organizations", json=payload, headers=bootstrap_headers)
    assert response.status_code == 422

    # Test empty name
    payload = {
        "name": "",
        "admin_email": "admin@test.com",
        "admin_password": "SecurePass123!"
    }
    response = await client.post("/api/organizations", json=payload, headers=bootstrap_headers)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_organization_success(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_admin_user: User
):
    """Test GET /organizations/{org_id} returns organization details.

    Contract: GET /organizations/{org_id}
    - Response: 200 { id, name, created_at, updated_at }
    - Requires: Authentication
    """
    # Arrange
    access_token = create_access_token({"sub": str(test_admin_user.id)})
    headers = {"Authorization": f"Bearer {access_token}"}

    # Act
    response = await client.get(f"/api/organizations/{test_org.id}", headers=headers)

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(test_org.id)
    assert data["name"] == test_org.name
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_get_organization_unauthorized(client: AsyncClient, test_org: Organization):
    """Test GET /organizations/{org_id} fails without authentication.

    Contract: GET /organizations/{org_id}
    - Response: 401 if not authenticated
    """
    # Act
    response = await client.get(f"/api/organizations/{test_org.id}")

    # Assert
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_organization_not_found(
    client: AsyncClient,
    test_admin_user: User
):
    """Test GET /organizations/{org_id} returns 404 for non-existent org.

    Contract: GET /organizations/{org_id}
    - Response: 404 if organization not found
    """
    # Arrange
    access_token = create_access_token({"sub": str(test_admin_user.id)})
    headers = {"Authorization": f"Bearer {access_token}"}
    fake_id = "00000000-0000-0000-0000-000000000000"

    # Act
    response = await client.get(f"/api/organizations/{fake_id}", headers=headers)

    # Assert
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_organization_success(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_admin_user: User
):
    """Test PATCH /organizations/{org_id} updates organization name.

    Contract: PATCH /organizations/{org_id}
    - Request: { name? }
    - Response: 200 { id, name, created_at, updated_at }
    - Requires: Admin role
    """
    # Arrange
    access_token = create_access_token({"sub": str(test_admin_user.id)})
    headers = {"Authorization": f"Bearer {access_token}"}
    payload = {"name": "Updated Organization Name"}

    # Act
    response = await client.patch(
        f"/api/organizations/{test_org.id}",
        headers=headers,
        json=payload
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Organization Name"
    assert data["id"] == str(test_org.id)

    # Verify in database
    await db.refresh(test_org)
    assert test_org.name == "Updated Organization Name"


@pytest.mark.asyncio
async def test_update_organization_non_admin_fails(
    client: AsyncClient,
    test_org: Organization,
    test_viewer_user: User
):
    """Test PATCH /organizations/{org_id} fails for non-admin users.

    Contract: PATCH /organizations/{org_id}
    - Response: 403 if not admin
    """
    # Arrange
    access_token = create_access_token({"sub": str(test_viewer_user.id)})
    headers = {"Authorization": f"Bearer {access_token}"}
    payload = {"name": "Hacker Attempt"}

    # Act
    response = await client.patch(
        f"/api/organizations/{test_org.id}",
        headers=headers,
        json=payload
    )

    # Assert
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_update_organization_unauthorized(
    client: AsyncClient,
    test_org: Organization
):
    """Test PATCH /organizations/{org_id} fails without authentication.

    Contract: PATCH /organizations/{org_id}
    - Response: 401 if not authenticated
    """
    # Act
    response = await client.patch(
        f"/api/organizations/{test_org.id}",
        json={"name": "Unauthorized"}
    )

    # Assert
    assert response.status_code == 401
