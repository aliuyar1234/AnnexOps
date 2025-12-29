"""Snapshot service for deterministic hash computation."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from src.core.manifest import (
    AISystemInfo,
    AnnexSectionData,
    EvidenceIndexItem,
    EvidenceMappingData,
    HighRiskAssessmentInfo,
    OrgInfo,
    SystemManifest,
    SystemVersionInfo,
)
from src.models.ai_system import AISystem
from src.models.annex_section import AnnexSection
from src.models.evidence_item import EvidenceItem
from src.models.evidence_mapping import EvidenceMapping
from src.models.high_risk_assessment import HighRiskAssessment
from src.models.organization import Organization
from src.models.system_version import SystemVersion


class SnapshotService:
    """Service for generating manifests and computing deterministic snapshot hashes.

    Implements Constitution Principle V: Reproducibility
    - Deterministic hash: same content MUST produce identical hash 100% of the time
    - Canonical JSON: sorted keys, no whitespace (compact)
    - SHA-256 hash over the canonical manifest JSON

    Note: the snapshot hash is computed over the canonical manifest JSON *without*
    the `snapshot_hash` field (to avoid circularity).
    """

    def generate_manifest(
        self,
        *,
        org: Organization,
        version: SystemVersion,
        ai_system: AISystem,
        sections: list[AnnexSection],
        evidence_items: list[EvidenceItem],
        mappings: list[EvidenceMapping],
        assessment: HighRiskAssessment | None = None,
    ) -> SystemManifest:
        """Generate a complete system manifest for a version (SSOT payload)."""
        generated_at = version.updated_at or version.created_at or datetime.now(UTC)

        annex_sections: dict[str, AnnexSectionData] = {
            section.section_key: AnnexSectionData(
                content=section.content or {},
                evidence_refs=sorted({str(eid) for eid in (section.evidence_refs or [])}),
            )
            for section in sections
        }

        evidence_index: dict[str, EvidenceIndexItem] = {}
        for evidence in evidence_items:
            evidence_id = str(evidence.id)
            evidence_index[evidence_id] = EvidenceIndexItem(
                id=evidence_id,
                title=evidence.title,
                type=evidence.type.value,
                classification=evidence.classification.value,
                tags=sorted({t for t in (evidence.tags or []) if t}),
                type_metadata=evidence.type_metadata or {},
                checksum=self._compute_evidence_checksum(evidence),
            )

        manifest_mappings: list[EvidenceMappingData] = [
            EvidenceMappingData(
                evidence_id=str(mapping.evidence_id),
                target_type=mapping.target_type.value,
                target_key=mapping.target_key,
                strength=mapping.strength.value if mapping.strength else None,
                notes=mapping.notes,
                created_at=mapping.created_at,
            )
            for mapping in mappings
        ]
        manifest_mappings.sort(key=lambda m: (m.target_type, m.target_key, m.evidence_id))

        return SystemManifest(
            manifest_version="1.0",
            generated_at=generated_at,
            snapshot_hash=None,
            org=OrgInfo(id=org.id, name=org.name),
            ai_system=AISystemInfo(
                id=ai_system.id,
                name=ai_system.name,
                hr_use_case_type=ai_system.hr_use_case_type.value,
                intended_purpose=ai_system.intended_purpose,
            ),
            system_version=SystemVersionInfo(
                id=version.id,
                label=version.label,
                status=version.status.value,
                release_date=version.release_date,
                created_at=version.created_at,
                updated_at=version.updated_at,
            ),
            high_risk_assessment=(
                HighRiskAssessmentInfo(
                    id=assessment.id,
                    result_label=assessment.result_label.value,
                    score=assessment.score,
                    answers_json=assessment.answers_json or {},
                    notes=assessment.notes,
                    created_at=assessment.created_at,
                )
                if assessment
                else None
            ),
            annex_sections=annex_sections,
            evidence_index=evidence_index,
            mappings=manifest_mappings,
        )

    def finalize_manifest(self, manifest: SystemManifest) -> SystemManifest:
        """Return a copy of `manifest` with `snapshot_hash` populated."""
        snapshot_hash = self.compute_hash_from_manifest(manifest)
        return SystemManifest(
            manifest_version=manifest.manifest_version,
            generated_at=manifest.generated_at,
            snapshot_hash=snapshot_hash,
            org=manifest.org,
            ai_system=manifest.ai_system,
            system_version=manifest.system_version,
            high_risk_assessment=manifest.high_risk_assessment,
            annex_sections=manifest.annex_sections,
            evidence_index=manifest.evidence_index,
            mappings=manifest.mappings,
        )

    def _compute_evidence_checksum(self, evidence: EvidenceItem) -> str:
        if evidence.type.value == "upload":
            checksum = (evidence.type_metadata or {}).get("checksum_sha256")
            if checksum:
                return str(checksum)

        metadata_json = json.dumps(
            evidence.type_metadata or {},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        return hashlib.sha256(metadata_json.encode("utf-8")).hexdigest()

    def _canonical_manifest_dict_for_hash(self, manifest: SystemManifest) -> dict:
        manifest_dict = manifest.to_dict()
        manifest_dict.pop("snapshot_hash", None)
        return manifest_dict

    def to_canonical_json(self, manifest: SystemManifest) -> str:
        """Convert manifest to canonical JSON format (sorted keys, no whitespace)."""
        canonical_dict = self._canonical_manifest_dict_for_hash(manifest)
        return json.dumps(
            canonical_dict,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )

    def compute_hash_from_manifest(self, manifest: SystemManifest) -> str:
        """Compute SHA-256 hash from a manifest (excluding snapshot_hash field)."""
        canonical = self.to_canonical_json(manifest)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
