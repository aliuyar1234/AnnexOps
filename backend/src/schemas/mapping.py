"""Pydantic schemas for evidence mapping endpoints."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from src.models.enums import MappingTargetType, MappingStrength
from src.schemas.evidence import EvidenceResponse


class CreateMappingRequest(BaseModel):
    """Request schema for creating an evidence mapping."""

    evidence_id: UUID = Field(..., description="Evidence item to map")
    target_type: MappingTargetType = Field(..., description="Target type (section/field/requirement)")
    target_key: str = Field(..., min_length=1, max_length=100, description="Target key (e.g., 'ANNEX4.RISK_MANAGEMENT')")
    strength: Optional[MappingStrength] = Field(None, description="Mapping strength (weak/medium/strong)")
    notes: Optional[str] = Field(None, description="Mapping rationale and notes")


class MappingResponse(BaseModel):
    """Response schema for evidence mapping."""

    id: UUID
    evidence_id: UUID
    version_id: UUID
    target_type: MappingTargetType
    target_key: str
    strength: Optional[MappingStrength] = None
    notes: Optional[str] = None
    created_by: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class MappingWithEvidence(BaseModel):
    """Response schema for evidence mapping with nested evidence details."""

    id: UUID
    evidence_id: UUID
    version_id: UUID
    target_type: MappingTargetType
    target_key: str
    strength: Optional[MappingStrength] = None
    notes: Optional[str] = None
    created_by: UUID
    created_at: datetime
    evidence: EvidenceResponse

    class Config:
        from_attributes = True
