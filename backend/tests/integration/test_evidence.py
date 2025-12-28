"""Integration tests for evidence operations."""

from unittest.mock import Mock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import create_access_token
from src.models.organization import Organization
from src.models.user import User


@pytest.mark.asyncio
async def test_full_upload_evidence_flow(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """Test complete upload evidence flow: get URL -> upload -> create evidence."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    with patch("src.api.routes.evidence.get_storage_service") as mock_storage_route:
        with patch("src.services.evidence_service.EvidenceService._validate_file_upload_metadata"):
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
                "checksum_sha256": "initial-checksum",
            }
            mock_storage.compute_checksum.return_value = "a" * 64  # Valid SHA-256 length
            mock_storage_route.return_value = mock_storage

            # Step 1: Get presigned upload URL
            url_response = await client.post(
                "/api/evidence/upload-url",
                json={
                    "filename": "compliance_report.pdf",
                    "mime_type": "application/pdf",
                },
                headers={"Authorization": f"Bearer {token}"},
            )

            assert url_response.status_code == 200
            url_data = url_response.json()
            assert "upload_url" in url_data
            assert "storage_uri" in url_data
            returned_storage_uri = url_data["storage_uri"]

            # Step 2: (Client uploads file to presigned URL - simulated)
            # In reality, client would PUT file to upload_url here

            # Step 3: Create evidence item with uploaded file
            create_response = await client.post(
                "/api/evidence",
                json={
                    "type": "upload",
                    "title": "Compliance Report 2025",
                    "description": "Annual compliance documentation",
                    "tags": ["compliance", "report", "2025"],
                    "classification": "internal",
                    "type_metadata": {
                        "storage_uri": returned_storage_uri,
                        "checksum_sha256": "a" * 64,
                        "file_size": 2048,
                        "mime_type": "application/pdf",
                        "original_filename": "compliance_report.pdf",
                    },
                },
                headers={"Authorization": f"Bearer {token}"},
            )

            assert create_response.status_code == 201
            evidence = create_response.json()
            assert evidence["title"] == "Compliance Report 2025"
            assert evidence["type"] == "upload"
            assert "id" in evidence

            # Step 4: Verify evidence appears in list
            list_response = await client.get(
                "/api/evidence",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert list_response.status_code == 200
            data = list_response.json()
            assert data["total"] == 1
            assert len(data["items"]) == 1
            assert data["items"][0]["id"] == evidence["id"]


@pytest.mark.asyncio
async def test_create_different_evidence_types(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """Test creating different types of evidence items with full validation."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create URL evidence
    url_response = await client.post(
        "/api/evidence",
        json={
            "type": "url",
            "title": "EU AI Act Documentation",
            "description": "Official EU AI Act website",
            "tags": ["ai-act", "regulation"],
            "classification": "public",
            "type_metadata": {
                "url": "https://artificial-intelligence-act.ec.europa.eu",
                "accessed_at": "2025-12-25T10:00:00Z",
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert url_response.status_code == 201
    url_evidence = url_response.json()
    assert url_evidence["type"] == "url"
    assert "url" in url_evidence["type_metadata"]
    assert "accessed_at" in url_evidence["type_metadata"]

    # Create Git evidence
    git_response = await client.post(
        "/api/evidence",
        json={
            "type": "git",
            "title": "Model Training Code",
            "description": "ML model training implementation",
            "tags": ["code", "ml", "training"],
            "classification": "confidential",
            "type_metadata": {
                "repo_url": "https://github.com/org/ml-models",
                "commit_hash": "abc123def4567890abcdef1234567890abcdef12",
                "branch": "main",
                "file_path": "training/model.py",
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert git_response.status_code == 201
    git_evidence = git_response.json()
    assert git_evidence["type"] == "git"
    assert git_evidence["type_metadata"]["repo_url"] == "https://github.com/org/ml-models"
    assert (
        git_evidence["type_metadata"]["commit_hash"] == "abc123def4567890abcdef1234567890abcdef12"
    )
    assert git_evidence["type_metadata"]["branch"] == "main"
    assert git_evidence["type_metadata"]["file_path"] == "training/model.py"

    # Create Ticket evidence
    ticket_response = await client.post(
        "/api/evidence",
        json={
            "type": "ticket",
            "title": "Bias Mitigation Issue",
            "description": "Jira ticket for bias mitigation feature",
            "tags": ["bias", "jira"],
            "classification": "internal",
            "type_metadata": {
                "ticket_system": "jira",
                "ticket_id": "AI-123",
                "ticket_url": "https://jira.company.com/browse/AI-123",
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert ticket_response.status_code == 201
    ticket_evidence = ticket_response.json()
    assert ticket_evidence["type"] == "ticket"
    assert ticket_evidence["type_metadata"]["ticket_system"] == "jira"
    assert ticket_evidence["type_metadata"]["ticket_id"] == "AI-123"
    assert (
        ticket_evidence["type_metadata"]["ticket_url"] == "https://jira.company.com/browse/AI-123"
    )

    # Create Note evidence
    note_response = await client.post(
        "/api/evidence",
        json={
            "type": "note",
            "title": "Risk Assessment Notes",
            "description": "Internal notes from risk assessment meeting",
            "tags": ["risk", "notes"],
            "classification": "confidential",
            "type_metadata": {
                "content": "Discussed potential risks and mitigation strategies.",
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert note_response.status_code == 201
    note_evidence = note_response.json()
    assert note_evidence["type"] == "note"
    assert (
        note_evidence["type_metadata"]["content"]
        == "Discussed potential risks and mitigation strategies."
    )

    # Verify all evidence items are in list
    list_response = await client.get(
        "/api/evidence",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_response.status_code == 200
    data = list_response.json()
    assert data["total"] == 4
    assert len(data["items"]) == 4

    # Verify types
    types = {item["type"] for item in data["items"]}
    assert types == {"url", "git", "ticket", "note"}


@pytest.mark.asyncio
async def test_filter_evidence_by_type(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """Test filtering evidence list by type."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create multiple evidence types
    await client.post(
        "/api/evidence",
        json={
            "type": "note",
            "title": "Note 1",
            "type_metadata": {"content": "Note content"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    await client.post(
        "/api/evidence",
        json={
            "type": "url",
            "title": "URL 1",
            "type_metadata": {"url": "https://example.com", "title": "Example"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    await client.post(
        "/api/evidence",
        json={
            "type": "note",
            "title": "Note 2",
            "type_metadata": {"content": "Another note"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    # Filter by note type
    note_response = await client.get(
        "/api/evidence?type=note",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert note_response.status_code == 200
    data = note_response.json()
    notes = data["items"]
    assert data["total"] == 2
    assert len(notes) == 2
    assert all(item["type"] == "note" for item in notes)

    # Filter by url type
    url_response = await client.get(
        "/api/evidence?type=url",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert url_response.status_code == 200
    data = url_response.json()
    urls = data["items"]
    assert data["total"] == 1
    assert len(urls) == 1
    assert urls[0]["type"] == "url"


@pytest.mark.asyncio
async def test_evidence_delete_flow(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """Test evidence deletion removes item from list."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create evidence
    create_response = await client.post(
        "/api/evidence",
        json={
            "type": "note",
            "title": "Temporary Note",
            "type_metadata": {"content": "To be deleted"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    evidence_id = create_response.json()["id"]

    # Verify it exists
    get_response = await client.get(
        f"/api/evidence/{evidence_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_response.status_code == 200

    # Delete evidence
    delete_response = await client.delete(
        f"/api/evidence/{evidence_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert delete_response.status_code == 204

    # Verify it's gone
    get_after_delete = await client.get(
        f"/api/evidence/{evidence_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_after_delete.status_code == 404

    # Verify not in list
    list_response = await client.get(
        "/api/evidence",
        headers={"Authorization": f"Bearer {token}"},
    )
    data = list_response.json()
    assert data["total"] == 0
    assert len(data["items"]) == 0


@pytest.mark.asyncio
async def test_evidence_org_isolation(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """Test that evidence items are isolated by organization."""
    from src.models.enums import UserRole
    from src.models.organization import Organization as OrgModel
    from tests.conftest import create_user

    # Create second organization with user
    org2 = OrgModel(name="Second Org")
    db.add(org2)
    await db.flush()

    user2 = await create_user(
        db,
        org_id=org2.id,
        email="editor2@test.com",
        role=UserRole.EDITOR,
    )
    await db.commit()

    token1 = create_access_token({"sub": str(test_editor_user.id)})
    token2 = create_access_token({"sub": str(user2.id)})

    # User 1 creates evidence
    await client.post(
        "/api/evidence",
        json={
            "type": "note",
            "title": "Org 1 Evidence",
            "type_metadata": {"content": "Private to org 1"},
        },
        headers={"Authorization": f"Bearer {token1}"},
    )

    # User 2 creates evidence
    await client.post(
        "/api/evidence",
        json={
            "type": "note",
            "title": "Org 2 Evidence",
            "type_metadata": {"content": "Private to org 2"},
        },
        headers={"Authorization": f"Bearer {token2}"},
    )

    # User 1 should only see their org's evidence
    list1_response = await client.get(
        "/api/evidence",
        headers={"Authorization": f"Bearer {token1}"},
    )
    data1 = list1_response.json()
    assert data1["total"] == 1
    assert len(data1["items"]) == 1
    assert data1["items"][0]["title"] == "Org 1 Evidence"

    # User 2 should only see their org's evidence
    list2_response = await client.get(
        "/api/evidence",
        headers={"Authorization": f"Bearer {token2}"},
    )
    data2 = list2_response.json()
    assert data2["total"] == 1
    assert len(data2["items"]) == 1
    assert data2["items"][0]["title"] == "Org 2 Evidence"


@pytest.mark.asyncio
async def test_evidence_pagination(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """Test evidence list pagination with limit and offset."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create 5 evidence items
    for i in range(5):
        await client.post(
            "/api/evidence",
            json={
                "type": "note",
                "title": f"Evidence {i + 1}",
                "type_metadata": {"content": f"Content {i + 1}"},
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    # Get first 2 items
    page1_response = await client.get(
        "/api/evidence?limit=2&offset=0",
        headers={"Authorization": f"Bearer {token}"},
    )
    page1_data = page1_response.json()
    assert len(page1_data["items"]) == 2

    # Get next 2 items
    page2_response = await client.get(
        "/api/evidence?limit=2&offset=2",
        headers={"Authorization": f"Bearer {token}"},
    )
    page2_data = page2_response.json()
    assert len(page2_data["items"]) == 2

    # Get last item
    page3_response = await client.get(
        "/api/evidence?limit=2&offset=4",
        headers={"Authorization": f"Bearer {token}"},
    )
    page3_data = page3_response.json()
    assert len(page3_data["items"]) == 1

    # Verify no duplicates
    all_ids = [
        item["id"] for item in (page1_data["items"] + page2_data["items"] + page3_data["items"])
    ]
    assert len(all_ids) == len(set(all_ids))  # All unique


@pytest.mark.asyncio
async def test_url_type_validation(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """Test URL type metadata validation requirements."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Valid URL with all fields
    response = await client.post(
        "/api/evidence",
        json={
            "type": "url",
            "title": "Test URL",
            "type_metadata": {
                "url": "https://example.com/document",
                "accessed_at": "2025-12-25T10:00:00Z",
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201

    # Valid URL without optional accessed_at
    response = await client.post(
        "/api/evidence",
        json={
            "type": "url",
            "title": "Test URL 2",
            "type_metadata": {
                "url": "https://example.com/other",
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201

    # Invalid: missing URL
    response = await client.post(
        "/api/evidence",
        json={
            "type": "url",
            "title": "Missing URL",
            "type_metadata": {},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422

    # Invalid: malformed URL
    response = await client.post(
        "/api/evidence",
        json={
            "type": "url",
            "title": "Bad URL",
            "type_metadata": {
                "url": "not-a-url",
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_git_type_validation(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """Test Git type metadata validation requirements."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Valid Git with all fields
    response = await client.post(
        "/api/evidence",
        json={
            "type": "git",
            "title": "Git Evidence",
            "type_metadata": {
                "repo_url": "https://github.com/org/repo",
                "commit_hash": "abc123def4567890abcdef1234567890abcdef12",
                "file_path": "src/main.py",
                "branch": "develop",
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    # Commit hash should be normalized to lowercase
    assert data["type_metadata"]["commit_hash"] == "abc123def4567890abcdef1234567890abcdef12"

    # Valid Git with only required fields
    response = await client.post(
        "/api/evidence",
        json={
            "type": "git",
            "title": "Git Evidence 2",
            "type_metadata": {
                "repo_url": "https://github.com/org/repo2",
                "commit_hash": "1234567890abcdef1234567890abcdef12345678",
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201

    # Invalid: missing commit_hash
    response = await client.post(
        "/api/evidence",
        json={
            "type": "git",
            "title": "Missing Commit",
            "type_metadata": {
                "repo_url": "https://github.com/org/repo",
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422

    # Invalid: commit_hash too short
    response = await client.post(
        "/api/evidence",
        json={
            "type": "git",
            "title": "Short Commit",
            "type_metadata": {
                "repo_url": "https://github.com/org/repo",
                "commit_hash": "abc123",
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422

    # Invalid: commit_hash not hex
    response = await client.post(
        "/api/evidence",
        json={
            "type": "git",
            "title": "Bad Commit Hash",
            "type_metadata": {
                "repo_url": "https://github.com/org/repo",
                "commit_hash": "gggggggggggggggggggggggggggggggggggggggg",
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_ticket_type_validation(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """Test Ticket type metadata validation requirements."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Valid Ticket with all fields
    response = await client.post(
        "/api/evidence",
        json={
            "type": "ticket",
            "title": "Ticket Evidence",
            "type_metadata": {
                "ticket_id": "JIRA-123",
                "ticket_system": "jira",
                "ticket_url": "https://jira.example.com/browse/JIRA-123",
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201

    # Valid Ticket without optional ticket_url
    response = await client.post(
        "/api/evidence",
        json={
            "type": "ticket",
            "title": "Ticket Evidence 2",
            "type_metadata": {
                "ticket_id": "GH-456",
                "ticket_system": "github",
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201

    # Invalid: missing ticket_id
    response = await client.post(
        "/api/evidence",
        json={
            "type": "ticket",
            "title": "Missing Ticket ID",
            "type_metadata": {
                "ticket_system": "jira",
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422

    # Invalid: missing ticket_system
    response = await client.post(
        "/api/evidence",
        json={
            "type": "ticket",
            "title": "Missing System",
            "type_metadata": {
                "ticket_id": "JIRA-789",
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_note_type_validation(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """Test Note type metadata validation requirements."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Valid Note
    response = await client.post(
        "/api/evidence",
        json={
            "type": "note",
            "title": "Note Evidence",
            "type_metadata": {
                "content": "This is a note with some content.",
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201

    # Valid Note with markdown content
    response = await client.post(
        "/api/evidence",
        json={
            "type": "note",
            "title": "Markdown Note",
            "type_metadata": {
                "content": "# Heading\n\n- List item 1\n- List item 2",
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201

    # Invalid: missing content
    response = await client.post(
        "/api/evidence",
        json={
            "type": "note",
            "title": "Missing Content",
            "type_metadata": {},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422

    # Invalid: empty content
    response = await client.post(
        "/api/evidence",
        json={
            "type": "note",
            "title": "Empty Content",
            "type_metadata": {
                "content": "",
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_full_text_search_on_title_and_description(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """Test full-text search functionality across title and description fields."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create diverse evidence items
    evidence_items = [
        {
            "type": "note",
            "title": "Risk Assessment Report",
            "description": "Comprehensive risk assessment and compliance review for AI system deployment",
            "tags": ["risk", "compliance"],
            "type_metadata": {"content": "Risk analysis content"},
        },
        {
            "type": "note",
            "title": "GDPR Compliance Guide",
            "description": "Guidelines for data protection and privacy compliance",
            "tags": ["gdpr", "privacy"],
            "type_metadata": {"content": "Privacy guidelines"},
        },
        {
            "type": "url",
            "title": "EU AI Act Documentation",
            "description": "Official EU AI Act website with regulatory requirements",
            "tags": ["regulation", "eu"],
            "type_metadata": {"url": "https://ai-act.eu"},
        },
        {
            "type": "note",
            "title": "Model Training Logs",
            "description": "Training metrics and performance data for ML model",
            "tags": ["ml", "training"],
            "type_metadata": {"content": "Training data"},
        },
        {
            "type": "note",
            "title": "Bias Mitigation Strategy",
            "description": "Approach to identify and mitigate algorithmic bias in recruitment",
            "tags": ["bias", "fairness"],
            "type_metadata": {"content": "Bias analysis"},
        },
    ]

    for item in evidence_items:
        await client.post(
            "/api/evidence",
            json=item,
            headers={"Authorization": f"Bearer {token}"},
        )

    # Test 1: Search for "risk" (should match title and description)
    response = await client.get(
        "/api/evidence?search=risk",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert "Risk Assessment" in data["items"][0]["title"]

    # Test 2: Search for "compliance" (should match multiple items)
    response = await client.get(
        "/api/evidence?search=compliance",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    titles = {item["title"] for item in data["items"]}
    assert "Risk Assessment Report" in titles
    assert "GDPR Compliance Guide" in titles

    # Test 3: Search for "training" (should match description)
    response = await client.get(
        "/api/evidence?search=training",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert "Model Training Logs" in data["items"][0]["title"]

    # Test 4: Search for "bias" (should match title)
    response = await client.get(
        "/api/evidence?search=bias",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert "Bias Mitigation" in data["items"][0]["title"]

    # Test 5: Multi-word search "AI system"
    response = await client.get(
        "/api/evidence?search=AI system",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    # Should match items with "AI" and "system" in title or description

    # Test 6: Search with no results
    response = await client.get(
        "/api/evidence?search=nonexistentterm",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert len(data["items"]) == 0

    # Test 7: Combine search with type filter
    response = await client.get(
        "/api/evidence?search=compliance&type=url",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0  # "compliance" is not in URL type evidence

    # Test 8: Combine search with tag filter
    response = await client.get(
        "/api/evidence?search=compliance&tags=gdpr",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert "GDPR Compliance" in data["items"][0]["title"]

    # Test 9: Test pagination with search
    response = await client.get(
        "/api/evidence?search=compliance&limit=1&offset=0",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2  # Total count remains 2
    assert len(data["items"]) == 1  # But only 1 item returned
    assert data["limit"] == 1
    assert data["offset"] == 0

    # Test 10: Verify response structure
    response = await client.get(
        "/api/evidence",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data
    assert isinstance(data["items"], list)
    assert data["total"] == 5
    assert data["limit"] == 100
    assert data["offset"] == 0


@pytest.mark.asyncio
async def test_orphaned_evidence_filter(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system,
    test_version,
):
    """Test filtering evidence by orphaned status (no mappings vs has mappings)."""
    from src.models.enums import MappingStrength, MappingTargetType
    from tests.conftest import create_evidence_item, create_evidence_mapping

    token = create_access_token({"sub": str(test_editor_user.id)})

    # Create 4 evidence items
    await create_evidence_item(
        db,
        org_id=test_org.id,
        type="note",
        title="Orphaned Evidence 1",
        description="This evidence has no mappings",
        tags=["orphan"],
        type_metadata={"content": "No mappings"},
        created_by=test_editor_user.id,
    )

    evidence2 = await create_evidence_item(
        db,
        org_id=test_org.id,
        type="note",
        title="Mapped Evidence 1",
        description="This evidence has mappings",
        tags=["mapped"],
        type_metadata={"content": "Has mappings"},
        created_by=test_editor_user.id,
    )

    await create_evidence_item(
        db,
        org_id=test_org.id,
        type="note",
        title="Orphaned Evidence 2",
        description="Another orphaned evidence",
        tags=["orphan"],
        type_metadata={"content": "No mappings either"},
        created_by=test_editor_user.id,
    )

    evidence4 = await create_evidence_item(
        db,
        org_id=test_org.id,
        type="note",
        title="Mapped Evidence 2",
        description="This evidence also has mappings",
        tags=["mapped"],
        type_metadata={"content": "Has multiple mappings"},
        created_by=test_editor_user.id,
    )

    await db.commit()

    # Create mappings for evidence2 and evidence4
    await create_evidence_mapping(
        db,
        evidence_id=evidence2.id,
        version_id=test_version.id,
        target_type=MappingTargetType.SECTION,
        target_key="ANNEX4.RISK_MANAGEMENT",
        strength=MappingStrength.STRONG,
        created_by=test_editor_user.id,
    )

    await create_evidence_mapping(
        db,
        evidence_id=evidence4.id,
        version_id=test_version.id,
        target_type=MappingTargetType.SECTION,
        target_key="ANNEX4.DATA_GOVERNANCE",
        strength=MappingStrength.MEDIUM,
        created_by=test_editor_user.id,
    )

    await create_evidence_mapping(
        db,
        evidence_id=evidence4.id,
        version_id=test_version.id,
        target_type=MappingTargetType.FIELD,
        target_key="hr_use_case_type",
        strength=MappingStrength.WEAK,
        created_by=test_editor_user.id,
    )

    await db.commit()

    # Test 1: Get all evidence (no orphaned filter)
    response = await client.get(
        "/api/evidence",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 4
    assert len(data["items"]) == 4

    # Verify usage_count is populated
    items_by_title = {item["title"]: item for item in data["items"]}
    assert items_by_title["Orphaned Evidence 1"]["usage_count"] == 0
    assert items_by_title["Orphaned Evidence 2"]["usage_count"] == 0
    assert items_by_title["Mapped Evidence 1"]["usage_count"] == 1
    assert items_by_title["Mapped Evidence 2"]["usage_count"] == 2

    # Test 2: Filter for orphaned evidence only (orphaned=true)
    response = await client.get(
        "/api/evidence?orphaned=true",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2

    # Verify only orphaned evidence is returned
    titles = {item["title"] for item in data["items"]}
    assert titles == {"Orphaned Evidence 1", "Orphaned Evidence 2"}

    # Verify all have usage_count of 0
    for item in data["items"]:
        assert item["usage_count"] == 0

    # Test 3: Filter for mapped evidence only (orphaned=false)
    response = await client.get(
        "/api/evidence?orphaned=false",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2

    # Verify only mapped evidence is returned
    titles = {item["title"] for item in data["items"]}
    assert titles == {"Mapped Evidence 1", "Mapped Evidence 2"}

    # Verify all have usage_count > 0
    for item in data["items"]:
        assert item["usage_count"] > 0

    # Test 4: Combine orphaned filter with search
    response = await client.get(
        "/api/evidence?orphaned=true&search=Evidence 1",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Orphaned Evidence 1"

    # Test 5: Combine orphaned filter with tags
    response = await client.get(
        "/api/evidence?orphaned=true&tags=orphan",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2

    # Test 6: Combine orphaned=false with tags
    response = await client.get(
        "/api/evidence?orphaned=false&tags=mapped",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2

    # Test 7: Verify pagination works with orphaned filter
    response = await client.get(
        "/api/evidence?orphaned=true&limit=1&offset=0",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2  # Total count remains 2
    assert len(data["items"]) == 1  # But only 1 item returned
    assert data["limit"] == 1
    assert data["offset"] == 0


@pytest.mark.asyncio
async def test_duplicate_checksum_detection(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """Test that duplicate checksums are detected and reported as warnings."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    with patch("src.api.routes.evidence.get_storage_service") as mock_storage_route:
        with patch("src.services.evidence_service.EvidenceService._validate_file_upload_metadata"):
            # Mock storage service
            mock_storage = Mock()
            storage_uri_1 = f"evidence/{test_org.id}/2025/12/file1.pdf"
            storage_uri_2 = f"evidence/{test_org.id}/2025/12/file2.pdf"

            # Same checksum for both files (duplicate content)
            duplicate_checksum = "a" * 64

            mock_storage.file_exists.return_value = True
            mock_storage.get_file_metadata.return_value = {
                "file_size": 2048,
                "mime_type": "application/pdf",
            }
            mock_storage.compute_checksum.return_value = duplicate_checksum
            mock_storage_route.return_value = mock_storage

            # Step 1: Upload first file
            first_response = await client.post(
                "/api/evidence",
                json={
                    "type": "upload",
                    "title": "First Upload",
                    "type_metadata": {
                        "storage_uri": storage_uri_1,
                        "checksum_sha256": duplicate_checksum,
                        "file_size": 2048,
                        "mime_type": "application/pdf",
                        "original_filename": "file1.pdf",
                    },
                },
                headers={"Authorization": f"Bearer {token}"},
            )

            assert first_response.status_code == 201
            first_evidence = first_response.json()
            first_evidence_id = first_evidence["id"]
            # First upload should not have duplicate warning
            assert first_evidence.get("duplicate_of") is None

            # Step 2: Upload second file with same checksum
            second_response = await client.post(
                "/api/evidence",
                json={
                    "type": "upload",
                    "title": "Second Upload (Duplicate)",
                    "type_metadata": {
                        "storage_uri": storage_uri_2,
                        "checksum_sha256": duplicate_checksum,
                        "file_size": 2048,
                        "mime_type": "application/pdf",
                        "original_filename": "file2.pdf",
                    },
                },
                headers={"Authorization": f"Bearer {token}"},
            )

            # Second upload should succeed but include duplicate warning
            assert second_response.status_code == 201
            second_evidence = second_response.json()

            # Should have duplicate_of field pointing to first evidence
            assert "duplicate_of" in second_evidence
            assert second_evidence["duplicate_of"] == first_evidence_id

            # Both evidence items should exist in database
            list_response = await client.get(
                "/api/evidence?type=upload",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert list_response.status_code == 200
            data = list_response.json()
            assert data["total"] == 2

            # Verify checksums match
            checksums = [item["type_metadata"]["checksum_sha256"] for item in data["items"]]
            assert checksums[0] == checksums[1] == duplicate_checksum
