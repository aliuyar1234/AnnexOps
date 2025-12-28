"""Pydantic schemas for evidence mapping endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.models.enums import MappingStrength, MappingTargetType
from src.schemas.evidence import EvidenceResponse


class CreateMappingRequest(BaseModel):
    """Request schema for creating an evidence mapping."""

    evidence_id: UUID = Field(..., description="Evidence item to map")
    target_type: MappingTargetType = Field(
        ..., description="Target type (section/field/requirement)"
    )
    target_key: str = Field(
        ..., min_length=1, max_length=100, description="Target key (e.g., 'ANNEX4.RISK_MANAGEMENT')"
    )
    strength: MappingStrength | None = Field(
        None, description="Mapping strength (weak/medium/strong)"
    )
    notes: str | None = Field(None, description="Mapping rationale and notes")


class MappingResponse(BaseModel):
    """Response schema for evidence mapping."""

    id: UUID
    evidence_id: UUID
    version_id: UUID
    target_type: MappingTargetType
    target_key: str
    strength: MappingStrength | None = None
    notes: str | None = None
    created_by: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MappingWithEvidence(BaseModel):
    """Response schema for evidence mapping with nested evidence details."""

    id: UUID
    evidence_id: UUID
    version_id: UUID
    target_type: MappingTargetType
    target_key: str
    strength: MappingStrength | None = None
    notes: str | None = None
    created_by: UUID
    created_at: datetime
    evidence: EvidenceResponse

    model_config = ConfigDict(from_attributes=True)
