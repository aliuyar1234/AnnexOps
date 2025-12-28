"""Integration tests for Role-Based Access Control (RBAC) on evidence endpoints."""

from unittest.mock import Mock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import create_access_token
from src.models.organization import Organization
from src.models.user import User


@pytest.mark.asyncio
class TestViewerEvidenceAccess:
    """Test viewer role permissions on evidence endpoints."""

    async def test_viewer_can_list_evidence(
        self,
        client: AsyncClient,
        db: AsyncSession,
        test_org: Organization,
        test_viewer_user: User,
        test_editor_user: User,
    ):
        """Test that viewer can list evidence items (read permission)."""
        # Create some evidence as editor
        editor_token = create_access_token({"sub": str(test_editor_user.id)})
        await client.post(
            "/api/evidence",
            json={
                "type": "note",
                "title": "Test Evidence",
                "type_metadata": {"content": "Test content"},
            },
            headers={"Authorization": f"Bearer {editor_token}"},
        )

        # Viewer should be able to list evidence
        viewer_token = create_access_token({"sub": str(test_viewer_user.id)})
        response = await client.get(
            "/api/evidence",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

    async def test_viewer_can_get_evidence_detail(
        self,
        client: AsyncClient,
        db: AsyncSession,
        test_org: Organization,
        test_viewer_user: User,
        test_editor_user: User,
    ):
        """Test that viewer can view evidence details (read permission)."""
        # Create evidence as editor
        editor_token = create_access_token({"sub": str(test_editor_user.id)})
        create_response = await client.post(
            "/api/evidence",
            json={
                "type": "note",
                "title": "Test Evidence Detail",
                "description": "Detailed test evidence",
                "type_metadata": {"content": "Test content"},
            },
            headers={"Authorization": f"Bearer {editor_token}"},
        )
        evidence_id = create_response.json()["id"]

        # Viewer should be able to get evidence details
        viewer_token = create_access_token({"sub": str(test_viewer_user.id)})
        response = await client.get(
            f"/api/evidence/{evidence_id}",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

        assert response.status_code == 200
        evidence = response.json()
        assert evidence["id"] == evidence_id
        assert evidence["title"] == "Test Evidence Detail"
        assert "usage_count" in evidence
        assert "mapped_versions" in evidence

    async def test_viewer_can_download_evidence(
        self,
        client: AsyncClient,
        db: AsyncSession,
        test_org: Organization,
        test_viewer_user: User,
        test_editor_user: User,
    ):
        """Test that viewer can download upload-type evidence files (read permission)."""
        editor_token = create_access_token({"sub": str(test_editor_user.id)})

        with patch("src.api.routes.evidence.get_storage_service") as mock_storage_route:
            with patch(
                "src.services.evidence_service.EvidenceService._validate_file_upload_metadata"
            ):
                # Mock storage service
                mock_storage = Mock()
                storage_uri = f"evidence/{test_org.id}/2025/12/test-file.pdf"
                mock_storage.generate_upload_url.return_value = (
                    "https://minio.test/upload-url",
                    storage_uri,
                )
                mock_storage.file_exists.return_value = True
                mock_storage.get_file_metadata.return_value = {
                    "file_size": 2048,
                    "mime_type": "application/pdf",
                }
                mock_storage.compute_checksum.return_value = "a" * 64
                mock_storage.generate_download_url.return_value = (
                    "https://minio.test/download-url?presigned=true"
                )
                mock_storage_route.return_value = mock_storage

                # Create upload-type evidence as editor
                create_response = await client.post(
                    "/api/evidence",
                    json={
                        "type": "upload",
                        "title": "Downloadable Evidence",
                        "type_metadata": {
                            "storage_uri": storage_uri,
                            "checksum_sha256": "a" * 64,
                            "file_size": 2048,
                            "mime_type": "application/pdf",
                            "original_filename": "test-file.pdf",
                        },
                    },
                    headers={"Authorization": f"Bearer {editor_token}"},
                )
                evidence_id = create_response.json()["id"]

                # Viewer should be able to download evidence
                viewer_token = create_access_token({"sub": str(test_viewer_user.id)})
                response = await client.get(
                    f"/api/evidence/{evidence_id}/download",
                    headers={"Authorization": f"Bearer {viewer_token}"},
                    follow_redirects=False,
                )

                assert response.status_code == 302
                assert "https://minio.test/download-url" in response.headers["location"]

    async def test_viewer_cannot_create_evidence(
        self,
        client: AsyncClient,
        db: AsyncSession,
        test_org: Organization,
        test_viewer_user: User,
    ):
        """Test that viewer cannot create evidence (requires Editor role)."""
        viewer_token = create_access_token({"sub": str(test_viewer_user.id)})

        response = await client.post(
            "/api/evidence",
            json={
                "type": "note",
                "title": "Unauthorized Evidence",
                "type_metadata": {"content": "This should fail"},
            },
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

        assert response.status_code == 403
        assert "Insufficient permissions" in response.json()["detail"]

    async def test_viewer_cannot_update_evidence(
        self,
        client: AsyncClient,
        db: AsyncSession,
        test_org: Organization,
        test_viewer_user: User,
        test_editor_user: User,
    ):
        """Test that viewer cannot update evidence (requires Editor role)."""
        # Create evidence as editor
        editor_token = create_access_token({"sub": str(test_editor_user.id)})
        create_response = await client.post(
            "/api/evidence",
            json={
                "type": "note",
                "title": "Original Title",
                "type_metadata": {"content": "Original content"},
            },
            headers={"Authorization": f"Bearer {editor_token}"},
        )
        evidence_id = create_response.json()["id"]

        # Viewer should not be able to update evidence
        viewer_token = create_access_token({"sub": str(test_viewer_user.id)})
        response = await client.patch(
            f"/api/evidence/{evidence_id}",
            json={"title": "Updated Title"},
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

        assert response.status_code == 403
        assert "Insufficient permissions" in response.json()["detail"]

    async def test_viewer_cannot_delete_evidence(
        self,
        client: AsyncClient,
        db: AsyncSession,
        test_org: Organization,
        test_viewer_user: User,
        test_editor_user: User,
    ):
        """Test that viewer cannot delete evidence (requires Editor role)."""
        # Create evidence as editor
        editor_token = create_access_token({"sub": str(test_editor_user.id)})
        create_response = await client.post(
            "/api/evidence",
            json={
                "type": "note",
                "title": "To Be Deleted",
                "type_metadata": {"content": "Delete me"},
            },
            headers={"Authorization": f"Bearer {editor_token}"},
        )
        evidence_id = create_response.json()["id"]

        # Viewer should not be able to delete evidence
        viewer_token = create_access_token({"sub": str(test_viewer_user.id)})
        response = await client.delete(
            f"/api/evidence/{evidence_id}",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

        assert response.status_code == 403
        assert "Insufficient permissions" in response.json()["detail"]


@pytest.mark.asyncio
class TestEditorEvidenceAccess:
    """Test editor role permissions on evidence endpoints."""

    async def test_editor_can_create_evidence(
        self,
        client: AsyncClient,
        db: AsyncSession,
        test_org: Organization,
        test_editor_user: User,
    ):
        """Test that editor can create evidence."""
        editor_token = create_access_token({"sub": str(test_editor_user.id)})

        response = await client.post(
            "/api/evidence",
            json={
                "type": "note",
                "title": "Editor Created Evidence",
                "description": "Created by editor",
                "type_metadata": {"content": "Editor content"},
            },
            headers={"Authorization": f"Bearer {editor_token}"},
        )

        assert response.status_code == 201
        evidence = response.json()
        assert evidence["title"] == "Editor Created Evidence"
        assert evidence["created_by"] == str(test_editor_user.id)

    async def test_editor_can_update_evidence(
        self,
        client: AsyncClient,
        db: AsyncSession,
        test_org: Organization,
        test_editor_user: User,
    ):
        """Test that editor can update evidence."""
        editor_token = create_access_token({"sub": str(test_editor_user.id)})

        # Create evidence
        create_response = await client.post(
            "/api/evidence",
            json={
                "type": "note",
                "title": "Original Title",
                "type_metadata": {"content": "Original content"},
            },
            headers={"Authorization": f"Bearer {editor_token}"},
        )
        evidence_id = create_response.json()["id"]

        # Update evidence
        update_response = await client.patch(
            f"/api/evidence/{evidence_id}",
            json={
                "title": "Updated Title",
                "description": "Updated description",
                "tags": ["updated", "test"],
            },
            headers={"Authorization": f"Bearer {editor_token}"},
        )

        assert update_response.status_code == 200
        evidence = update_response.json()
        assert evidence["title"] == "Updated Title"
        assert evidence["description"] == "Updated description"
        assert "updated" in evidence["tags"]

    async def test_editor_can_delete_evidence(
        self,
        client: AsyncClient,
        db: AsyncSession,
        test_org: Organization,
        test_editor_user: User,
    ):
        """Test that editor can delete evidence."""
        editor_token = create_access_token({"sub": str(test_editor_user.id)})

        # Create evidence
        create_response = await client.post(
            "/api/evidence",
            json={
                "type": "note",
                "title": "To Be Deleted",
                "type_metadata": {"content": "Delete me"},
            },
            headers={"Authorization": f"Bearer {editor_token}"},
        )
        evidence_id = create_response.json()["id"]

        # Delete evidence
        delete_response = await client.delete(
            f"/api/evidence/{evidence_id}",
            headers={"Authorization": f"Bearer {editor_token}"},
        )

        assert delete_response.status_code == 204

        # Verify deletion
        get_response = await client.get(
            f"/api/evidence/{evidence_id}",
            headers={"Authorization": f"Bearer {editor_token}"},
        )
        assert get_response.status_code == 404
