"""Contract tests for attachment endpoints."""
import io
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import create_access_token
from src.models.organization import Organization
from src.models.user import User
from src.models.ai_system import AISystem


@pytest.mark.asyncio
async def test_upload_attachment_returns_201(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """POST /systems/{id}/attachments returns 201 on successful upload."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create a simple text file
    file_content = b"Test file content for attachment"

    response = await client.post(
        f"/api/systems/{test_ai_system.id}/attachments",
        files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
        data={"title": "Test Document", "description": "Test description"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Document"
    assert data["description"] == "Test description"
    assert data["mime_type"] == "text/plain"
    assert data["file_size"] == len(file_content)
    assert "id" in data


@pytest.mark.asyncio
async def test_upload_attachment_returns_413_for_large_file(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """POST /systems/{id}/attachments returns 413 for files over 50MB."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create a file larger than 50MB (51MB)
    large_content = b"x" * (51 * 1024 * 1024)

    response = await client.post(
        f"/api/systems/{test_ai_system.id}/attachments",
        files={"file": ("large.txt", io.BytesIO(large_content), "text/plain")},
        data={"title": "Large File"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 413


@pytest.mark.asyncio
async def test_upload_attachment_returns_415_for_unsupported_type(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """POST /systems/{id}/attachments returns 415 for unsupported file types."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    response = await client.post(
        f"/api/systems/{test_ai_system.id}/attachments",
        files={"file": ("script.exe", io.BytesIO(b"fake exe"), "application/x-msdownload")},
        data={"title": "Executable File"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 415


@pytest.mark.asyncio
async def test_list_attachments_returns_200(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """GET /systems/{id}/attachments returns 200 with attachment list."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    response = await client.get(
        f"/api/systems/{test_ai_system.id}/attachments",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
