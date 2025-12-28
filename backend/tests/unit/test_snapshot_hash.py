"""Unit tests for snapshot hash computation."""

import json
from datetime import date, datetime
from uuid import uuid4

from src.core.manifest import (
    EvidenceItem,
    SectionData,
    SystemInfo,
    SystemManifest,
    VersionInfo,
)
from src.services.snapshot_service import SnapshotService


class TestSnapshotHash:
    """Tests for deterministic snapshot hash computation."""

    def test_deterministic_hash_same_content_produces_same_hash(self):
        """Same manifest content MUST produce identical hash 100% of the time."""
        # Arrange
        system_id = uuid4()
        version_id = uuid4()

        manifest1 = SystemManifest(
            manifest_version="1.0",
            generated_at=datetime(2025, 1, 15, 10, 30, 0),
            system=SystemInfo(
                id=system_id,
                name="Test System",
                hr_use_case_type="recruitment",
                intended_purpose="Automated CV screening",
            ),
            version=VersionInfo(
                id=version_id,
                label="1.0.0",
                status="approved",
                release_date=date(2025, 1, 15),
            ),
            sections=[],
            evidence_index=[],
        )

        manifest2 = SystemManifest(
            manifest_version="1.0",
            generated_at=datetime(2025, 1, 15, 10, 30, 0),
            system=SystemInfo(
                id=system_id,
                name="Test System",
                hr_use_case_type="recruitment",
                intended_purpose="Automated CV screening",
            ),
            version=VersionInfo(
                id=version_id,
                label="1.0.0",
                status="approved",
                release_date=date(2025, 1, 15),
            ),
            sections=[],
            evidence_index=[],
        )

        service = SnapshotService()

        # Act
        hash1 = service.compute_hash_from_manifest(manifest1)
        hash2 = service.compute_hash_from_manifest(manifest2)

        # Assert
        assert hash1 == hash2, "Same content MUST produce identical hash"
        assert len(hash1) == 64, "SHA-256 hash should be 64 hex characters"

    def test_different_content_produces_different_hash(self):
        """Different manifest content MUST produce different hashes."""
        # Arrange
        system_id = uuid4()
        version_id = uuid4()

        manifest1 = SystemManifest(
            manifest_version="1.0",
            generated_at=datetime(2025, 1, 15, 10, 30, 0),
            system=SystemInfo(
                id=system_id,
                name="Test System",
                hr_use_case_type="recruitment",
                intended_purpose="Automated CV screening",
            ),
            version=VersionInfo(
                id=version_id,
                label="1.0.0",
                status="approved",
                release_date=date(2025, 1, 15),
            ),
            sections=[],
            evidence_index=[],
        )

        manifest2 = SystemManifest(
            manifest_version="1.0",
            generated_at=datetime(2025, 1, 15, 10, 30, 0),
            system=SystemInfo(
                id=system_id,
                name="Test System",
                hr_use_case_type="recruitment",
                intended_purpose="DIFFERENT PURPOSE",  # Changed
            ),
            version=VersionInfo(
                id=version_id,
                label="1.0.0",
                status="approved",
                release_date=date(2025, 1, 15),
            ),
            sections=[],
            evidence_index=[],
        )

        service = SnapshotService()

        # Act
        hash1 = service.compute_hash_from_manifest(manifest1)
        hash2 = service.compute_hash_from_manifest(manifest2)

        # Assert
        assert hash1 != hash2, "Different content MUST produce different hashes"

    def test_canonical_json_has_sorted_keys_no_whitespace(self):
        """Canonical JSON MUST have sorted keys and no whitespace for determinism."""
        # Arrange
        manifest = SystemManifest(
            manifest_version="1.0",
            generated_at=datetime(2025, 1, 15, 10, 30, 0),
            system=SystemInfo(
                id=uuid4(),
                name="Test System",
                hr_use_case_type="recruitment",
                intended_purpose="CV screening",
            ),
            version=VersionInfo(
                id=uuid4(),
                label="1.0.0",
                status="approved",
                release_date=date(2025, 1, 15),
            ),
            sections=[],
            evidence_index=[],
        )

        service = SnapshotService()

        # Act
        canonical = service.to_canonical_json(manifest)

        # Assert
        # Should be compact (no extra whitespace)
        assert "\n" not in canonical, "Should have no newlines"
        assert "  " not in canonical, "Should have no extra spaces"

        # Should be valid JSON
        parsed = json.loads(canonical)
        assert "manifest_version" in parsed
        assert "system" in parsed
        assert "version" in parsed

        # Keys should be sorted (verify by checking string order)
        # In sorted order: evidence_index, generated_at, manifest_version, sections, system, version
        assert canonical.index('"evidence_index"') < canonical.index('"generated_at"')
        assert canonical.index('"generated_at"') < canonical.index('"manifest_version"')
        assert canonical.index('"manifest_version"') < canonical.index('"sections"')
        assert canonical.index('"sections"') < canonical.index('"system"')
        assert canonical.index('"system"') < canonical.index('"version"')

    def test_hash_with_sections_and_evidence(self):
        """Hash computation MUST work with sections and evidence data."""
        # Arrange
        manifest = SystemManifest(
            manifest_version="1.0",
            generated_at=datetime(2025, 1, 15, 10, 30, 0),
            system=SystemInfo(
                id=uuid4(),
                name="Test System",
                hr_use_case_type="recruitment",
                intended_purpose="CV screening",
            ),
            version=VersionInfo(
                id=uuid4(),
                label="1.0.0",
                status="approved",
                release_date=date(2025, 1, 15),
            ),
            sections=[
                SectionData(
                    key="section1",
                    content={"field1": "value1", "field2": "value2"},
                    evidence_refs=["ev1", "ev2"],
                )
            ],
            evidence_index=[
                EvidenceItem(
                    id="ev1",
                    title="Evidence 1",
                    type="document",
                    checksum="abc123",
                )
            ],
        )

        service = SnapshotService()

        # Act
        hash_result = service.compute_hash_from_manifest(manifest)

        # Assert
        assert len(hash_result) == 64
        assert hash_result.isalnum(), "Hash should be hexadecimal"

    def test_hash_determinism_with_complex_nested_data(self):
        """Hash MUST be deterministic even with complex nested structures."""
        # Arrange
        system_id = uuid4()
        version_id = uuid4()

        # Create two manifests with same complex data in different object instances
        def create_manifest():
            return SystemManifest(
                manifest_version="1.0",
                generated_at=datetime(2025, 1, 15, 10, 30, 0),
                system=SystemInfo(
                    id=system_id,
                    name="Complex System",
                    hr_use_case_type="recruitment",
                    intended_purpose="Multi-stage hiring",
                ),
                version=VersionInfo(
                    id=version_id,
                    label="2.0.0",
                    status="approved",
                    release_date=date(2025, 1, 15),
                ),
                sections=[
                    SectionData(
                        key="sec1",
                        content={
                            "nested": {"deep": {"value": 123}},
                            "array": [1, 2, 3],
                            "text": "Some text",
                        },
                        evidence_refs=["e1", "e2"],
                    ),
                    SectionData(
                        key="sec2",
                        content={"simple": "value"},
                        evidence_refs=[],
                    ),
                ],
                evidence_index=[
                    EvidenceItem(
                        id="e1",
                        title="Evidence One",
                        type="document",
                        checksum="hash1",
                    ),
                    EvidenceItem(
                        id="e2",
                        title="Evidence Two",
                        type="image",
                        checksum="hash2",
                    ),
                ],
            )

        manifest1 = create_manifest()
        manifest2 = create_manifest()

        service = SnapshotService()

        # Act
        hash1 = service.compute_hash_from_manifest(manifest1)
        hash2 = service.compute_hash_from_manifest(manifest2)

        # Assert
        assert hash1 == hash2, "Complex nested data MUST produce identical hash"

    def test_to_canonical_json_sorts_nested_keys(self):
        """Canonical JSON MUST sort keys at all nesting levels."""
        # Arrange
        manifest = SystemManifest(
            manifest_version="1.0",
            generated_at=datetime(2025, 1, 15, 10, 30, 0),
            system=SystemInfo(
                id=uuid4(),
                name="Test",
                hr_use_case_type="recruitment",
                intended_purpose="Test",
            ),
            version=VersionInfo(
                id=uuid4(),
                label="1.0.0",
                status="draft",
                release_date=None,
            ),
            sections=[
                SectionData(
                    key="sec1",
                    content={
                        "zebra": "last",
                        "apple": "first",
                        "middle": "center",
                    },
                    evidence_refs=[],
                )
            ],
            evidence_index=[],
        )

        service = SnapshotService()

        # Act
        canonical = service.to_canonical_json(manifest)

        # Assert
        # In the content object, keys should be sorted: apple, middle, zebra
        content_start = canonical.index('"content":{')
        apple_pos = canonical.index('"apple"', content_start)
        middle_pos = canonical.index('"middle"', content_start)
        zebra_pos = canonical.index('"zebra"', content_start)

        assert apple_pos < middle_pos < zebra_pos, "Nested keys must be sorted"
