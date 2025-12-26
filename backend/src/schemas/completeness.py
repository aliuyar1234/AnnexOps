"""Completeness dashboard schemas."""
from pydantic import BaseModel, Field
from uuid import UUID


class GapItem(BaseModel):
    """Individual gap in documentation completeness.

    Attributes:
        section_key: Section identifier (e.g., "ANNEX4.RISK_MANAGEMENT")
        gap_type: Type of gap ("required_field" or "no_evidence")
        description: Human-readable description of the gap
    """
    section_key: str = Field(..., description="Section identifier")
    gap_type: str = Field(..., description="Type of gap: required_field or no_evidence")
    description: str = Field(..., description="Description of the gap")


class SectionCompletenessItem(BaseModel):
    """Completeness details for a single section.

    Attributes:
        section_key: Section identifier
        title: Human-readable section title
        score: Completeness score (0-100)
        field_completion: Dictionary mapping field names to filled status
        evidence_count: Number of evidence items mapped to this section
        gaps: List of gap descriptions for this section
    """
    section_key: str = Field(..., description="Section identifier")
    title: str = Field(..., description="Human-readable section title")
    score: float = Field(..., ge=0, le=100, description="Completeness score (0-100)")
    field_completion: dict[str, bool] = Field(
        ...,
        description="Map of field names to filled status"
    )
    evidence_count: int = Field(..., ge=0, description="Number of evidence items")
    gaps: list[str] = Field(default_factory=list, description="List of gap descriptions")


class CompletenessResponse(BaseModel):
    """Complete dashboard response with overall and per-section completeness.

    Attributes:
        version_id: System version identifier
        overall_score: Weighted average completeness score (0-100)
        sections: List of section completeness details
        gaps: Aggregated list of all gaps across sections
    """
    version_id: UUID = Field(..., description="System version identifier")
    overall_score: float = Field(..., ge=0, le=100, description="Overall completeness score")
    sections: list[SectionCompletenessItem] = Field(
        default_factory=list,
        description="Per-section completeness details"
    )
    gaps: list[GapItem] = Field(
        default_factory=list,
        description="Aggregated list of all gaps"
    )

    class Config:
        """Pydantic model configuration."""
        json_schema_extra = {
            "example": {
                "version_id": "123e4567-e89b-12d3-a456-426614174000",
                "overall_score": 68.5,
                "sections": [
                    {
                        "section_key": "ANNEX4.GENERAL",
                        "title": "General Information",
                        "score": 100.0,
                        "field_completion": {
                            "provider_name": True,
                            "provider_address": True,
                            "system_name": True,
                            "system_version": True,
                            "conformity_declaration_date": True,
                        },
                        "evidence_count": 2,
                        "gaps": [],
                    },
                    {
                        "section_key": "ANNEX4.RISK_MANAGEMENT",
                        "title": "Risk Management System",
                        "score": 46.67,
                        "field_completion": {
                            "risk_management_system_description": True,
                            "identified_risks": False,
                            "risk_mitigation_measures": True,
                            "residual_risks": False,
                            "risk_acceptability_criteria": False,
                        },
                        "evidence_count": 1,
                        "gaps": [
                            "Missing required field: identified_risks",
                            "Missing required field: residual_risks",
                            "Missing required field: risk_acceptability_criteria",
                        ],
                    },
                ],
                "gaps": [
                    {
                        "section_key": "ANNEX4.RISK_MANAGEMENT",
                        "gap_type": "required_field",
                        "description": "Missing required field: identified_risks",
                    },
                    {
                        "section_key": "ANNEX4.RISK_MANAGEMENT",
                        "gap_type": "required_field",
                        "description": "Missing required field: residual_risks",
                    },
                ],
            }
        }
