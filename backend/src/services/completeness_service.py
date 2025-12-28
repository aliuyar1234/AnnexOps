"""Completeness calculation service for Annex IV documentation."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.section_schemas import SECTION_SCHEMAS, SECTION_WEIGHTS
from src.models.annex_section import AnnexSection
from src.schemas.completeness import (
    CompletenessResponse,
    GapItem,
    SectionCompletenessItem,
)

# Human-readable section titles
SECTION_TITLES = {
    "ANNEX4.GENERAL": "General Information",
    "ANNEX4.INTENDED_PURPOSE": "Intended Purpose",
    "ANNEX4.SYSTEM_DESCRIPTION": "System Description",
    "ANNEX4.RISK_MANAGEMENT": "Risk Management System",
    "ANNEX4.DATA_GOVERNANCE": "Data Governance",
    "ANNEX4.MODEL_TECHNICAL": "Model & Technical Documentation",
    "ANNEX4.PERFORMANCE": "Performance Metrics",
    "ANNEX4.HUMAN_OVERSIGHT": "Human Oversight",
    "ANNEX4.LOGGING": "Logging & Traceability",
    "ANNEX4.ACCURACY_ROBUSTNESS_CYBERSEC": "Accuracy, Robustness & Cybersecurity",
    "ANNEX4.POST_MARKET_MONITORING": "Post-Market Monitoring",
    "ANNEX4.CHANGE_MANAGEMENT": "Change Management",
}


def calculate_section_score(section: AnnexSection) -> float:
    """Calculate completeness score for a section.

    Uses the formula:
    - 50% from required fields (all filled = 50%)
    - 50% from evidence (max 3 items = 50%, 1 item = 16.67%, etc.)

    Args:
        section: AnnexSection instance with content and evidence_refs

    Returns:
        Completeness score (0-100)
    """
    section_key = section.section_key

    # Get required fields for this section
    if section_key not in SECTION_SCHEMAS:
        return 0.0

    required = SECTION_SCHEMAS[section_key]
    if not required:
        # If no required fields, only evidence counts
        evidence_score = min(len(section.evidence_refs), 3) / 3 * 100
        return round(evidence_score, 2)

    # Calculate field score (50%)
    content = section.content or {}
    filled = sum(1 for field in required if content.get(field) not in (None, "", []))
    field_score = (filled / len(required)) * 50

    # Calculate evidence score (50%)
    # Max 3 evidence items = full 50 points
    evidence_count = len(section.evidence_refs)
    evidence_score = min(evidence_count, 3) / 3 * 50

    return round(field_score + evidence_score, 2)


def calculate_version_score(sections: list[AnnexSection]) -> float:
    """Calculate overall weighted version completeness.

    Uses SECTION_WEIGHTS to create weighted average of section scores.
    Missing sections contribute 0 to the weighted sum.

    Args:
        sections: List of AnnexSection instances for the version

    Returns:
        Weighted overall completeness score (0-100)
    """
    # Build section scores map
    section_scores = {}
    for section in sections:
        score = calculate_section_score(section)
        section_scores[section.section_key] = score

    # Calculate weighted sum
    total_score = 0.0
    total_weight = sum(SECTION_WEIGHTS.values())

    for section_key, weight in SECTION_WEIGHTS.items():
        if section_key in section_scores:
            total_score += section_scores[section_key] * weight
        # Missing sections contribute 0

    if total_weight == 0:
        return 0.0

    return round(total_score / total_weight, 2)


def detect_gaps(section: AnnexSection) -> tuple[dict[str, bool], list[str], list[GapItem]]:
    """Detect gaps in section completeness.

    Args:
        section: AnnexSection instance to analyze

    Returns:
        Tuple of:
        - field_completion: Dict mapping field names to filled status
        - gap_descriptions: List of human-readable gap descriptions
        - gap_items: List of GapItem objects for aggregation
    """
    section_key = section.section_key
    content = section.content or {}

    # Get required fields
    if section_key not in SECTION_SCHEMAS:
        return {}, [], []

    required = SECTION_SCHEMAS[section_key]
    field_completion = {}
    gap_descriptions = []
    gap_items = []

    # Check each required field
    for field in required:
        is_filled = content.get(field) not in (None, "", [])
        field_completion[field] = is_filled

        if not is_filled:
            description = f"Missing required field: {field}"
            gap_descriptions.append(description)
            gap_items.append(
                GapItem(
                    section_key=section_key,
                    gap_type="required_field",
                    description=description,
                )
            )

    # Check evidence (warn if no evidence)
    if len(section.evidence_refs) == 0:
        description = "No evidence items mapped to this section"
        gap_descriptions.append(description)
        gap_items.append(
            GapItem(
                section_key=section_key,
                gap_type="no_evidence",
                description=description,
            )
        )

    return field_completion, gap_descriptions, gap_items


async def get_completeness_report(
    db: AsyncSession,
    version_id: UUID,
) -> CompletenessResponse:
    """Generate completeness dashboard report for a version.

    Args:
        db: Database session
        version_id: System version ID

    Returns:
        CompletenessResponse with overall and per-section details
    """
    # Fetch all sections for this version
    result = await db.execute(select(AnnexSection).where(AnnexSection.version_id == version_id))
    sections = result.scalars().all()

    # Calculate overall score
    overall_score = calculate_version_score(sections)

    # Build section details and aggregate gaps
    section_items = []
    all_gaps = []

    for section in sections:
        score = calculate_section_score(section)
        field_completion, gap_descriptions, gap_items = detect_gaps(section)

        section_item = SectionCompletenessItem(
            section_key=section.section_key,
            title=SECTION_TITLES.get(section.section_key, section.section_key),
            score=score,
            field_completion=field_completion,
            evidence_count=len(section.evidence_refs),
            gaps=gap_descriptions,
        )
        section_items.append(section_item)
        all_gaps.extend(gap_items)

    return CompletenessResponse(
        version_id=version_id,
        overall_score=overall_score,
        sections=section_items,
        gaps=all_gaps,
    )
