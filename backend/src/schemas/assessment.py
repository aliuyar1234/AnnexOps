"""Pydantic schemas for high-risk assessment endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.schemas.ai_system import UserSummary


class WizardQuestion(BaseModel):
    """Single wizard question."""

    id: str
    text: str
    help_text: str
    high_risk_indicator: bool


class WizardQuestions(BaseModel):
    """Response schema for wizard questions."""

    version: str
    questions: list[WizardQuestion]


class AnswerItem(BaseModel):
    """Single answer to a wizard question."""

    model_config = ConfigDict(extra="forbid")

    question_id: str = Field(..., min_length=1, max_length=100)
    answer: bool


class AssessmentSubmission(BaseModel):
    """Request schema for submitting an assessment."""

    model_config = ConfigDict(extra="forbid")

    answers: list[AnswerItem] = Field(..., min_length=1, max_length=200)
    notes: str | None = Field(None, max_length=2000)


class AssessmentResponse(BaseModel):
    """Response schema for a completed assessment."""

    id: UUID
    result_label: str
    score: int
    notes: str | None = None
    checklist: list[str] = []
    disclaimer: str
    created_by: UserSummary | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
