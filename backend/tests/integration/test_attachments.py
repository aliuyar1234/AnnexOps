"""Integration tests for attachment operations."""
import io
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import patch, MagicMock

from src.core.security import create_access_token
from src.models.organization import Organization
from src.models.user import User
from src.models.ai_system import AISystem


@pytest.mark.asyncio
async def test_attachment_upload_download_flow(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """Test complete attachment flow: upload -> list -> download."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Mock the storage client to avoid needing MinIO
    with patch("src.services.attachment_service.get_storage_client") as mock_storage:
        mock_client = MagicMock()
        mock_client.upload_file.return_value = (
            "attachments/test/file.txt",
            "abc123def456",
            100,
        )
        mock_client.get_presigned_url.return_value = "http://localhost:9000/download/file.txt"
        mock_storage.return_value = mock_client

        # Step 1: Upload attachment
        file_content = b"Test file content"
        upload_response = await client.post(
            f"/api/systems/{test_ai_system.id}/attachments",
            files={"file": ("doc.txt", io.BytesIO(file_content), "text/plain")},
            data={"title": "Architecture Doc", "description": "System architecture"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert upload_response.status_code == 201
        attachment = upload_response.json()
        attachment_id = attachment["id"]

        # Step 2: List attachments
        list_response = await client.get(
            f"/api/systems/{test_ai_system.id}/attachments",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert list_response.status_code == 200
        attachments = list_response.json()
        assert len(attachments) == 1
        assert attachments[0]["id"] == attachment_id

        # Step 3: Download attachment (returns redirect)
        download_response = await client.get(
            f"/api/systems/{test_ai_system.id}/attachments/{attachment_id}/download",
            headers={"Authorization": f"Bearer {token}"},
            follow_redirects=False,
        )
        assert download_response.status_code == 302


@pytest.mark.asyncio
async def test_attachment_delete_removes_file(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """Test that deleting attachment removes it from list."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    with patch("src.services.attachment_service.get_storage_client") as mock_storage:
        mock_client = MagicMock()
        mock_client.upload_file.return_value = (
            "attachments/test/file.txt",
            "abc123",
            100,
        )
        mock_client.delete_file.return_value = True
        mock_storage.return_value = mock_client

        # Upload attachment
        upload_response = await client.post(
            f"/api/systems/{test_ai_system.id}/attachments",
            files={"file": ("test.txt", io.BytesIO(b"content"), "text/plain")},
            data={"title": "To Delete"},
            headers={"Authorization": f"Bearer {token}"},
        )
        attachment_id = upload_response.json()["id"]

        # Delete attachment
        delete_response = await client.delete(
            f"/api/systems/{test_ai_system.id}/attachments/{attachment_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert delete_response.status_code == 204

        # Verify deleted from list
        list_response = await client.get(
            f"/api/systems/{test_ai_system.id}/attachments",
            headers={"Authorization": f"Bearer {token}"},
        )
        attachments = list_response.json()
        assert len(attachments) == 0
