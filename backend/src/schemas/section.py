"""Pydantic schemas for Annex IV section endpoints."""
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class SectionResponse(BaseModel):
    """Response schema for a single Annex IV section."""

    id: UUID = Field(description="Section ID")
    version_id: UUID = Field(description="System version ID")
    section_key: str = Field(description="Section key (e.g., ANNEX4.RISK_MANAGEMENT)")
    title: str = Field(description="Human-readable section title")
    content: dict = Field(default_factory=dict, description="JSONB section content")
    completeness_score: Decimal = Field(description="Completeness percentage (0-100)")
    evidence_refs: list[UUID] = Field(
        default_factory=list, description="List of evidence item IDs referenced by this section"
    )
    llm_assisted: bool = Field(description="Whether section content was LLM-assisted")
    last_edited_by: UUID | None = Field(None, description="User ID who last edited this section")
    updated_at: datetime = Field(description="Last update timestamp")

    class Config:
        from_attributes = True


class UpdateSectionRequest(BaseModel):
    """Request schema for updating a section."""

    content: dict | None = Field(None, description="JSONB section content to update")
    evidence_refs: list[UUID] | None = Field(
        None, description="List of evidence item IDs to associate with this section"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "content": {
                    "introduction": "This section describes our risk management approach...",
                    "subsections": [],
                },
                "evidence_refs": [
                    "123e4567-e89b-12d3-a456-426614174000",
                    "987fcdeb-51a2-43f7-b9d8-1234567890ab",
                ],
            }
        }


class SectionListResponse(BaseModel):
    """Response schema for listing sections."""

    items: list[SectionResponse] = Field(description="List of sections")
    total: int = Field(description="Total number of sections")

    class Config:
        json_schema_extra = {
            "example": {
                "items": [
                    {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "version_id": "987fcdeb-51a2-43f7-b9d8-1234567890ab",
                        "section_key": "ANNEX4.RISK_MANAGEMENT",
                        "title": "Risk Management System",
                        "content": {},
                        "completeness_score": 0,
                        "evidence_refs": [],
                        "llm_assisted": False,
                        "last_edited_by": None,
                        "updated_at": "2024-01-01T00:00:00Z",
                    }
                ],
                "total": 12,
            }
        }
