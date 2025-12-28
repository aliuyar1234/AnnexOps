"""Gap suggestion service (Module G)."""

from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.prompts import GAP_SUGGESTIONS_DISCLAIMER
from src.core.section_schemas import SECTION_SCHEMAS
from src.models.llm_interaction import LlmInteraction
from src.models.user import User
from src.schemas.llm import GapSuggestion, GapSuggestionResponse
from src.services.llm_service import LlmService
from src.services.section_service import SectionService

_DEFAULT_ARTIFACT_TYPES = [
    "Policy document",
    "Procedure description",
    "Test report",
]

_FIELD_ARTIFACT_TYPES: dict[str, list[str]] = {
    "training_data_sources": ["Dataset inventory", "Dataset card", "Data lineage document"],
    "training_data_characteristics": ["Dataset card", "Data dictionary", "Sampling report"],
    "data_quality_measures": ["Quality assurance report", "Data validation logs"],
    "data_preprocessing_steps": [
        "ETL pipeline documentation",
        "Preprocessing scripts",
        "Data processing report",
    ],
    "bias_assessment": ["Bias assessment report", "Fairness evaluation", "Mitigation plan"],
    "data_protection_measures": ["DPIA", "Access control policy", "Retention policy"],
    "risk_management_system_description": ["Risk management policy", "Process description"],
    "identified_risks": ["Risk register", "Hazard analysis"],
    "risk_mitigation_measures": ["Mitigation plan", "Control implementation notes"],
    "residual_risks": ["Residual risk assessment", "Risk acceptance record"],
    "risk_acceptability_criteria": ["Risk criteria document", "Acceptance thresholds"],
}


def _suggest_artifacts_for_field(field: str) -> list[str]:
    if field in _FIELD_ARTIFACT_TYPES:
        return _FIELD_ARTIFACT_TYPES[field]

    lowered = field.lower()
    if "data" in lowered:
        return ["Data dictionary", "Dataset card", "Data lineage document"]
    if "risk" in lowered:
        return ["Risk assessment", "Risk register", "Mitigation plan"]
    if "test" in lowered or "validation" in lowered:
        return ["Test report", "Validation report", "Benchmark results"]
    if "process" in lowered or "procedure" in lowered:
        return ["Process description", "SOP", "Work instruction"]

    return _DEFAULT_ARTIFACT_TYPES


class GapService:
    """Service for generating gap suggestions without making system claims."""

    def __init__(self, db: AsyncSession, llm_service: LlmService | None = None):
        self.db = db
        self.llm_service = llm_service or LlmService()

    async def suggest_gaps(
        self,
        *,
        section_key: str,
        version_id: UUID,
        current_user: User,
    ) -> GapSuggestionResponse:
        section_service = SectionService(self.db)
        section = await section_service.get_by_key(
            version_id=version_id,
            section_key=section_key,
            org_id=current_user.org_id,
        )

        required_fields = SECTION_SCHEMAS.get(section_key, [])
        content = section.content or {}
        missing = [f for f in required_fields if content.get(f) in (None, "", [])]

        suggestions = [
            GapSuggestion(field=field, artifact_types=_suggest_artifacts_for_field(field))
            for field in missing
        ]

        # Log request/response for audit (even though this is deterministic)
        interaction = LlmInteraction(
            version_id=version_id,
            section_key=section_key,
            user_id=current_user.id,
            selected_evidence_ids=[],
            prompt=f"[GAPS] Missing fields for {section_key}: {', '.join(missing) if missing else 'none'}",
            response=json.dumps(
                {
                    "suggestions": [s.model_dump() for s in suggestions],
                    "disclaimer": GAP_SUGGESTIONS_DISCLAIMER,
                },
                ensure_ascii=False,
            ),
            cited_evidence_ids=[],
            model=self.llm_service.settings.llm_model,
            input_tokens=0,
            output_tokens=0,
            strict_mode=False,
            duration_ms=0,
        )
        self.db.add(interaction)
        await self.db.flush()

        return GapSuggestionResponse(
            suggestions=suggestions,
            disclaimer=GAP_SUGGESTIONS_DISCLAIMER,
        )
