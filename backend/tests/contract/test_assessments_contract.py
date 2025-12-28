"""Contract tests for assessment endpoints."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import create_access_token
from src.models.ai_system import AISystem
from src.models.organization import Organization
from src.models.user import User


@pytest.mark.asyncio
async def test_get_wizard_questions_returns_200(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """GET /systems/{id}/high-risk-assessment/questions returns 200."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    response = await client.get(
        f"/api/systems/{test_ai_system.id}/high-risk-assessment/questions",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "version" in data
    assert "questions" in data
    assert len(data["questions"]) == 13
    assert all("id" in q and "text" in q for q in data["questions"])


@pytest.mark.asyncio
async def test_submit_assessment_returns_201(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """POST /systems/{id}/high-risk-assessment returns 201 with result."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Submit assessment with some high-risk answers
    response = await client.post(
        f"/api/systems/{test_ai_system.id}/high-risk-assessment",
        json={
            "answers": [
                {"question_id": "q1_hiring_decisions", "answer": True},
                {"question_id": "q2_cv_evaluation", "answer": True},
                {"question_id": "q3_candidate_ranking", "answer": True},
                {"question_id": "q4_performance_monitoring", "answer": False},
                {"question_id": "q5_behavior_tracking", "answer": False},
                {"question_id": "q6_promotion_termination", "answer": False},
                {"question_id": "q7_task_allocation", "answer": False},
                {"question_id": "q8_conduct_evaluation", "answer": False},
                {"question_id": "q9_training_access", "answer": False},
                {"question_id": "q10_autonomous_decisions", "answer": False},
                {"question_id": "q11_biometric_data", "answer": False},
                {"question_id": "q12_special_category_data", "answer": False},
                {"question_id": "q13_vulnerable_workers", "answer": False},
            ],
            "notes": "Initial assessment for testing",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["score"] == 3
    assert data["result_label"] == "likely_not"
    assert "disclaimer" in data
    assert data["checklist"] == []  # No checklist for likely_not


@pytest.mark.asyncio
async def test_submit_assessment_high_risk_result(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """POST assessment with high-risk answers returns checklist."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Submit assessment with many high-risk answers
    response = await client.post(
        f"/api/systems/{test_ai_system.id}/high-risk-assessment",
        json={
            "answers": [
                {"question_id": "q1_hiring_decisions", "answer": True},
                {"question_id": "q2_cv_evaluation", "answer": True},
                {"question_id": "q3_candidate_ranking", "answer": True},
                {"question_id": "q4_performance_monitoring", "answer": True},
                {"question_id": "q5_behavior_tracking", "answer": True},
                {"question_id": "q6_promotion_termination", "answer": True},
                {"question_id": "q7_task_allocation", "answer": True},
                {"question_id": "q8_conduct_evaluation", "answer": True},
                {"question_id": "q9_training_access", "answer": False},
                {"question_id": "q10_autonomous_decisions", "answer": False},
                {"question_id": "q11_biometric_data", "answer": False},
                {"question_id": "q12_special_category_data", "answer": False},
                {"question_id": "q13_vulnerable_workers", "answer": False},
            ],
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["score"] == 8
    assert data["result_label"] == "likely_high_risk"
    assert len(data["checklist"]) > 0


@pytest.mark.asyncio
async def test_get_assessment_history_returns_200(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """GET /systems/{id}/high-risk-assessment returns assessment history."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Submit an assessment first
    await client.post(
        f"/api/systems/{test_ai_system.id}/high-risk-assessment",
        json={
            "answers": [
                {"question_id": "q1_hiring_decisions", "answer": True},
                {"question_id": "q2_cv_evaluation", "answer": False},
            ],
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    # Get history
    response = await client.get(
        f"/api/systems/{test_ai_system.id}/high-risk-assessment",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
