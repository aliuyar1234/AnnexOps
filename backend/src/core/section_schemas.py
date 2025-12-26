"""Section schemas and weights for Annex IV documentation."""

from typing import Dict, List

# Section schemas define required fields for each Annex IV section
SECTION_SCHEMAS: Dict[str, List[str]] = {
    "ANNEX4.GENERAL": [
        "provider_name",
        "provider_address",
        "system_name",
        "system_version",
        "conformity_declaration_date",
    ],
    "ANNEX4.INTENDED_PURPOSE": [
        "intended_purpose_description",
        "target_users",
        "deployment_context",
        "reasonably_foreseeable_misuse",
    ],
    "ANNEX4.SYSTEM_DESCRIPTION": [
        "architecture_overview",
        "technical_components",
        "input_data_description",
        "output_data_description",
        "dependencies",
    ],
    "ANNEX4.RISK_MANAGEMENT": [
        "risk_management_system_description",
        "identified_risks",
        "risk_mitigation_measures",
        "residual_risks",
        "risk_acceptability_criteria",
    ],
    "ANNEX4.DATA_GOVERNANCE": [
        "training_data_sources",
        "training_data_characteristics",
        "data_quality_measures",
        "data_preprocessing_steps",
        "bias_assessment",
        "data_protection_measures",
    ],
    "ANNEX4.MODEL_TECHNICAL": [
        "model_architecture",
        "training_methodology",
        "hyperparameters",
        "feature_engineering",
        "model_validation_approach",
    ],
    "ANNEX4.PERFORMANCE": [
        "performance_metrics",
        "test_dataset_description",
        "performance_results",
        "performance_across_subgroups",
        "benchmark_comparison",
    ],
    "ANNEX4.HUMAN_OVERSIGHT": [
        "oversight_measures",
        "human_review_process",
        "override_capabilities",
        "competence_requirements",
    ],
    "ANNEX4.LOGGING": [
        "logging_capabilities",
        "logged_events",
        "log_retention_period",
        "log_access_controls",
        "traceability_measures",
    ],
    "ANNEX4.ACCURACY_ROBUSTNESS_CYBERSEC": [
        "accuracy_requirements",
        "robustness_testing",
        "cybersecurity_measures",
        "resilience_to_attacks",
        "fail_safe_mechanisms",
    ],
    "ANNEX4.POST_MARKET_MONITORING": [
        "monitoring_plan",
        "feedback_mechanisms",
        "incident_reporting_procedures",
        "continuous_improvement_process",
    ],
    "ANNEX4.CHANGE_MANAGEMENT": [
        "change_management_process",
        "version_control_procedures",
        "update_notification_process",
        "regression_testing_approach",
    ],
}

# Section weights for completeness calculation
# These weights determine the relative importance of each section
# Total should sum to 100 for percentage calculation
SECTION_WEIGHTS: Dict[str, float] = {
    "ANNEX4.GENERAL": 5.0,
    "ANNEX4.INTENDED_PURPOSE": 8.0,
    "ANNEX4.SYSTEM_DESCRIPTION": 10.0,
    "ANNEX4.RISK_MANAGEMENT": 15.0,
    "ANNEX4.DATA_GOVERNANCE": 12.0,
    "ANNEX4.MODEL_TECHNICAL": 10.0,
    "ANNEX4.PERFORMANCE": 10.0,
    "ANNEX4.HUMAN_OVERSIGHT": 8.0,
    "ANNEX4.LOGGING": 7.0,
    "ANNEX4.ACCURACY_ROBUSTNESS_CYBERSEC": 10.0,
    "ANNEX4.POST_MARKET_MONITORING": 5.0,
    "ANNEX4.CHANGE_MANAGEMENT": 0.0,
}


def get_section_completeness(section_key: str, content: Dict) -> float:
    """Calculate completeness score for a section.

    Args:
        section_key: The section key (e.g., "ANNEX4.GENERAL")
        content: The section content as a dictionary

    Returns:
        Completeness score as a percentage (0-100)
    """
    if section_key not in SECTION_SCHEMAS:
        return 0.0

    required_fields = SECTION_SCHEMAS[section_key]
    if not required_fields:
        return 100.0

    filled_fields = sum(
        1 for field in required_fields
        if field in content and content[field] not in (None, "", [])
    )

    return round((filled_fields / len(required_fields)) * 100, 2)


def get_overall_completeness(sections: Dict[str, Dict]) -> float:
    """Calculate overall completeness across all sections.

    Args:
        sections: Dictionary mapping section_key to section content

    Returns:
        Weighted average completeness score (0-100)
    """
    total_score = 0.0
    total_weight = sum(SECTION_WEIGHTS.values())

    for section_key, weight in SECTION_WEIGHTS.items():
        if section_key in sections:
            section_completeness = get_section_completeness(
                section_key, sections[section_key]
            )
            total_score += section_completeness * weight
        # If section doesn't exist, it contributes 0 to the score

    if total_weight == 0:
        return 0.0

    return round(total_score / total_weight, 2)
