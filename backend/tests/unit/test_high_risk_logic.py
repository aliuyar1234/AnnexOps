"""Unit tests for high-risk assessment scoring logic."""
import pytest

from src.core.wizard_questions import (
    calculate_score,
    get_result_label,
    get_checklist,
    WIZARD_QUESTIONS,
    HIGH_RISK_CHECKLIST,
)


class TestScoreCalculation:
    """Tests for score calculation logic."""

    def test_zero_score_when_all_false(self):
        """Score is 0 when all answers are False."""
        answers = [{"question_id": q["id"], "answer": False} for q in WIZARD_QUESTIONS]
        assert calculate_score(answers) == 0

    def test_max_score_when_all_true(self):
        """Score is 13 when all answers are True."""
        answers = [{"question_id": q["id"], "answer": True} for q in WIZARD_QUESTIONS]
        assert calculate_score(answers) == 13

    def test_partial_score(self):
        """Score counts only True answers for high-risk indicators."""
        answers = [
            {"question_id": "q1_hiring_decisions", "answer": True},
            {"question_id": "q2_cv_evaluation", "answer": True},
            {"question_id": "q3_candidate_ranking", "answer": False},
            {"question_id": "q4_performance_monitoring", "answer": True},
        ]
        assert calculate_score(answers) == 3

    def test_empty_answers(self):
        """Score is 0 for empty answers."""
        assert calculate_score([]) == 0

    def test_unknown_question_id_ignored(self):
        """Unknown question IDs are ignored in scoring."""
        answers = [
            {"question_id": "q1_hiring_decisions", "answer": True},
            {"question_id": "unknown_question", "answer": True},
        ]
        assert calculate_score(answers) == 1


class TestResultLabel:
    """Tests for result label determination."""

    def test_likely_not_for_low_scores(self):
        """Scores 0-3 return 'likely_not'."""
        assert get_result_label(0) == "likely_not"
        assert get_result_label(1) == "likely_not"
        assert get_result_label(2) == "likely_not"
        assert get_result_label(3) == "likely_not"

    def test_unclear_for_medium_scores(self):
        """Scores 4-6 return 'unclear'."""
        assert get_result_label(4) == "unclear"
        assert get_result_label(5) == "unclear"
        assert get_result_label(6) == "unclear"

    def test_likely_high_risk_for_high_scores(self):
        """Scores 7+ return 'likely_high_risk'."""
        assert get_result_label(7) == "likely_high_risk"
        assert get_result_label(10) == "likely_high_risk"
        assert get_result_label(13) == "likely_high_risk"


class TestChecklist:
    """Tests for checklist generation."""

    def test_checklist_for_high_risk(self):
        """High-risk results include checklist items."""
        checklist = get_checklist("likely_high_risk")
        assert len(checklist) == len(HIGH_RISK_CHECKLIST)
        assert "Conduct conformity assessment" in checklist

    def test_no_checklist_for_likely_not(self):
        """Likely not high-risk results have empty checklist."""
        checklist = get_checklist("likely_not")
        assert checklist == []

    def test_no_checklist_for_unclear(self):
        """Unclear results have empty checklist."""
        checklist = get_checklist("unclear")
        assert checklist == []


class TestWizardQuestions:
    """Tests for wizard question structure."""

    def test_question_count(self):
        """There are 13 wizard questions."""
        assert len(WIZARD_QUESTIONS) == 13

    def test_all_questions_have_required_fields(self):
        """All questions have id, text, help_text, high_risk_indicator."""
        for q in WIZARD_QUESTIONS:
            assert "id" in q
            assert "text" in q
            assert "help_text" in q
            assert "high_risk_indicator" in q

    def test_all_questions_are_high_risk_indicators(self):
        """All questions are high-risk indicators (per research.md)."""
        for q in WIZARD_QUESTIONS:
            assert q["high_risk_indicator"] is True
