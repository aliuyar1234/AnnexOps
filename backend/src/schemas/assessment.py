"""Pydantic schemas for high-risk assessment endpoints."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

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

    question_id: str
    answer: bool


class AssessmentSubmission(BaseModel):
    """Request schema for submitting an assessment."""

    answers: list[AnswerItem]
    notes: Optional[str] = Field(None, max_length=2000)


class AssessmentResponse(BaseModel):
    """Response schema for a completed assessment."""

    id: UUID
    result_label: str
    score: int
    notes: Optional[str] = None
    checklist: list[str] = []
    disclaimer: str
    created_by: Optional[UserSummary] = None
    created_at: datetime

    class Config:
        from_attributes = True
