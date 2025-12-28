"""High-risk assessment wizard questions per EU AI Act Annex III."""

WIZARD_VERSION = "1.0"

WIZARD_QUESTIONS = [
    {
        "id": "q1_hiring_decisions",
        "text": "Does the system make or influence hiring decisions?",
        "help_text": "This includes ranking candidates, filtering applications, or recommending hires",
        "high_risk_indicator": True,
    },
    {
        "id": "q2_cv_evaluation",
        "text": "Does the system evaluate job applications or CVs?",
        "help_text": "Automated screening or scoring of resumes and applications",
        "high_risk_indicator": True,
    },
    {
        "id": "q3_candidate_ranking",
        "text": "Does the system rank or filter candidates?",
        "help_text": "Sorting or prioritizing candidates based on AI-derived scores",
        "high_risk_indicator": True,
    },
    {
        "id": "q4_performance_monitoring",
        "text": "Does the system monitor worker performance?",
        "help_text": "Tracking productivity, quality metrics, or work output",
        "high_risk_indicator": True,
    },
    {
        "id": "q5_behavior_tracking",
        "text": "Does the system track worker behavior, location, or activities?",
        "help_text": "Surveillance of physical location, computer activity, or communications",
        "high_risk_indicator": True,
    },
    {
        "id": "q6_promotion_termination",
        "text": "Does the system influence promotions or terminations?",
        "help_text": "Recommendations or decisions about career advancement or job loss",
        "high_risk_indicator": True,
    },
    {
        "id": "q7_task_allocation",
        "text": "Does the system allocate tasks based on worker profiles?",
        "help_text": "Assigning work or shifts based on AI-derived worker assessments",
        "high_risk_indicator": True,
    },
    {
        "id": "q8_conduct_evaluation",
        "text": "Does the system evaluate worker conduct or attendance?",
        "help_text": "Monitoring compliance with policies, punctuality, or behavior standards",
        "high_risk_indicator": True,
    },
    {
        "id": "q9_training_access",
        "text": "Does the system make decisions affecting access to training or benefits?",
        "help_text": "Determining eligibility for professional development or employee benefits",
        "high_risk_indicator": True,
    },
    {
        "id": "q10_autonomous_decisions",
        "text": "Does the system operate autonomously without human review of decisions?",
        "help_text": "Decisions are implemented automatically without human approval",
        "high_risk_indicator": True,
    },
    {
        "id": "q11_biometric_data",
        "text": "Does the system use biometric data for identification or categorization?",
        "help_text": "Facial recognition, voice analysis, or other biometric processing",
        "high_risk_indicator": True,
    },
    {
        "id": "q12_special_category_data",
        "text": "Does the system process special category data (health, ethnicity, etc.)?",
        "help_text": "Processing of sensitive personal data as defined in GDPR Article 9",
        "high_risk_indicator": True,
    },
    {
        "id": "q13_vulnerable_workers",
        "text": "Are affected workers in a vulnerable situation (temporary, gig, etc.)?",
        "help_text": "Workers with precarious employment status or limited bargaining power",
        "high_risk_indicator": True,
    },
]

# Scoring thresholds
SCORE_THRESHOLDS = {
    "likely_not": (0, 3),  # 0-3 indicators: likely not high-risk
    "unclear": (4, 6),  # 4-6 indicators: unclear, needs analysis
    "likely_high_risk": (7, 13),  # 7+ indicators: likely high-risk
}

# Checklist items for high-risk systems
HIGH_RISK_CHECKLIST = [
    "Conduct conformity assessment",
    "Implement risk management system",
    "Ensure data governance practices",
    "Prepare technical documentation (Annex IV)",
    "Implement logging and traceability",
    "Provide transparency information to deployers",
    "Ensure human oversight mechanisms",
    "Register in EU database (when applicable)",
]

# Disclaimer text
ASSESSMENT_DISCLAIMER = (
    "This assessment is advisory only and does not constitute legal advice. "
    "Organizations should consult with qualified legal professionals for definitive "
    "EU AI Act compliance determinations."
)


def calculate_score(answers: list[dict]) -> int:
    """Calculate high-risk score from answers.

    Args:
        answers: List of answer dicts with question_id and answer

    Returns:
        Count of high-risk indicators where answer is True
    """
    question_indicators = {q["id"]: q["high_risk_indicator"] for q in WIZARD_QUESTIONS}

    score = 0
    for answer in answers:
        question_id = answer.get("question_id")
        answer_value = answer.get("answer", False)

        if question_id in question_indicators:
            if answer_value and question_indicators[question_id]:
                score += 1

    return score


def get_result_label(score: int) -> str:
    """Get result label based on score.

    Args:
        score: High-risk indicator count

    Returns:
        Result label string
    """
    if score <= 3:
        return "likely_not"
    elif score <= 6:
        return "unclear"
    else:
        return "likely_high_risk"


def get_checklist(result_label: str) -> list[str]:
    """Get checklist items based on result.

    Args:
        result_label: Assessment result label

    Returns:
        List of checklist items (empty for non-high-risk)
    """
    if result_label == "likely_high_risk":
        return HIGH_RISK_CHECKLIST
    return []
