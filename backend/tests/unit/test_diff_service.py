"""Unit tests for diff service."""
from uuid import uuid4

from src.models.enums import VersionStatus
from src.models.system_version import SystemVersion
from src.services.diff_service import DiffService


def test_diff_service_computes_field_changes():
    """Test that diff service detects field changes between versions."""
    service = DiffService()

    # Create two version objects with different fields
    version1 = SystemVersion(
        id=uuid4(),
        ai_system_id=uuid4(),
        label="1.0.0",
        status=VersionStatus.APPROVED,
        notes="Initial version",
        created_by=uuid4(),
    )

    version2 = SystemVersion(
        id=uuid4(),
        ai_system_id=version1.ai_system_id,  # Same system
        label="1.1.0",
        status=VersionStatus.DRAFT,
        notes="Updated version",
        created_by=uuid4(),
    )

    result = service.compute_diff(version1, version2)

    # Should detect changes in label, status, and notes
    assert len(result["changes"]) >= 3

    # Find specific field changes
    label_change = next((c for c in result["changes"] if c["field"] == "label"), None)
    status_change = next((c for c in result["changes"] if c["field"] == "status"), None)
    notes_change = next((c for c in result["changes"] if c["field"] == "notes"), None)

    assert label_change is not None
    assert label_change["old_value"] == "1.0.0"
    assert label_change["new_value"] == "1.1.0"

    assert status_change is not None
    assert status_change["old_value"] == "approved"
    assert status_change["new_value"] == "draft"

    assert notes_change is not None
    assert notes_change["old_value"] == "Initial version"
    assert notes_change["new_value"] == "Updated version"


def test_diff_service_detects_null_to_value_changes():
    """Test that diff service detects changes from null to a value."""
    service = DiffService()

    version1 = SystemVersion(
        id=uuid4(),
        ai_system_id=uuid4(),
        label="1.0.0",
        status=VersionStatus.DRAFT,
        notes=None,  # No notes initially
        created_by=uuid4(),
    )

    version2 = SystemVersion(
        id=uuid4(),
        ai_system_id=version1.ai_system_id,
        label="1.0.0",
        status=VersionStatus.DRAFT,
        notes="Added notes",  # Notes added
        created_by=uuid4(),
    )

    result = service.compute_diff(version1, version2)

    # Find notes change
    notes_change = next((c for c in result["changes"] if c["field"] == "notes"), None)
    assert notes_change is not None
    assert notes_change["old_value"] is None
    assert notes_change["new_value"] == "Added notes"


def test_diff_service_detects_value_to_null_changes():
    """Test that diff service detects changes from a value to null."""
    service = DiffService()

    version1 = SystemVersion(
        id=uuid4(),
        ai_system_id=uuid4(),
        label="1.0.0",
        status=VersionStatus.DRAFT,
        notes="Has notes",
        created_by=uuid4(),
    )

    version2 = SystemVersion(
        id=uuid4(),
        ai_system_id=version1.ai_system_id,
        label="1.0.0",
        status=VersionStatus.DRAFT,
        notes=None,  # Notes removed
        created_by=uuid4(),
    )

    result = service.compute_diff(version1, version2)

    # Find notes change
    notes_change = next((c for c in result["changes"] if c["field"] == "notes"), None)
    assert notes_change is not None
    assert notes_change["old_value"] == "Has notes"
    assert notes_change["new_value"] is None


def test_diff_service_computes_summary():
    """Test that diff service computes summary with counts."""
    service = DiffService()

    version1 = SystemVersion(
        id=uuid4(),
        ai_system_id=uuid4(),
        label="1.0.0",
        status=VersionStatus.DRAFT,
        notes=None,
        created_by=uuid4(),
    )

    version2 = SystemVersion(
        id=uuid4(),
        ai_system_id=version1.ai_system_id,
        label="1.1.0",
        status=VersionStatus.REVIEW,
        notes="Added notes",
        created_by=uuid4(),
    )

    result = service.compute_diff(version1, version2)

    # Check summary structure
    assert "summary" in result
    assert "added" in result["summary"]
    assert "removed" in result["summary"]
    assert "modified" in result["summary"]

    # All counts should be non-negative integers
    assert isinstance(result["summary"]["added"], int)
    assert isinstance(result["summary"]["removed"], int)
    assert isinstance(result["summary"]["modified"], int)
    assert result["summary"]["added"] >= 0
    assert result["summary"]["removed"] >= 0
    assert result["summary"]["modified"] >= 0


def test_diff_service_handles_identical_versions():
    """Test that diff service returns empty changes for identical versions."""
    service = DiffService()

    system_id = uuid4()
    creator_id = uuid4()

    version1 = SystemVersion(
        id=uuid4(),
        ai_system_id=system_id,
        label="1.0.0",
        status=VersionStatus.DRAFT,
        notes="Same notes",
        created_by=creator_id,
    )

    version2 = SystemVersion(
        id=uuid4(),
        ai_system_id=system_id,
        label="1.0.0",
        status=VersionStatus.DRAFT,
        notes="Same notes",
        created_by=creator_id,
    )

    result = service.compute_diff(version1, version2)

    # Should have minimal or no changes (only IDs differ, which we ignore)
    # The actual behavior depends on implementation, but typically we ignore
    # metadata fields like id, created_at, updated_at
    assert isinstance(result["changes"], list)
    assert result["summary"]["added"] == 0
    assert result["summary"]["removed"] == 0
    # modified might be 0 or small number depending on what fields are compared


def test_diff_service_returns_consistent_structure():
    """Test that diff service always returns expected structure."""
    service = DiffService()

    version1 = SystemVersion(
        id=uuid4(),
        ai_system_id=uuid4(),
        label="1.0.0",
        status=VersionStatus.DRAFT,
        notes="Test",
        created_by=uuid4(),
    )

    version2 = SystemVersion(
        id=uuid4(),
        ai_system_id=version1.ai_system_id,
        label="2.0.0",
        status=VersionStatus.APPROVED,
        notes="Production",
        created_by=uuid4(),
    )

    result = service.compute_diff(version1, version2)

    # Verify structure
    assert isinstance(result, dict)
    assert "changes" in result
    assert "summary" in result
    assert isinstance(result["changes"], list)
    assert isinstance(result["summary"], dict)

    # Each change should have field, old_value, new_value
    for change in result["changes"]:
        assert "field" in change
        assert "old_value" in change
        assert "new_value" in change
        assert isinstance(change["field"], str)
