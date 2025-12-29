"""System manifest schema for version snapshots (SSOT export payload)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from uuid import UUID


@dataclass
class OrgInfo:
    """Organization information for the manifest."""

    id: UUID
    name: str


@dataclass
class AISystemInfo:
    """AI system information for the manifest."""

    id: UUID
    name: str
    hr_use_case_type: str
    intended_purpose: str


@dataclass
class SystemVersionInfo:
    """System version information for the manifest."""

    id: UUID
    label: str
    status: str
    release_date: date | None
    created_at: datetime
    updated_at: datetime


@dataclass
class HighRiskAssessmentInfo:
    """High-risk assessment summary for the manifest."""

    id: UUID
    result_label: str
    score: int
    answers_json: dict[str, Any]
    notes: str | None
    created_at: datetime


@dataclass
class AnnexSectionData:
    """Annex section data for the manifest."""

    content: dict[str, Any]
    evidence_refs: list[str]


@dataclass
class EvidenceIndexItem:
    """Evidence item for the manifest index."""

    id: str
    title: str
    type: str
    classification: str
    tags: list[str]
    type_metadata: dict[str, Any]
    checksum: str


@dataclass
class EvidenceMappingData:
    """Evidence mapping record for the manifest."""

    evidence_id: str
    target_type: str
    target_key: str
    strength: str | None
    notes: str | None
    created_at: datetime


@dataclass
class SystemManifest:
    """Canonical manifest used as SSOT for exports and reproducibility.

    Important: the `snapshot_hash` is computed from the canonical JSON
    representation *excluding* the `snapshot_hash` field itself.
    """

    manifest_version: str
    generated_at: datetime
    snapshot_hash: str | None
    org: OrgInfo
    ai_system: AISystemInfo
    system_version: SystemVersionInfo
    high_risk_assessment: HighRiskAssessmentInfo | None
    annex_sections: dict[str, AnnexSectionData]
    evidence_index: dict[str, EvidenceIndexItem]
    mappings: list[EvidenceMappingData]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ai_system": {
                "hr_use_case_type": self.ai_system.hr_use_case_type,
                "id": str(self.ai_system.id),
                "intended_purpose": self.ai_system.intended_purpose,
                "name": self.ai_system.name,
            },
            "annex_sections": {
                key: {
                    "content": section.content,
                    "evidence_refs": section.evidence_refs,
                }
                for key, section in self.annex_sections.items()
            },
            "evidence_index": {
                key: {
                    "checksum": evidence.checksum,
                    "classification": evidence.classification,
                    "id": evidence.id,
                    "tags": evidence.tags,
                    "title": evidence.title,
                    "type": evidence.type,
                    "type_metadata": evidence.type_metadata,
                }
                for key, evidence in self.evidence_index.items()
            },
            "generated_at": self.generated_at.isoformat(),
            "high_risk_assessment": (
                {
                    "answers_json": self.high_risk_assessment.answers_json,
                    "created_at": self.high_risk_assessment.created_at.isoformat(),
                    "id": str(self.high_risk_assessment.id),
                    "notes": self.high_risk_assessment.notes,
                    "result_label": self.high_risk_assessment.result_label,
                    "score": self.high_risk_assessment.score,
                }
                if self.high_risk_assessment
                else None
            ),
            "manifest_version": self.manifest_version,
            "mappings": [
                {
                    "created_at": mapping.created_at.isoformat(),
                    "evidence_id": mapping.evidence_id,
                    "notes": mapping.notes,
                    "strength": mapping.strength,
                    "target_key": mapping.target_key,
                    "target_type": mapping.target_type,
                }
                for mapping in self.mappings
            ],
            "org": {"id": str(self.org.id), "name": self.org.name},
            "snapshot_hash": self.snapshot_hash,
            "system_version": {
                "created_at": self.system_version.created_at.isoformat(),
                "id": str(self.system_version.id),
                "label": self.system_version.label,
                "release_date": self.system_version.release_date.isoformat()
                if self.system_version.release_date
                else None,
                "status": self.system_version.status,
                "updated_at": self.system_version.updated_at.isoformat(),
            },
        }
