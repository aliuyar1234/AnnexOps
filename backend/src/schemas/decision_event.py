"""Pydantic schemas for decision event ingestion (Module F)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SubjectInfo(BaseModel):
    """Subject information for a decision event (hashed by default)."""

    model_config = ConfigDict(extra="forbid")

    subject_type: str = Field(..., min_length=1, max_length=50)
    subject_id_hash: str | None = Field(
        None,
        min_length=1,
        max_length=200,
        description="Hashed identifier (preferred; no raw PII).",
    )
    subject_id: str | None = Field(
        None,
        min_length=1,
        max_length=200,
        description="Raw identifier (only allowed when ALLOW_RAW_PII=true).",
    )

    @model_validator(mode="after")
    def validate_subject_identifier(self) -> SubjectInfo:
        if not self.subject_id_hash and not self.subject_id:
            raise ValueError("subject must include subject_id_hash or subject_id")
        return self


class ModelInfo(BaseModel):
    """Model metadata used for the decision."""

    model_config = ConfigDict(extra="forbid")

    model_id: str = Field(..., min_length=1, max_length=200)
    model_version: str = Field(..., min_length=1, max_length=200)
    prompt_version: str | None = Field(None, min_length=1, max_length=200)


class InputInfo(BaseModel):
    """Input metadata (hash + optional feature summary)."""

    model_config = ConfigDict(extra="forbid")

    input_hash: str = Field(..., min_length=1, max_length=200)
    features_summary: dict[str, Any] | None = None


class OutputInfo(BaseModel):
    """Output metadata (decision + optional score + hash)."""

    model_config = ConfigDict(extra="forbid")

    decision: str = Field(..., min_length=1, max_length=100)
    score: float | None = None
    output_hash: str = Field(..., min_length=1, max_length=200)


class HumanInfo(BaseModel):
    """Optional human-in-the-loop metadata."""

    model_config = ConfigDict(extra="forbid")

    reviewer_id: str | None = Field(None, min_length=1, max_length=200)
    override: bool = False
    override_reason: str | None = Field(None, min_length=1, max_length=500)


class TraceInfo(BaseModel):
    """Optional tracing metadata."""

    model_config = ConfigDict(extra="forbid")

    request_id: str | None = Field(None, min_length=1, max_length=200)
    latency_ms: int | None = Field(None, ge=0)
    error: str | None = Field(None, min_length=1, max_length=500)


class DecisionEvent(BaseModel):
    """Top-level decision event schema (strict)."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(..., min_length=1, max_length=255)
    event_time: datetime
    actor: str = Field(..., min_length=1, max_length=255)
    subject: SubjectInfo
    model: ModelInfo
    input: InputInfo
    output: OutputInfo
    human: HumanInfo | None = None
    trace: TraceInfo | None = None
