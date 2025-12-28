"""Integration tests for Annex IV section functionality."""
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.annex_section import AnnexSection
from src.models.enums import AnnexSectionKey
from src.models.organization import Organization
from src.models.system_version import SystemVersion
from src.models.user import User
from src.services.section_service import SectionService


@pytest.mark.asyncio
async def test_list_sections_initializes_if_none_exist(
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_version: SystemVersion,
):
    """Test that listing sections initializes all 12 sections if none exist."""
    service = SectionService(db)

    # Verify no sections exist initially
    query = select(AnnexSection).where(AnnexSection.version_id == test_version.id)
    result = await db.execute(query)
    assert len(list(result.scalars().all())) == 0

    # List sections should initialize them
    sections = await service.list_sections(
        version_id=test_version.id,
        org_id=test_org.id,
    )

    assert len(sections) == 12
    for section in sections:
        assert section.version_id == test_version.id
        assert section.content == {}
        assert section.completeness_score == 0
        assert section.evidence_refs == []
        assert section.llm_assisted is False


@pytest.mark.asyncio
async def test_get_by_key_creates_section_if_not_exists(
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_version: SystemVersion,
):
    """Test that getting a section by key creates it if it doesn't exist."""
    service = SectionService(db)

    section = await service.get_by_key(
        version_id=test_version.id,
        section_key="ANNEX4.RISK_MANAGEMENT",
        org_id=test_org.id,
    )

    assert section is not None
    assert section.section_key == "ANNEX4.RISK_MANAGEMENT"
    assert section.version_id == test_version.id
    assert section.content == {}


@pytest.mark.asyncio
async def test_update_content_updates_section_and_recalculates_score(
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_version: SystemVersion,
):
    """Test updating section content recalculates completeness score."""
    service = SectionService(db)

    # Create initial section
    section = await service.get_by_key(
        version_id=test_version.id,
        section_key="ANNEX4.RISK_MANAGEMENT",
        org_id=test_org.id,
    )
    initial_score = section.completeness_score
    assert initial_score == 0

    # Update with partial content
    updated_section = await service.update_content(
        version_id=test_version.id,
        section_key="ANNEX4.RISK_MANAGEMENT",
        content={
            "risk_management_system_description": "Our risk management approach",
            "identified_risks": ["Risk 1", "Risk 2"],
        },
        evidence_refs=None,
        current_user=test_editor_user,
    )

    # Score should be recalculated and higher than 0
    assert updated_section.completeness_score > 0
    assert updated_section.last_edited_by == test_editor_user.id
    assert updated_section.content["risk_management_system_description"] == "Our risk management approach"


@pytest.mark.asyncio
async def test_update_content_updates_evidence_refs(
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_version: SystemVersion,
):
    """Test updating evidence references."""
    from uuid import uuid4

    service = SectionService(db)

    evidence_id_1 = uuid4()
    evidence_id_2 = uuid4()

    section = await service.update_content(
        version_id=test_version.id,
        section_key="ANNEX4.DATA_GOVERNANCE",
        content=None,  # Don't update content
        evidence_refs=[evidence_id_1, evidence_id_2],
        current_user=test_editor_user,
    )

    assert len(section.evidence_refs) == 2
    assert evidence_id_1 in section.evidence_refs
    assert evidence_id_2 in section.evidence_refs


@pytest.mark.asyncio
async def test_initialize_sections_creates_all_12_sections(
    db: AsyncSession,
    test_version: SystemVersion,
):
    """Test that initialize_sections creates all 12 Annex IV sections."""
    service = SectionService(db)

    sections = await service.initialize_sections(test_version.id)

    assert len(sections) == 12

    # Verify all section keys are present
    section_keys = {s.section_key for s in sections}
    expected_keys = {key.value for key in AnnexSectionKey}
    assert section_keys == expected_keys


@pytest.mark.asyncio
async def test_section_crud_flow(
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_version: SystemVersion,
):
    """Integration test for complete section CRUD flow."""
    from uuid import uuid4

    service = SectionService(db)

    # 1. List sections (should initialize all 12)
    sections = await service.list_sections(
        version_id=test_version.id,
        org_id=test_org.id,
    )
    assert len(sections) == 12

    # 2. Get specific section
    section = await service.get_by_key(
        version_id=test_version.id,
        section_key="ANNEX4.RISK_MANAGEMENT",
        org_id=test_org.id,
    )
    assert section.section_key == "ANNEX4.RISK_MANAGEMENT"

    # 3. Update section content
    evidence_id = uuid4()
    updated_section = await service.update_content(
        version_id=test_version.id,
        section_key="ANNEX4.RISK_MANAGEMENT",
        content={
            "risk_management_system_description": "Comprehensive risk management",
            "identified_risks": ["Risk A", "Risk B", "Risk C"],
            "risk_mitigation_measures": ["Mitigation 1"],
        },
        evidence_refs=[evidence_id],
        current_user=test_editor_user,
    )

    # 4. Verify updates
    assert updated_section.content["risk_management_system_description"] == "Comprehensive risk management"
    assert len(updated_section.content["identified_risks"]) == 3
    assert len(updated_section.evidence_refs) == 1
    assert updated_section.last_edited_by == test_editor_user.id
    assert updated_section.completeness_score > 0

    # 5. Get section again to verify persistence
    refreshed_section = await service.get_by_key(
        version_id=test_version.id,
        section_key="ANNEX4.RISK_MANAGEMENT",
        org_id=test_org.id,
    )
    assert refreshed_section.id == updated_section.id
    assert refreshed_section.content == updated_section.content
