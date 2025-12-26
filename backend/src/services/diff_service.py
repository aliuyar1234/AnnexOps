"""Service for computing differences between system versions."""
from typing import Any, Optional
from deepdiff import DeepDiff

from src.models.system_version import SystemVersion


class DiffService:
    """Service for computing version diffs using deepdiff library."""

    # Fields to include in version comparison
    COMPARABLE_FIELDS = [
        "label",
        "status",
        "notes",
        "release_date",
    ]

    def __init__(self):
        """Initialize diff service."""
        pass

    def _serialize_value(self, value: Any) -> Optional[str]:
        """Serialize a value to string for diff output.

        Args:
            value: Value to serialize

        Returns:
            Serialized string value or None
        """
        if value is None:
            return None
        if isinstance(value, str):
            return value
        # For enums, get the value
        if hasattr(value, "value"):
            return value.value
        # For dates, convert to ISO format
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)

    def _extract_comparable_data(self, version: SystemVersion) -> dict:
        """Extract comparable fields from a version.

        Args:
            version: SystemVersion instance

        Returns:
            Dictionary of comparable field values
        """
        data = {}
        for field in self.COMPARABLE_FIELDS:
            value = getattr(version, field, None)
            data[field] = self._serialize_value(value)
        return data

    def _compute_summary(self, changes: list[dict]) -> dict:
        """Compute summary counts from changes.

        Args:
            changes: List of field changes

        Returns:
            Summary dict with added, removed, modified counts
        """
        added = 0
        removed = 0
        modified = 0

        for change in changes:
            old_val = change["old_value"]
            new_val = change["new_value"]

            if old_val is None and new_val is not None:
                added += 1
            elif old_val is not None and new_val is None:
                removed += 1
            elif old_val != new_val:
                modified += 1

        return {
            "added": added,
            "removed": removed,
            "modified": modified,
        }

    def compute_diff(
        self,
        from_version: SystemVersion,
        to_version: SystemVersion,
    ) -> dict:
        """Compute differences between two system versions.

        Args:
            from_version: Source version (older version)
            to_version: Target version (newer version)

        Returns:
            Dictionary containing:
            - changes: List of field changes
            - summary: Summary counts (added, removed, modified)
        """
        # Extract comparable data from both versions
        from_data = self._extract_comparable_data(from_version)
        to_data = self._extract_comparable_data(to_version)

        # Use deepdiff to find differences
        # ignore_none_type_changes=False ensures None <-> value changes are detected
        diff = DeepDiff(
            from_data,
            to_data,
            ignore_order=True,
            verbose_level=2,
            ignore_type_in_groups=[(type(None), str)],  # Compare None and str types
        )

        changes = []

        # Handle values that changed
        if "values_changed" in diff:
            for path, change_detail in diff["values_changed"].items():
                # Extract field name from path (e.g., "root['label']" -> "label")
                field = path.replace("root['", "").replace("']", "")
                old_val = change_detail.get("old_value")
                new_val = change_detail.get("new_value")
                changes.append({
                    "field": field,
                    "old_value": old_val,
                    "new_value": new_val,
                })

        # Handle type changes (e.g., None -> str, str -> None)
        if "type_changes" in diff:
            for path, change_detail in diff["type_changes"].items():
                field = path.replace("root['", "").replace("']", "")
                old_val = change_detail.get("old_value")
                new_val = change_detail.get("new_value")
                changes.append({
                    "field": field,
                    "old_value": old_val,
                    "new_value": new_val,
                })

        # Handle new items (added fields)
        if "dictionary_item_added" in diff:
            for path in diff["dictionary_item_added"]:
                field = path.replace("root['", "").replace("']", "")
                changes.append({
                    "field": field,
                    "old_value": None,
                    "new_value": to_data.get(field),
                })

        # Handle removed items (removed fields)
        if "dictionary_item_removed" in diff:
            for path in diff["dictionary_item_removed"]:
                field = path.replace("root['", "").replace("']", "")
                changes.append({
                    "field": field,
                    "old_value": from_data.get(field),
                    "new_value": None,
                })

        # Compute summary
        summary = self._compute_summary(changes)

        return {
            "changes": changes,
            "summary": summary,
        }

    def compute_version_diff_response(
        self,
        from_version: SystemVersion,
        to_version: SystemVersion,
    ) -> dict:
        """Compute full diff response for API endpoint.

        Args:
            from_version: Source version
            to_version: Target version

        Returns:
            Dictionary ready for VersionDiffResponse schema
        """
        diff_result = self.compute_diff(from_version, to_version)

        return {
            "from_version": {
                "id": from_version.id,
                "label": from_version.label,
                "status": from_version.status,
            },
            "to_version": {
                "id": to_version.id,
                "label": to_version.label,
                "status": to_version.status,
            },
            "changes": diff_result["changes"],
            "summary": diff_result["summary"],
        }
