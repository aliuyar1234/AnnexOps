"""Snapshot service for deterministic hash computation."""
import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from src.core.manifest import (
    SystemManifest,
    SystemInfo,
    VersionInfo,
)
from src.models.ai_system import AISystem
from src.models.system_version import SystemVersion


class SnapshotService:
    """Service for generating manifests and computing deterministic snapshot hashes.

    Implements Constitution Principle V: Reproducibility
    - Deterministic hash: same content MUST produce identical hash 100% of the time
    - Canonical JSON: sorted keys, no whitespace (compact)
    - SHA-256 hash over the canonical manifest JSON
    """

    def generate_manifest(
        self,
        version: SystemVersion,
        ai_system: AISystem,
    ) -> SystemManifest:
        """Generate a complete system manifest for a version.

        Args:
            version: The system version to generate manifest for
            ai_system: The AI system the version belongs to

        Returns:
            SystemManifest with all current data (sections and evidence will be empty for now)
        """
        return SystemManifest(
            manifest_version="1.0",
            generated_at=datetime.now(timezone.utc),
            system=SystemInfo(
                id=ai_system.id,
                name=ai_system.name,
                hr_use_case_type=ai_system.hr_use_case_type.value,
                intended_purpose=ai_system.intended_purpose,
            ),
            version=VersionInfo(
                id=version.id,
                label=version.label,
                status=version.status.value,
                release_date=version.release_date,
            ),
            sections=[],  # Placeholder for Module E
            evidence_index=[],  # Placeholder for Module D
        )

    def to_canonical_json(self, manifest: SystemManifest) -> str:
        """Convert manifest to canonical JSON format.

        Canonical format requirements:
        - Sorted keys at ALL nesting levels
        - No whitespace (compact)
        - Deterministic output for identical content

        Args:
            manifest: The SystemManifest to serialize

        Returns:
            Canonical JSON string (sorted keys, no whitespace)
        """
        # Convert manifest to dictionary
        manifest_dict = manifest.to_dict()

        # Serialize with sorted keys and no whitespace
        # sort_keys=True ensures keys are sorted at all levels
        # separators=(',', ':') ensures compact output (no spaces)
        canonical = json.dumps(
            manifest_dict,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )

        return canonical

    def compute_hash_from_manifest(self, manifest: SystemManifest) -> str:
        """Compute SHA-256 hash from a manifest.

        Args:
            manifest: The SystemManifest to hash

        Returns:
            64-character SHA-256 hash (hexadecimal)
        """
        # Generate canonical JSON
        canonical = self.to_canonical_json(manifest)

        # Compute SHA-256 hash
        hash_bytes = hashlib.sha256(canonical.encode("utf-8")).digest()

        # Return as hexadecimal string
        return hash_bytes.hex()

    def get_or_compute_hash(
        self,
        version: SystemVersion,
        ai_system: AISystem,
    ) -> str:
        """Get the snapshot hash for a version, computing if necessary.

        This method is used during export (Module E) to set the snapshot_hash field.
        For now, it always computes a fresh hash.

        Args:
            version: The system version
            ai_system: The AI system the version belongs to

        Returns:
            64-character SHA-256 hash (hexadecimal)
        """
        # Generate fresh manifest
        manifest = self.generate_manifest(version, ai_system)

        # Compute and return hash
        return self.compute_hash_from_manifest(manifest)
