"""Unit tests for completeness calculation logic."""
from uuid import uuid4


def test_section_score_formula_only_fields():
    """Test section completeness formula with only field completion (no evidence)."""
    from src.core.section_schemas import SECTION_SCHEMAS

    # ANNEX4.GENERAL has 5 required fields
    section_key = "ANNEX4.GENERAL"
    required = SECTION_SCHEMAS[section_key]
    assert len(required) == 5

    # Test: all fields filled, no evidence
    content = {
        "provider_name": "Test Provider",
        "provider_address": "123 Test St",
        "system_name": "Test System",
        "system_version": "1.0.0",
        "conformity_declaration_date": "2024-01-01",
    }
    evidence_refs = []

    # Calculate field score: 5/5 * 50 = 50%
    filled = sum(1 for f in required if content.get(f))
    field_score = (filled / len(required)) * 50

    # Calculate evidence score: 0/3 * 50 = 0%
    evidence_score = min(len(evidence_refs), 3) / 3 * 50

    total_score = round(field_score + evidence_score, 2)
    assert total_score == 50.0


def test_section_score_formula_only_evidence():
    """Test section completeness formula with only evidence (no fields filled)."""
    from src.core.section_schemas import SECTION_SCHEMAS

    # ANNEX4.GENERAL has 5 required fields
    section_key = "ANNEX4.GENERAL"
    required = SECTION_SCHEMAS[section_key]

    # Test: no fields filled, 3 evidence items (max)
    content = {}
    evidence_refs = [uuid4(), uuid4(), uuid4()]

    # Calculate field score: 0/5 * 50 = 0%
    filled = sum(1 for f in required if content.get(f))
    field_score = (filled / len(required)) * 50

    # Calculate evidence score: 3/3 * 50 = 50%
    evidence_score = min(len(evidence_refs), 3) / 3 * 50

    total_score = round(field_score + evidence_score, 2)
    assert total_score == 50.0


def test_section_score_formula_partial_both():
    """Test section completeness formula with partial field and evidence completion."""
    from src.core.section_schemas import SECTION_SCHEMAS

    # ANNEX4.GENERAL has 5 required fields
    section_key = "ANNEX4.GENERAL"
    required = SECTION_SCHEMAS[section_key]

    # Test: 3/5 fields filled, 1 evidence item
    content = {
        "provider_name": "Test Provider",
        "system_name": "Test System",
        "system_version": "1.0.0",
    }
    evidence_refs = [uuid4()]

    # Calculate field score: 3/5 * 50 = 30%
    filled = sum(1 for f in required if content.get(f))
    field_score = (filled / len(required)) * 50

    # Calculate evidence score: 1/3 * 50 = 16.67%
    evidence_score = min(len(evidence_refs), 3) / 3 * 50

    total_score = round(field_score + evidence_score, 2)
    assert total_score == 46.67


def test_section_score_formula_complete():
    """Test section completeness formula with all fields and max evidence."""
    from src.core.section_schemas import SECTION_SCHEMAS

    # ANNEX4.GENERAL has 5 required fields
    section_key = "ANNEX4.GENERAL"
    required = SECTION_SCHEMAS[section_key]

    # Test: all fields filled, 3+ evidence items
    content = {
        "provider_name": "Test Provider",
        "provider_address": "123 Test St",
        "system_name": "Test System",
        "system_version": "1.0.0",
        "conformity_declaration_date": "2024-01-01",
    }
    evidence_refs = [uuid4(), uuid4(), uuid4(), uuid4()]  # 4 items, but max is 3

    # Calculate field score: 5/5 * 50 = 50%
    filled = sum(1 for f in required if content.get(f))
    field_score = (filled / len(required)) * 50

    # Calculate evidence score: min(4, 3)/3 * 50 = 50%
    evidence_score = min(len(evidence_refs), 3) / 3 * 50

    total_score = round(field_score + evidence_score, 2)
    assert total_score == 100.0


