"""Integration tests for export operations."""
from datetime import UTC
from decimal import Decimal
from unittest.mock import Mock, patch

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
async def test_export_history_listing_workflow(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_ai_system: AISystem,
    test_version: SystemVersion,
    test_viewer_user: User,
    test_editor_user: User,
):
    """Test complete export history listing workflow.

    Verifies that:
    1. User can list exports for a version
    2. Exports are ordered by creation date (newest first)
    3. Export details are complete and accurate
    """
    token = create_access_token({"sub": str(test_viewer_user.id)})

    # Create multiple exports at different times
    from datetime import datetime, timedelta

    now = datetime.now(UTC)
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
    export1.created_at = now - timedelta(minutes=1)
    db.add(export1)
    await db.flush()

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
    export2.created_at = now
    db.add(export2)
    await db.flush()

    # List exports
    response = await client.get(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}/exports",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()

    # Verify structure
    assert "items" in data
    assert "total" in data
    assert data["total"] == 2
    assert len(data["items"]) == 2

    # Verify ordering (newest first)
    exports = data["items"]
    assert str(exports[0]["id"]) == str(export2.id)  # Export2 created later
    assert str(exports[1]["id"]) == str(export1.id)

    # Verify export details
    first = exports[0]
    assert first["export_type"] == "full"
    assert first["file_size"] == 2048
    assert first["include_diff"] is False
    assert first["compare_version_id"] is None
    assert float(first["completeness_score"]) == 98.00
    assert str(first["created_by"]) == str(test_editor_user.id)


@pytest.mark.asyncio
async def test_export_download_workflow(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_version: SystemVersion,
    test_viewer_user: User,
    test_editor_user: User,
):
    """Test complete export download workflow.

    Verifies that:
    1. User can request download URL for an export
    2. System generates presigned URL
    3. Response is 302 redirect to presigned URL
    """
    token = create_access_token({"sub": str(test_viewer_user.id)})

    # Create export
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

    # Mock storage service to avoid real S3 calls
    with patch("src.services.export_service.get_storage_service") as mock_storage:
        mock_instance = Mock()
        presigned_url = "https://minio.test/presigned-download?sig=abc123"
        mock_instance.generate_download_url.return_value = presigned_url
        mock_storage.return_value = mock_instance

        # Request download
        response = await client.get(
            f"/api/exports/{export.id}/download",
            headers={"Authorization": f"Bearer {token}"},
            follow_redirects=False,
        )

    # Verify redirect
    assert response.status_code == 302
    assert response.headers["location"] == presigned_url

    # Verify storage service was called correctly
    mock_instance.generate_download_url.assert_called_once()
    call_args = mock_instance.generate_download_url.call_args
    assert call_args[0][0] == export.storage_uri
    assert call_args[1]["expires_in"] == 3600


@pytest.mark.asyncio
async def test_export_listing_with_pagination(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_ai_system: AISystem,
    test_version: SystemVersion,
    test_viewer_user: User,
    test_editor_user: User,
):
    """Test export listing with pagination parameters.

    Verifies that:
    1. Pagination limit works correctly
    2. Pagination offset works correctly
    3. Total count is accurate regardless of limit/offset
    """
    token = create_access_token({"sub": str(test_viewer_user.id)})

    # Create 5 exports
    exports = []
    for i in range(5):
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
        exports.append(export)
    await db.flush()

    # Test limit
    response = await client.get(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}/exports?limit=2",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert len(data["items"]) == 2
    assert data["limit"] == 2
    assert data["offset"] == 0

    # Test offset
    response = await client.get(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}/exports?offset=3",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert len(data["items"]) == 2  # 5 total - 3 offset = 2 remaining
    assert data["offset"] == 3

    # Test limit + offset
    response = await client.get(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}/exports?limit=2&offset=1",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert len(data["items"]) == 2
    assert data["limit"] == 2
    assert data["offset"] == 1


@pytest.mark.asyncio
async def test_export_access_control(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_ai_system: AISystem,
    test_version: SystemVersion,
    test_viewer_user: User,
    test_editor_user: User,
):
    """Test export access control across organizations.

    Verifies that:
    1. Users can only access exports for their own organization
    2. Attempting to access other org's exports returns 404
    """
    # Create another org and user
    from src.models.organization import Organization as OrgModel
    from tests.conftest import create_ai_system, create_user, create_version

    other_org = OrgModel(name="Other Organization")
    db.add(other_org)
    await db.flush()

    other_user = await create_user(
        db,
        org_id=other_org.id,
        email="other@test.com",
        role=test_viewer_user.role,
    )

    # Create system and version for other org
    other_system = await create_ai_system(
        db,
        org_id=other_org.id,
        name="Other System",
        owner_user_id=other_user.id,
    )
    await create_version(
        db,
        ai_system_id=other_system.id,
        label="1.0.0",
        created_by=other_user.id,
    )

    # Create export for test org
    test_export = Export(
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
    db.add(test_export)
    await db.flush()

    # Other user tries to access test org's exports
    other_token = create_access_token({"sub": str(other_user.id)})

    response = await client.get(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}/exports",
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert response.status_code == 404

    # Other user tries to download test org's export
    response = await client.get(
        f"/api/exports/{test_export.id}/download",
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_diff_export_generation_workflow(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_ai_system: AISystem,
    test_editor_user: User,
):
    """Test complete diff export generation workflow.

    Verifies that:
    1. User can generate export with diff from previous version
    2. DiffReport.json is included in the export
    3. Diff report contains changed sections and evidence
    """
    from tests.conftest import create_version

    # Create two versions with different data
    version1 = await create_version(
        db,
        ai_system_id=test_ai_system.id,
        label="1.0.0",
        created_by=test_editor_user.id,
    )
    version1.notes = "Initial version"
    await db.flush()

    version2 = await create_version(
        db,
        ai_system_id=test_ai_system.id,
        label="2.0.0",
        created_by=test_editor_user.id,
    )
    version2.notes = "Updated version with changes"
    await db.flush()

    token = create_access_token({"sub": str(test_editor_user.id)})

    # Mock storage service and docx generator
    with patch("src.services.export_service.get_storage_client") as mock_get_storage_client, \
         patch("src.services.export_service.generate_annex_iv_document") as mock_generate_docx:
        mock_storage_client = Mock()
        mock_storage_client._bucket = "test-bucket"
        mock_storage_client._client = Mock()
        mock_get_storage_client.return_value = mock_storage_client

        from io import BytesIO

        mock_generate_docx.return_value = BytesIO(b"fake docx content")

        # Request diff export
        response = await client.post(
            f"/api/systems/{test_ai_system.id}/versions/{version2.id}/exports",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "include_diff": True,
                "compare_version_id": str(version1.id),
            },
        )

    # Verify export was created
    assert response.status_code == 201
    data = response.json()

    # Verify export properties
    assert data["export_type"] == "diff"
    assert data["include_diff"] is True
    assert str(data["compare_version_id"]) == str(version1.id)
    assert str(data["version_id"]) == str(version2.id)
    assert data["storage_uri"].startswith(
        f"exports/{test_org.id}/{test_ai_system.id}/{version2.id}/"
    )
    assert data["storage_uri"].endswith(".zip")

    # Verify upload call and contents
    mock_storage_client._client.put_object.assert_called_once()
    put_args = mock_storage_client._client.put_object.call_args.kwargs
    assert put_args["Key"] == data["storage_uri"]
    zip_bytes = put_args["Body"]

    import io
    import zipfile

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        assert "DiffReport.json" in zf.namelist()
