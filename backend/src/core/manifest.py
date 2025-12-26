"""System manifest schema for version snapshots."""
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from uuid import UUID


@dataclass
class SystemInfo:
    """System information for manifest."""

    id: UUID
    name: str
    hr_use_case_type: str
    intended_purpose: str


@dataclass
class VersionInfo:
    """Version information for manifest."""

    id: UUID
    label: str
    status: str
    release_date: date | None


@dataclass
class SectionData:
    """Section data for manifest."""

    key: str
    content: dict[str, Any]
    evidence_refs: list[str]


@dataclass
class EvidenceItem:
    """Evidence item for manifest index."""

    id: str
    title: str
    type: str
    checksum: str


@dataclass
class SystemManifest:
    """Complete system manifest for version snapshot.

    This represents the canonical structure used for computing
    the snapshot hash for reproducibility.

    The manifest is serialized to JSON with sorted keys and no
    whitespace, then hashed with SHA-256.
    """

    manifest_version: str  # Schema version (e.g., "1.0")
    generated_at: datetime
    system: SystemInfo
    version: VersionInfo
    sections: list[SectionData]
    evidence_index: list[EvidenceItem]

    def to_dict(self) -> dict[str, Any]:
        """Convert manifest to dictionary for JSON serialization.

        Returns:
            Dictionary representation with all nested dataclasses converted
        """
        return {
            "manifest_version": self.manifest_version,
            "generated_at": self.generated_at.isoformat(),
            "system": {
                "id": str(self.system.id),
                "name": self.system.name,
                "hr_use_case_type": self.system.hr_use_case_type,
                "intended_purpose": self.system.intended_purpose,
            },
            "version": {
                "id": str(self.version.id),
                "label": self.version.label,
                "status": self.version.status,
                "release_date": self.version.release_date.isoformat() if self.version.release_date else None,
            },
            "sections": [
                {
                    "key": section.key,
                    "content": section.content,
                    "evidence_refs": section.evidence_refs,
                }
                for section in self.sections
            ],
            "evidence_index": [
                {
                    "id": evidence.id,
                    "title": evidence.title,
                    "type": evidence.type,
                    "checksum": evidence.checksum,
                }
                for evidence in self.evidence_index
            ],
        }