def test_section_score_formula_empty_values_dont_count():
    """Test that empty string and None values don't count as filled."""
    from src.core.section_schemas import SECTION_SCHEMAS

    section_key = "ANNEX4.GENERAL"
    required = SECTION_SCHEMAS[section_key]

    # Test: fields present but empty
    content = {
        "provider_name": "",  # Empty string
        "provider_address": None,  # None
        "system_name": "Test System",  # Valid
        "system_version": "1.0.0",  # Valid
        "conformity_declaration_date": [],  # Empty list
    }

    # Only 2 fields should count as filled
    filled = sum(1 for f in required if content.get(f) not in (None, "", []))
    assert filled == 2

    field_score = (filled / len(required)) * 50
    evidence_score = 0  # No evidence
    total_score = round(field_score + evidence_score, 2)
    assert total_score == 20.0


def test_weighted_version_completeness():
    """Test weighted version completeness using SECTION_WEIGHTS."""
    from src.core.section_schemas import SECTION_WEIGHTS

    # Create section scores
    section_scores = {
        "ANNEX4.GENERAL": 100.0,  # weight 5.0
        "ANNEX4.INTENDED_PURPOSE": 80.0,  # weight 8.0
        "ANNEX4.SYSTEM_DESCRIPTION": 60.0,  # weight 10.0
        "ANNEX4.RISK_MANAGEMENT": 50.0,  # weight 15.0
        "ANNEX4.DATA_GOVERNANCE": 70.0,  # weight 12.0
        "ANNEX4.MODEL_TECHNICAL": 90.0,  # weight 10.0
        "ANNEX4.PERFORMANCE": 40.0,  # weight 10.0
        "ANNEX4.HUMAN_OVERSIGHT": 75.0,  # weight 8.0
        "ANNEX4.LOGGING": 85.0,  # weight 7.0
        "ANNEX4.ACCURACY_ROBUSTNESS_CYBERSEC": 55.0,  # weight 10.0
        "ANNEX4.POST_MARKET_MONITORING": 95.0,  # weight 5.0
        "ANNEX4.CHANGE_MANAGEMENT": 100.0,  # weight 0.0 (not counted)
    }

    # Calculate weighted sum
    total_score = 0.0
    total_weight = 0.0

    for section_key, score in section_scores.items():
        weight = SECTION_WEIGHTS[section_key]
        total_score += score * weight
        total_weight += weight

    overall_score = round(total_score / total_weight, 2)

    # Verify calculation
    # Total weighted score = 100*5 + 80*8 + 60*10 + 50*15 + 70*12 + 90*10 + 40*10 + 75*8 + 85*7 + 55*10 + 95*5
    # = 500 + 640 + 600 + 750 + 840 + 900 + 400 + 600 + 595 + 550 + 475 = 6850
    # Total weight = 5 + 8 + 10 + 15 + 12 + 10 + 10 + 8 + 7 + 10 + 5 = 100
    # Overall = 6850 / 100 = 68.50
    assert overall_score == 68.50


def test_weighted_version_completeness_missing_sections():
    """Test weighted version completeness when some sections are missing."""
    from src.core.section_schemas import SECTION_WEIGHTS

    # Only 3 sections present
    section_scores = {
        "ANNEX4.GENERAL": 100.0,  # weight 5.0
        "ANNEX4.RISK_MANAGEMENT": 80.0,  # weight 15.0
        "ANNEX4.DATA_GOVERNANCE": 60.0,  # weight 12.0
    }

    # Calculate weighted sum (missing sections contribute 0)
    total_score = 0.0
    total_weight = sum(SECTION_WEIGHTS.values())

    for section_key, weight in SECTION_WEIGHTS.items():
        if section_key in section_scores:
            total_score += section_scores[section_key] * weight
        # Missing sections contribute 0 to total_score

    overall_score = round(total_score / total_weight, 2)

    # Verify calculation
    # Total weighted score = 100*5 + 80*15 + 60*12 = 500 + 1200 + 720 = 2420
    # Total weight = 100 (sum of all weights)
    # Overall = 2420 / 100 = 24.20
    assert overall_score == 24.20
