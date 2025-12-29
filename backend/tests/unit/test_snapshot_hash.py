"""Unit tests for snapshot hash computation."""

import json
from datetime import date, datetime
from uuid import UUID, uuid4

from src.core.manifest import (
    AISystemInfo,
    AnnexSectionData,
    EvidenceIndexItem,
    OrgInfo,
    SystemManifest,
    SystemVersionInfo,
)
from src.services.snapshot_service import SnapshotService


class TestSnapshotHash:
    """Tests for deterministic snapshot hash computation."""

    def _make_minimal_manifest(
        self,
        *,
        intended_purpose: str = "Automated CV screening",
        org_id: UUID | None = None,
        system_id: UUID | None = None,
        version_id: UUID | None = None,
        ts: datetime | None = None,
    ) -> SystemManifest:
        org_id = org_id or uuid4()
        system_id = system_id or uuid4()
        version_id = version_id or uuid4()
        ts = ts or datetime(2025, 1, 15, 10, 30, 0)

        return SystemManifest(
            manifest_version="1.0",
            generated_at=ts,
            snapshot_hash=None,
            org=OrgInfo(id=org_id, name="Test Org"),
            ai_system=AISystemInfo(
                id=system_id,
                name="Test System",
                hr_use_case_type="recruitment",
                intended_purpose=intended_purpose,
            ),
            system_version=SystemVersionInfo(
                id=version_id,
                label="1.0.0",
                status="approved",
                release_date=date(2025, 1, 15),
                created_at=ts,
                updated_at=ts,
            ),
            high_risk_assessment=None,
            annex_sections={},
            evidence_index={},
            mappings=[],
        )

    def test_deterministic_hash_same_content_produces_same_hash(self):
        """Same manifest content MUST produce identical hash 100% of the time."""
        # Arrange
        org_id = uuid4()
        system_id = uuid4()
        version_id = uuid4()
        ts = datetime(2025, 1, 15, 10, 30, 0)

        manifest1 = self._make_minimal_manifest(
            intended_purpose="Automated CV screening",
            org_id=org_id,
            system_id=system_id,
            version_id=version_id,
            ts=ts,
        )
        manifest2 = self._make_minimal_manifest(
            intended_purpose="Automated CV screening",
            org_id=org_id,
            system_id=system_id,
            version_id=version_id,
            ts=ts,
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
        org_id = uuid4()
        system_id = uuid4()
        version_id = uuid4()
        ts = datetime(2025, 1, 15, 10, 30, 0)

        manifest1 = self._make_minimal_manifest(
            intended_purpose="Automated CV screening",
            org_id=org_id,
            system_id=system_id,
            version_id=version_id,
            ts=ts,
        )
        manifest2 = self._make_minimal_manifest(
            intended_purpose="DIFFERENT PURPOSE",
            org_id=org_id,
            system_id=system_id,
            version_id=version_id,
            ts=ts,
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
        manifest = self._make_minimal_manifest(intended_purpose="CV screening")

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
        assert "ai_system" in parsed
        assert "system_version" in parsed

        # Keys should be sorted (verify by checking string order)
        assert canonical.index('"ai_system"') < canonical.index('"annex_sections"')
        assert canonical.index('"annex_sections"') < canonical.index('"evidence_index"')
        assert canonical.index('"evidence_index"') < canonical.index('"generated_at"')
        assert canonical.index('"generated_at"') < canonical.index('"high_risk_assessment"')
        assert canonical.index('"high_risk_assessment"') < canonical.index('"manifest_version"')
        assert canonical.index('"manifest_version"') < canonical.index('"mappings"')
        assert canonical.index('"mappings"') < canonical.index('"org"')
        assert canonical.index('"org"') < canonical.index('"system_version"')

    def test_hash_with_sections_and_evidence(self):
        """Hash computation MUST work with sections and evidence data."""
        # Arrange
        manifest = self._make_minimal_manifest(intended_purpose="CV screening")
        manifest.annex_sections["section1"] = AnnexSectionData(
            content={"field1": "value1", "field2": "value2"},
            evidence_refs=["ev1", "ev2"],
        )
        manifest.evidence_index["ev1"] = EvidenceIndexItem(
            id="ev1",
            title="Evidence 1",
            type="document",
            classification="public",
            tags=[],
            type_metadata={},
            checksum="abc123",
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
        org_id = uuid4()
        system_id = uuid4()
        version_id = uuid4()
        ts = datetime(2025, 1, 15, 10, 30, 0)

        # Create two manifests with same complex data in different object instances
        def create_manifest():
            manifest = self._make_minimal_manifest(
                intended_purpose="Multi-stage hiring",
                org_id=org_id,
                system_id=system_id,
                version_id=version_id,
                ts=ts,
            )
            manifest.system_version.label = "2.0.0"
            manifest.annex_sections["sec1"] = AnnexSectionData(
                content={
                    "nested": {"deep": {"value": 123}},
                    "array": [1, 2, 3],
                    "text": "Some text",
                },
                evidence_refs=["e1", "e2"],
            )
            manifest.annex_sections["sec2"] = AnnexSectionData(
                content={"simple": "value"},
                evidence_refs=[],
            )
            manifest.evidence_index["e1"] = EvidenceIndexItem(
                id="e1",
                title="Evidence One",
                type="document",
                classification="public",
                tags=[],
                type_metadata={},
                checksum="hash1",
            )
            manifest.evidence_index["e2"] = EvidenceIndexItem(
                id="e2",
                title="Evidence Two",
                type="image",
                classification="public",
                tags=[],
                type_metadata={},
                checksum="hash2",
            )
            return manifest

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
        manifest = self._make_minimal_manifest(intended_purpose="Test")
        manifest.system_version.status = "draft"
        manifest.system_version.release_date = None
        manifest.annex_sections["sec1"] = AnnexSectionData(
            content={
                "zebra": "last",
                "apple": "first",
                "middle": "center",
            },
            evidence_refs=[],
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
