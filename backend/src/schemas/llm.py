"""Pydantic schemas for LLM Assist (Module G)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DraftRequest(BaseModel):
    """Request schema for generating an LLM draft."""

    model_config = ConfigDict(extra="forbid")

    version_id: UUID = Field(description="System version ID")
    selected_evidence_ids: list[UUID] = Field(
        default_factory=list,
        max_length=50,
        description="Evidence items selected by the user",
    )
    instructions: str | None = Field(
        default=None,
        max_length=2000,
        description="Optional user guidance (tone, focus areas)",
    )

    @field_validator("instructions")
    @classmethod
    def strip_instructions(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None


class DraftResponse(BaseModel):
    """Response schema for draft generation."""

    draft_text: str = Field(description="Generated markdown draft or placeholder")
    cited_evidence_ids: list[UUID] = Field(
        default_factory=list, description="Evidence IDs cited in the draft"
    )
    warnings: list[str] = Field(default_factory=list, description="Warnings list")
    strict_mode: bool = Field(description="Whether strict mode was activated")
    model_info: str | None = Field(
        default=None, description="Model identifier (null when no LLM call was made)"
    )
    interaction_id: UUID = Field(description="LLM interaction audit record ID")


class GapRequest(BaseModel):
    """Request schema for gap suggestions."""

    model_config = ConfigDict(extra="forbid")

    version_id: UUID = Field(description="System version ID")


class GapSuggestion(BaseModel):
    """Single gap suggestion item."""

    field: str = Field(description="Missing field key")
    artifact_types: list[str] = Field(
        default_factory=list, description="Suggested artifact types to provide"
    )


class GapSuggestionResponse(BaseModel):
    """Response schema for gap suggestions."""

    suggestions: list[GapSuggestion] = Field(default_factory=list)
    disclaimer: str = Field(description="Disclaimer that suggestions are not claims")


class LlmInteractionResponse(BaseModel):
    """Response schema for a single LLM interaction (audit)."""

    id: UUID
    version_id: UUID
    section_key: str
    user_id: UUID
    selected_evidence_ids: list[UUID]
    cited_evidence_ids: list[UUID]
    prompt: str
    response: str
    model: str
    input_tokens: int
    output_tokens: int
    strict_mode: bool
    duration_ms: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LlmHistoryListResponse(BaseModel):
    """Response schema for listing interactions for a version."""

    items: list[LlmInteractionResponse] = Field(default_factory=list)
    total: int = Field(description="Total interactions returned")


class LlmStatusResponse(BaseModel):
    """Response schema for reporting LLM availability/config (admin)."""        

    llm_enabled: bool
    llm_available: bool
    provider: str
    model: str
    provider_configured: bool = Field(
        description="Whether provider credentials/config are present (never includes secrets)"
    )


class LlmUsageTotals(BaseModel):
    """Aggregated usage totals for LLM interactions."""

    interactions: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    avg_duration_ms: float | None = Field(default=None, ge=0)


class LlmUsageDay(BaseModel):
    """Daily usage bucket."""

    day: datetime
    interactions: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)


class LlmUsageResponse(BaseModel):
    """Response schema for usage reporting (admin)."""

    all_time: LlmUsageTotals
    period_days: int = Field(ge=1, le=365)
    period: LlmUsageTotals
    by_day: list[LlmUsageDay] = Field(default_factory=list)
