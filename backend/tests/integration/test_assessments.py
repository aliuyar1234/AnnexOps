"""Integration tests for assessment operations."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import create_access_token
from src.models.ai_system import AISystem
from src.models.organization import Organization
from src.models.user import User


@pytest.mark.asyncio
async def test_assessment_flow(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """Test complete assessment flow: get questions -> submit -> view history."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Step 1: Get questions
    questions_response = await client.get(
        f"/api/systems/{test_ai_system.id}/high-risk-assessment/questions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert questions_response.status_code == 200
    questions = questions_response.json()["questions"]

    # Step 2: Submit assessment with all answers
    answers = [
        {"question_id": q["id"], "answer": i < 5}  # First 5 are True
        for i, q in enumerate(questions)
    ]

    submit_response = await client.post(
        f"/api/systems/{test_ai_system.id}/high-risk-assessment",
        json={"answers": answers, "notes": "Complete assessment test"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert submit_response.status_code == 201
    assessment = submit_response.json()
    assert assessment["score"] == 5
    assert assessment["result_label"] == "unclear"

    # Step 3: Verify in history
    history_response = await client.get(
        f"/api/systems/{test_ai_system.id}/high-risk-assessment",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert history_response.status_code == 200
    history = history_response.json()
    assert len(history) == 1
    assert history[0]["id"] == assessment["id"]


@pytest.mark.asyncio
async def test_multiple_assessments_ordered_by_date(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
):
    """Test that multiple assessments are ordered newest first."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    # Submit first assessment
    await client.post(
        f"/api/systems/{test_ai_system.id}/high-risk-assessment",
        json={
            "answers": [{"question_id": "q1_hiring_decisions", "answer": True}],
            "notes": "First assessment",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    # Submit second assessment
    second_response = await client.post(
        f"/api/systems/{test_ai_system.id}/high-risk-assessment",
        json={
            "answers": [{"question_id": "q1_hiring_decisions", "answer": False}],
            "notes": "Second assessment",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    second_id = second_response.json()["id"]

    # Get history - second should be first (newest)
    history_response = await client.get(
        f"/api/systems/{test_ai_system.id}/high-risk-assessment",
        headers={"Authorization": f"Bearer {token}"},
    )
    history = history_response.json()
    assert len(history) == 2
    assert history[0]["id"] == second_id  # Newest first


@pytest.mark.asyncio
async def test_assessment_for_nonexistent_system_returns_404(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
):
    """Test that assessment for non-existent system returns 404."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    response = await client.get(
        "/api/systems/00000000-0000-0000-0000-000000000000/high-risk-assessment/questions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
