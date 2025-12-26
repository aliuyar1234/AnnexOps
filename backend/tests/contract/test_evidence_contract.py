"""Contract tests for evidence endpoints."""
from unittest.mock import Mock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import create_access_token
from src.models.organization import Organization
from src.models.user import User


@pytest.mark.asyncio
async def test_get_upload_url_returns_200(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """POST /evidence/upload-url returns 200 with presigned URL."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Mock the storage service to avoid real S3 calls
    with patch("src.api.routes.evidence.get_storage_service") as mock_storage:
        mock_instance = Mock()
        mock_instance.generate_upload_url.return_value = (
            "https://minio.test/upload-url",
            f"evidence/{test_org.id}/2025/12/test-uuid.pdf",
        )
        mock_storage.return_value = mock_instance

        response = await client.post(
            "/api/v1/evidence/upload-url",
            json={
                "filename": "test-document.pdf",
                "mime_type": "application/pdf",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    data = response.json()
    assert "upload_url" in data
    assert "storage_uri" in data
    assert "expires_in" in data
    assert data["upload_url"] == "https://minio.test/upload-url"
    assert "evidence/" in data["storage_uri"]


@pytest.mark.asyncio
async def test_get_upload_url_returns_415_for_unsupported_mime_type(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """POST /evidence/upload-url returns 415 for unsupported MIME types."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    response = await client.post(
        "/api/v1/evidence/upload-url",
        json={
            "filename": "malware.exe",
            "mime_type": "application/x-msdownload",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 415


@pytest.mark.asyncio
async def test_create_evidence_upload_returns_201(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """POST /evidence returns 201 for upload type evidence."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    storage_uri = f"evidence/{test_org.id}/2025/12/test-uuid.pdf"

    # Mock storage service
    with patch("src.api.routes.evidence.get_storage_service") as mock_storage:
        mock_instance = Mock()
        mock_instance.file_exists.return_value = True
        mock_instance.get_file_metadata.return_value = {
            "file_size": 1024,
            "mime_type": "application/pdf",
            "checksum_sha256": "mock-checksum",
        }
        mock_instance.compute_checksum.return_value = (
            "abc123def456789012345678901234567890123456789012345678901234abcd"
        )
        mock_storage.return_value = mock_instance

        response = await client.post(
            "/api/v1/evidence",
            json={
                "type": "upload",
                "title": "Risk Assessment Document",
                "description": "Annual risk assessment for AI system",
                "tags": ["risk", "compliance"],
                "classification": "internal",
                "type_metadata": {
                    "storage_uri": storage_uri,
                    "checksum_sha256": "a" * 64,
                    "file_size": 1024,
                    "mime_type": "application/pdf",
                    "original_filename": "risk_assessment.pdf",
                },
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Risk Assessment Document"
    assert data["type"] == "upload"
    assert data["classification"] == "internal"
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_evidence_url_returns_201(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """POST /evidence returns 201 for URL type evidence with valid URL."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    response = await client.post(
        "/api/v1/evidence",
        json={
            "type": "url",
            "title": "GDPR Compliance Guide",
            "description": "Official GDPR documentation",
            "tags": ["gdpr", "compliance"],
            "classification": "public",
            "type_metadata": {
                "url": "https://gdpr.eu/compliance-guide",
                "accessed_at": "2025-12-25T10:00:00Z",
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "GDPR Compliance Guide"
    assert data["type"] == "url"
    assert data["classification"] == "public"
    assert data["type_metadata"]["url"].rstrip("/") == "https://gdpr.eu/compliance-guide"
    assert "accessed_at" in data["type_metadata"]


@pytest.mark.asyncio
async def test_create_evidence_url_with_optional_accessed_at(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """POST /evidence returns 201 for URL type without accessed_at."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    response = await client.post(
        "/api/v1/evidence",
        json={
            "type": "url",
            "title": "Security Documentation",
            "type_metadata": {
                "url": "https://security.example.com/docs",
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Security Documentation"
    assert data["type_metadata"]["url"] == "https://security.example.com/docs"


@pytest.mark.asyncio
async def test_create_evidence_url_returns_422_for_invalid_url(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """POST /evidence returns 422 for invalid URL format."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    response = await client.post(
        "/api/v1/evidence",
        json={
            "type": "url",
            "title": "Invalid URL",
            "type_metadata": {
                "url": "not-a-valid-url",
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_evidence_url_returns_422_for_missing_url(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """POST /evidence returns 422 when url field is missing."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    response = await client.post(
        "/api/v1/evidence",
        json={
            "type": "url",
            "title": "Missing URL",
            "type_metadata": {
                "accessed_at": "2025-12-25T10:00:00Z",
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_evidence_git_returns_201(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """POST /evidence returns 201 for Git type evidence with all fields."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    response = await client.post(
        "/api/v1/evidence",
        json={
            "type": "git",
            "title": "Model Training Implementation",
            "description": "ML model training code",
            "tags": ["code", "ml"],
            "classification": "confidential",
            "type_metadata": {
                "repo_url": "https://github.com/org/ml-models",
                "commit_hash": "abc123def4567890abcdef1234567890abcdef12",
                "file_path": "training/model.py",
                "branch": "main",
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Model Training Implementation"
    assert data["type"] == "git"
    assert data["type_metadata"]["repo_url"] == "https://github.com/org/ml-models"
    assert data["type_metadata"]["commit_hash"] == "abc123def4567890abcdef1234567890abcdef12"
    assert data["type_metadata"]["file_path"] == "training/model.py"
    assert data["type_metadata"]["branch"] == "main"


@pytest.mark.asyncio
async def test_create_evidence_git_with_optional_fields(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """POST /evidence returns 201 for Git type with only required fields."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    response = await client.post(
        "/api/v1/evidence",
        json={
            "type": "git",
            "title": "Code Snapshot",
            "type_metadata": {
                "repo_url": "https://github.com/org/project",
                "commit_hash": "1234567890abcdef1234567890abcdef12345678",
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["type"] == "git"
    assert data["type_metadata"]["repo_url"] == "https://github.com/org/project"
    assert data["type_metadata"]["commit_hash"] == "1234567890abcdef1234567890abcdef12345678"


@pytest.mark.asyncio
async def test_create_evidence_git_returns_422_for_invalid_commit_hash(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """POST /evidence returns 422 for invalid commit hash (not 40 chars hex)."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Too short commit hash
    response = await client.post(
        "/api/v1/evidence",
        json={
            "type": "git",
            "title": "Invalid Commit",
            "type_metadata": {
                "repo_url": "https://github.com/org/project",
                "commit_hash": "abc123",  # Too short
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_evidence_git_returns_422_for_non_hex_commit_hash(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """POST /evidence returns 422 for non-hexadecimal commit hash."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    response = await client.post(
        "/api/v1/evidence",
        json={
            "type": "git",
            "title": "Invalid Commit Hash",
            "type_metadata": {
                "repo_url": "https://github.com/org/project",
                "commit_hash": "gggggggggggggggggggggggggggggggggggggggg",  # Invalid hex
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_evidence_git_returns_422_for_missing_repo_url(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """POST /evidence returns 422 when repo_url is missing."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    response = await client.post(
        "/api/v1/evidence",
        json={
            "type": "git",
            "title": "Missing Repo",
            "type_metadata": {
                "commit_hash": "1234567890abcdef1234567890abcdef12345678",
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_evidence_git_returns_422_for_missing_commit_hash(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """POST /evidence returns 422 when commit_hash is missing."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    response = await client.post(
        "/api/v1/evidence",
        json={
            "type": "git",
            "title": "Missing Commit",
            "type_metadata": {
                "repo_url": "https://github.com/org/project",
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_evidence_note_returns_201(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """POST /evidence returns 201 for note type evidence."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    response = await client.post(
        "/api/v1/evidence",
        json={
            "type": "note",
            "title": "Meeting Minutes",
            "description": "Risk assessment meeting with stakeholders",
            "tags": ["meeting", "risk"],
            "classification": "confidential",
            "type_metadata": {
                "content": "Discussed AI system risks and mitigation strategies.",
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Meeting Minutes"
    assert data["type"] == "note"
    assert data["classification"] == "confidential"


@pytest.mark.asyncio
async def test_create_evidence_returns_422_for_invalid_metadata(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """POST /evidence returns 422 for missing required metadata fields."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Missing 'content' field for note type
    response = await client.post(
        "/api/v1/evidence",
        json={
            "type": "note",
            "title": "Incomplete Note",
            "type_metadata": {},
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_evidence_returns_413_for_large_file(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """POST /evidence returns 413 for files over 50MB."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    storage_uri = f"evidence/{test_org.id}/2025/12/large-file.pdf"

    # Mock storage service to return large file size
    with patch("src.api.routes.evidence.get_storage_service") as mock_storage:
        mock_instance = Mock()
        mock_instance.file_exists.return_value = True
        mock_instance.get_file_metadata.return_value = {
            "file_size": 51 * 1024 * 1024,  # 51MB
            "mime_type": "application/pdf",
        }
        mock_instance.compute_checksum.return_value = "a" * 64
        mock_storage.return_value = mock_instance

        response = await client.post(
            "/api/v1/evidence",
            json={
                "type": "upload",
                "title": "Large File",
                "type_metadata": {
                    "storage_uri": storage_uri,
                    "checksum_sha256": "a" * 64,
                    "file_size": 51 * 1024 * 1024,
                    "mime_type": "application/pdf",
                    "original_filename": "large.pdf",
                },
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 413


@pytest.mark.asyncio
async def test_create_evidence_returns_415_for_unsupported_mime_type(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """POST /evidence returns 415 for unsupported MIME types."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    storage_uri = f"evidence/{test_org.id}/2025/12/malware.exe"

    # Mock storage service
    with patch("src.api.routes.evidence.get_storage_service") as mock_storage:
        mock_instance = Mock()
        mock_instance.file_exists.return_value = True
        mock_instance.get_file_metadata.return_value = {
            "file_size": 1024,
            "mime_type": "application/x-msdownload",
        }
        mock_instance.compute_checksum.return_value = "a" * 64
        mock_storage.return_value = mock_instance

        response = await client.post(
            "/api/v1/evidence",
            json={
                "type": "upload",
                "title": "Malware",
                "type_metadata": {
                    "storage_uri": storage_uri,
                    "checksum_sha256": "a" * 64,
                    "file_size": 1024,
                    "mime_type": "application/x-msdownload",
                    "original_filename": "malware.exe",
                },
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 415


@pytest.mark.asyncio
async def test_list_evidence_returns_200(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """GET /evidence returns 200 with evidence list."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    response = await client.get(
        "/api/v1/evidence",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert "items" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data
    assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_get_evidence_returns_200_with_details(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_evidence_item,
    test_evidence_mapping,
):
    """GET /evidence/{id} returns 200 with evidence details including usage_count and mapped_versions."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    response = await client.get(
        f"/api/v1/evidence/{test_evidence_item.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(test_evidence_item.id)
    assert data["title"] == test_evidence_item.title
    assert "usage_count" in data
    assert data["usage_count"] == 1  # Has one mapping from fixture
    assert "mapped_versions" in data
    assert isinstance(data["mapped_versions"], list)
    assert len(data["mapped_versions"]) == 1
    # Check version summary structure
    version = data["mapped_versions"][0]
    assert "id" in version
    assert "label" in version
    assert "system_id" in version
    assert "system_name" in version


@pytest.mark.asyncio
async def test_delete_evidence_returns_204(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_evidence_item,
):
    """DELETE /evidence/{id} returns 204."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    response = await client.delete(
        f"/api/v1/evidence/{test_evidence_item.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_create_evidence_returns_403_for_viewer(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_viewer_user: User,
):
    """POST /evidence returns 403 for VIEWER role."""
    token = create_access_token({"sub": str(test_viewer_user.id)})

    response = await client.post(
        "/api/v1/evidence",
        json={
            "type": "note",
            "title": "Test Note",
            "type_metadata": {"content": "Test content"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_evidence_with_search_returns_200(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """GET /evidence with search parameter returns 200 with filtered results."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create evidence items with different content
    await client.post(
        "/api/v1/evidence",
        json={
            "type": "note",
            "title": "Risk Assessment Report",
            "description": "Annual risk assessment for AI system",
            "type_metadata": {"content": "Detailed risk analysis"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    await client.post(
        "/api/v1/evidence",
        json={
            "type": "note",
            "title": "Compliance Guide",
            "description": "GDPR compliance documentation",
            "type_metadata": {"content": "Privacy guidelines"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    # Search for "risk"
    response = await client.get(
        "/api/v1/evidence?search=risk",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert "risk" in data["items"][0]["title"].lower() or "risk" in data["items"][0]["description"].lower()


@pytest.mark.asyncio
async def test_list_evidence_with_tag_filter_returns_200(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """GET /evidence with tags parameter returns 200 with filtered results."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create evidence with different tags
    await client.post(
        "/api/v1/evidence",
        json={
            "type": "note",
            "title": "Evidence 1",
            "tags": ["compliance", "gdpr"],
            "type_metadata": {"content": "Content 1"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    await client.post(
        "/api/v1/evidence",
        json={
            "type": "note",
            "title": "Evidence 2",
            "tags": ["compliance", "risk"],
            "type_metadata": {"content": "Content 2"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    await client.post(
        "/api/v1/evidence",
        json={
            "type": "note",
            "title": "Evidence 3",
            "tags": ["gdpr"],
            "type_metadata": {"content": "Content 3"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    # Filter by single tag "compliance"
    response = await client.get(
        "/api/v1/evidence?tags=compliance",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2

    # Filter by multiple tags (must have ALL)
    response = await client.get(
        "/api/v1/evidence?tags=compliance&tags=gdpr",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert set(data["items"][0]["tags"]) >= {"compliance", "gdpr"}


@pytest.mark.asyncio
async def test_download_evidence_returns_302_for_upload_type(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """GET /evidence/{id}/download returns 302 redirect for upload type evidence."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    storage_uri = f"evidence/{test_org.id}/2025/12/test-download.pdf"

    # Create upload type evidence
    with patch("src.api.routes.evidence.get_storage_service") as mock_storage:
        mock_instance = Mock()
        mock_instance.file_exists.return_value = True
        mock_instance.get_file_metadata.return_value = {
            "file_size": 1024,
            "mime_type": "application/pdf",
        }
        mock_instance.compute_checksum.return_value = (
            "abc123def456789012345678901234567890123456789012345678901234abcd"
        )
        mock_storage.return_value = mock_instance

        response = await client.post(
            "/api/v1/evidence",
            json={
                "type": "upload",
                "title": "Test Download",
                "type_metadata": {
                    "storage_uri": storage_uri,
                    "checksum_sha256": "a" * 64,
                    "file_size": 1024,
                    "mime_type": "application/pdf",
                    "original_filename": "test.pdf",
                },
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    evidence_id = response.json()["id"]

    # Test download endpoint
    with patch("src.api.routes.evidence.get_storage_service") as mock_storage:
        mock_instance = Mock()
        mock_instance.generate_download_url.return_value = "https://minio.test/download-url"
        mock_storage.return_value = mock_instance

        response = await client.get(
            f"/api/v1/evidence/{evidence_id}/download",
            headers={"Authorization": f"Bearer {token}"},
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert response.headers["location"] == "https://minio.test/download-url"


@pytest.mark.asyncio
async def test_download_evidence_returns_400_for_non_upload_type(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """GET /evidence/{id}/download returns 400 for non-upload type evidence."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create note type evidence
    response = await client.post(
        "/api/v1/evidence",
        json={
            "type": "note",
            "title": "Test Note",
            "type_metadata": {"content": "Cannot download this"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    evidence_id = response.json()["id"]

    # Try to download
    response = await client.get(
        f"/api/v1/evidence/{evidence_id}/download",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    assert "Only 'upload' type evidence has downloadable files" in response.json()["detail"]


@pytest.mark.asyncio
async def test_update_evidence_returns_200(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """PATCH /evidence/{id} returns 200 with updated evidence."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create evidence
    response = await client.post(
        "/api/v1/evidence",
        json={
            "type": "note",
            "title": "Original Title",
            "description": "Original description",
            "tags": ["original"],
            "classification": "internal",
            "type_metadata": {"content": "Original content"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    evidence_id = response.json()["id"]

    # Update evidence
    response = await client.patch(
        f"/api/v1/evidence/{evidence_id}",
        json={
            "title": "Updated Title",
            "description": "Updated description",
            "tags": ["updated", "test"],
            "classification": "confidential",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"
    assert data["description"] == "Updated description"
    assert set(data["tags"]) == {"updated", "test"}
    assert data["classification"] == "confidential"
    assert "usage_count" in data
    assert "mapped_versions" in data


@pytest.mark.asyncio
async def test_update_evidence_partial_update(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """PATCH /evidence/{id} allows partial updates."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create evidence
    response = await client.post(
        "/api/v1/evidence",
        json={
            "type": "note",
            "title": "Original Title",
            "description": "Original description",
            "tags": ["original"],
            "type_metadata": {"content": "Original content"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    evidence_id = response.json()["id"]

    # Update only title
    response = await client.patch(
        f"/api/v1/evidence/{evidence_id}",
        json={"title": "New Title Only"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "New Title Only"
    assert data["description"] == "Original description"  # Unchanged
    assert data["tags"] == ["original"]  # Unchanged


@pytest.mark.asyncio
async def test_update_evidence_returns_403_for_viewer(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_viewer_user: User,
    test_evidence_item,
):
    """PATCH /evidence/{id} returns 403 for VIEWER role."""
    token = create_access_token({"sub": str(test_viewer_user.id)})

    response = await client.patch(
        f"/api/v1/evidence/{test_evidence_item.id}",
        json={"title": "Unauthorized Update"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_evidence_returns_409_when_has_mappings_without_force(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_evidence_item,
    test_evidence_mapping,
):
    """DELETE /evidence/{id} returns 409 when evidence has mappings without force=true."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    response = await client.delete(
        f"/api/v1/evidence/{test_evidence_item.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 409
    assert "existing mapping" in response.json()["detail"].lower()
    assert "force=true" in response.json()["detail"]


@pytest.mark.asyncio
async def test_delete_evidence_with_force_returns_204(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_evidence_item,
    test_evidence_mapping,
):
    """DELETE /evidence/{id}?force=true returns 204 and deletes mappings."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    response = await client.delete(
        f"/api/v1/evidence/{test_evidence_item.id}?force=true",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 204

    # Verify evidence is deleted
    response = await client.get(
        f"/api/v1/evidence/{test_evidence_item.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_evidence_without_mappings_returns_204(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """DELETE /evidence/{id} returns 204 when evidence has no mappings."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create evidence without mappings
    response = await client.post(
        "/api/v1/evidence",
        json={
            "type": "note",
            "title": "To be deleted",
            "type_metadata": {"content": "Will be deleted"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    evidence_id = response.json()["id"]

    # Delete without force (should work since no mappings)
    response = await client.delete(
        f"/api/v1/evidence/{evidence_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 204
