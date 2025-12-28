"""Contract tests for export endpoints."""
from decimal import Decimal
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import create_access_token
from src.models.ai_system import AISystem
from src.models.export import Export
from src.models.organization import Organization
from src.models.system_version import SystemVersion
from src.models.user import User


@pytest.mark.asyncio
async def test_list_exports_returns_200(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_ai_system: AISystem,
    test_version: SystemVersion,
    test_viewer_user: User,
    test_editor_user: User,
):
    """GET /systems/{id}/versions/{vid}/exports returns 200 with export list."""
    token = create_access_token({"sub": str(test_viewer_user.id)})

    # Create test exports
    export1 = Export(
        version_id=test_version.id,
        export_type="full",
        snapshot_hash="a" * 64,
        storage_uri=f"exports/{test_org.id}/2025/12/export1.pdf",
        file_size=1024,
        include_diff=False,
        compare_version_id=None,
        completeness_score=Decimal("95.50"),
        created_by=test_editor_user.id,
    )
    export2 = Export(
        version_id=test_version.id,
        export_type="full",
        snapshot_hash="b" * 64,
        storage_uri=f"exports/{test_org.id}/2025/12/export2.pdf",
        file_size=2048,
        include_diff=False,
        compare_version_id=None,
        completeness_score=Decimal("98.00"),
        created_by=test_editor_user.id,
    )
    db.add_all([export1, export2])
    await db.flush()

    response = await client.get(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}/exports",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert data["limit"] == 100
    assert data["offset"] == 0

    # Verify export structure
    first_export = data["items"][0]
    assert "id" in first_export
    assert "version_id" in first_export
    assert "export_type" in first_export
    assert "snapshot_hash" in first_export
    assert "storage_uri" in first_export
    assert "file_size" in first_export
    assert "include_diff" in first_export
    assert "completeness_score" in first_export
    assert "created_by" in first_export
    assert "created_at" in first_export


@pytest.mark.asyncio
async def test_list_exports_pagination_works(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_ai_system: AISystem,
    test_version: SystemVersion,
    test_viewer_user: User,
    test_editor_user: User,
):
    """GET /systems/{id}/versions/{vid}/exports supports pagination."""
    token = create_access_token({"sub": str(test_viewer_user.id)})

    # Create 3 test exports
    for i in range(3):
        export = Export(
            version_id=test_version.id,
            export_type="full",
            snapshot_hash=f"{i}" * 64,
            storage_uri=f"exports/{test_org.id}/2025/12/export{i}.pdf",
            file_size=1024 * (i + 1),
            include_diff=False,
            compare_version_id=None,
            completeness_score=Decimal("95.00"),
            created_by=test_editor_user.id,
        )
        db.add(export)
    await db.flush()

    # Test limit
    response = await client.get(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}/exports?limit=2",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["items"]) == 2
    assert data["limit"] == 2

    # Test offset
    response = await client.get(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}/exports?offset=2",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["items"]) == 1
    assert data["offset"] == 2


@pytest.mark.asyncio
async def test_list_exports_returns_404_for_nonexistent_version(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_ai_system: AISystem,
    test_viewer_user: User,
):
    """GET /systems/{id}/versions/{vid}/exports returns 404 for nonexistent version."""
    token = create_access_token({"sub": str(test_viewer_user.id)})

    nonexistent_version_id = uuid4()
    response = await client.get(
        f"/api/systems/{test_ai_system.id}/versions/{nonexistent_version_id}/exports",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_download_export_returns_302_redirect(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_version: SystemVersion,
    test_viewer_user: User,
    test_editor_user: User,
):
    """GET /exports/{id}/download returns 302 redirect to presigned URL."""
    token = create_access_token({"sub": str(test_viewer_user.id)})

    # Create test export
    export = Export(
        version_id=test_version.id,
        export_type="full",
        snapshot_hash="a" * 64,
        storage_uri=f"exports/{test_org.id}/2025/12/export.pdf",
        file_size=1024,
        include_diff=False,
        compare_version_id=None,
        completeness_score=Decimal("95.50"),
        created_by=test_editor_user.id,
    )
    db.add(export)
    await db.flush()

    # Mock storage service
    with patch("src.services.export_service.get_storage_service") as mock_storage:
        mock_instance = Mock()
        mock_instance.generate_download_url.return_value = (
            "https://minio.test/presigned-download-url"
        )
        mock_storage.return_value = mock_instance

        response = await client.get(
            f"/api/exports/{export.id}/download",
            headers={"Authorization": f"Bearer {token}"},
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert response.headers["location"] == "https://minio.test/presigned-download-url"


@pytest.mark.asyncio
async def test_download_export_returns_404_for_nonexistent_export(
    client: AsyncClient,
    db: AsyncSession,
    test_viewer_user: User,
):
    """GET /exports/{id}/download returns 404 for nonexistent export."""
    token = create_access_token({"sub": str(test_viewer_user.id)})

    nonexistent_export_id = uuid4()
    response = await client.get(
        f"/api/exports/{nonexistent_export_id}/download",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_export_with_diff_returns_201(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_ai_system: AISystem,
    test_editor_user: User,
):
    """POST /systems/{id}/versions/{vid}/exports with include_diff=True returns 201."""
    from tests.conftest import create_version

    # Create two versions
    version1 = await create_version(
        db,
        ai_system_id=test_ai_system.id,
        label="1.0.0",
        created_by=test_editor_user.id,
    )
    version2 = await create_version(
        db,
        ai_system_id=test_ai_system.id,
        label="2.0.0",
        created_by=test_editor_user.id,
    )
    await db.flush()

    token = create_access_token({"sub": str(test_editor_user.id)})

    # Mock storage service and docx generator
    with patch("src.services.export_service.get_storage_service") as mock_storage, \
         patch("src.services.export_service.generate_annex_iv_document") as mock_generate_docx:
        mock_storage_instance = Mock()
        mock_storage_instance.upload_file.return_value = f"exports/{test_org.id}/2025/12/test.zip"
        mock_storage.return_value = mock_storage_instance

        from io import BytesIO

        mock_generate_docx.return_value = BytesIO(b"fake docx content")

        response = await client.post(
            f"/api/systems/{test_ai_system.id}/versions/{version2.id}/exports",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "include_diff": True,
                "compare_version_id": str(version1.id),
            },
        )

    assert response.status_code == 201
    data = response.json()

    # Verify response structure
    assert "id" in data
    assert "version_id" in data
    assert data["export_type"] == "diff"
    assert data["include_diff"] is True
    assert data["compare_version_id"] == str(version1.id)
    assert "snapshot_hash" in data
    assert "storage_uri" in data
    assert "file_size" in data
    assert "completeness_score" in data
    assert "created_by" in data
    assert "created_at" in data
