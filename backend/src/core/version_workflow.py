"""Version status workflow state machine."""

from src.models.enums import VersionStatus

# Valid status transitions for version lifecycle
# Key: current status, Value: list of allowed next statuses
VALID_TRANSITIONS: dict[VersionStatus, list[VersionStatus]] = {
    VersionStatus.DRAFT: [VersionStatus.REVIEW],
    VersionStatus.REVIEW: [VersionStatus.APPROVED, VersionStatus.DRAFT],
    VersionStatus.APPROVED: [],  # Terminal state - no further transitions
}


def is_valid_transition(from_status: VersionStatus, to_status: VersionStatus) -> bool:
    """Check if a status transition is valid.

    Args:
        from_status: Current version status
        to_status: Target version status

    Returns:
        True if the transition is allowed, False otherwise

    Examples:
        >>> is_valid_transition(VersionStatus.DRAFT, VersionStatus.REVIEW)
        True
        >>> is_valid_transition(VersionStatus.DRAFT, VersionStatus.APPROVED)
        False
        >>> is_valid_transition(VersionStatus.APPROVED, VersionStatus.DRAFT)
        False
    """
    return to_status in VALID_TRANSITIONS.get(from_status, [])


def get_allowed_transitions(from_status: VersionStatus) -> list[VersionStatus]:
    """Get list of allowed transitions from a given status.

    Args:
        from_status: Current version status

    Returns:
        List of allowed next statuses

    Examples:
        >>> get_allowed_transitions(VersionStatus.DRAFT)
        [<VersionStatus.REVIEW: 'review'>]
        >>> get_allowed_transitions(VersionStatus.REVIEW)
        [<VersionStatus.APPROVED: 'approved'>, <VersionStatus.DRAFT: 'draft'>]
        >>> get_allowed_transitions(VersionStatus.APPROVED)
        []
    """
    return VALID_TRANSITIONS.get(from_status, [])
