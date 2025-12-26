"""Integration tests for evidence mapping functionality."""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.models.organization import Organization
from src.models.user import User
from src.models.ai_system import AISystem
from src.models.system_version import SystemVersion
from src.models.evidence_item import EvidenceItem
from src.models.evidence_mapping import EvidenceMapping
from src.models.enums import MappingTargetType, MappingStrength, EvidenceType, Classification
from src.schemas.mapping import CreateMappingRequest
from src.services.mapping_service import MappingService
from tests.conftest import create_evidence_item, create_evidence_mapping


@pytest.mark.asyncio
async def test_create_mapping_success(
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_version: SystemVersion,
    test_evidence_item: EvidenceItem,
):
    """Test creating a mapping successfully."""
    service = MappingService(db)

    request = CreateMappingRequest(
        evidence_id=test_evidence_item.id,
        target_type=MappingTargetType.SECTION,
        target_key="ANNEX4.RISK_MANAGEMENT",
        strength=MappingStrength.STRONG,
        notes="Comprehensive risk management documentation",
    )

    mapping = await service.create(
        version_id=test_version.id,
        request=request,
        current_user=test_editor_user,
    )

    assert mapping.id is not None
    assert mapping.evidence_id == test_evidence_item.id
    assert mapping.version_id == test_version.id
    assert mapping.target_type == MappingTargetType.SECTION
    assert mapping.target_key == "ANNEX4.RISK_MANAGEMENT"
    assert mapping.strength == MappingStrength.STRONG
    assert mapping.notes == "Comprehensive risk management documentation"
    assert mapping.created_by == test_editor_user.id


@pytest.mark.asyncio
async def test_create_mapping_enforces_unique_constraint(
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_version: SystemVersion,
    test_evidence_item: EvidenceItem,
):
    """Test that creating duplicate mapping raises conflict error."""
    service = MappingService(db)

    # Create first mapping
    await create_evidence_mapping(
        db,
        evidence_id=test_evidence_item.id,
        version_id=test_version.id,
        target_type=MappingTargetType.SECTION,
        target_key="ANNEX4.DATA_GOVERNANCE",
        created_by=test_editor_user.id,
    )
    await db.commit()

    # Attempt to create duplicate
    request = CreateMappingRequest(
        evidence_id=test_evidence_item.id,
        target_type=MappingTargetType.SECTION,
        target_key="ANNEX4.DATA_GOVERNANCE",
    )

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await service.create(
            version_id=test_version.id,
            request=request,
            current_user=test_editor_user,
        )

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_create_mapping_different_target_types_allowed(
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_version: SystemVersion,
    test_evidence_item: EvidenceItem,
):
    """Test that same evidence can map to different target types of same key."""
    service = MappingService(db)

    # Create section mapping
    request1 = CreateMappingRequest(
        evidence_id=test_evidence_item.id,
        target_type=MappingTargetType.SECTION,
        target_key="RISK_MANAGEMENT",
    )
    mapping1 = await service.create(
        version_id=test_version.id,
        request=request1,
        current_user=test_editor_user,
    )
    await db.commit()

    # Create field mapping with same key but different type - should succeed
    request2 = CreateMappingRequest(
        evidence_id=test_evidence_item.id,
        target_type=MappingTargetType.FIELD,
        target_key="RISK_MANAGEMENT",
    )
    mapping2 = await service.create(
        version_id=test_version.id,
        request=request2,
        current_user=test_editor_user,
    )

    assert mapping1.id != mapping2.id
    assert mapping1.target_type != mapping2.target_type


@pytest.mark.asyncio
async def test_list_mappings_with_nested_evidence(
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_version: SystemVersion,
    test_evidence_item: EvidenceItem,
):
    """Test listing mappings returns nested evidence details."""
    service = MappingService(db)

    # Create multiple mappings
    await create_evidence_mapping(
        db,
        evidence_id=test_evidence_item.id,
        version_id=test_version.id,
        target_type=MappingTargetType.SECTION,
        target_key="ANNEX4.RISK_MANAGEMENT",
        created_by=test_editor_user.id,
    )
    await create_evidence_mapping(
        db,
        evidence_id=test_evidence_item.id,
        version_id=test_version.id,
        target_type=MappingTargetType.FIELD,
        target_key="hr_use_case_type",
        created_by=test_editor_user.id,
    )
    await db.commit()

    mappings = await service.list(
        version_id=test_version.id,
        org_id=test_org.id,
    )

    assert len(mappings) == 2
    for mapping in mappings:
        assert mapping.evidence_item is not None
        assert mapping.evidence_item.id == test_evidence_item.id
        assert mapping.evidence_item.title == test_evidence_item.title


@pytest.mark.asyncio
async def test_list_mappings_filters_by_target_type(
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_version: SystemVersion,
    test_evidence_item: EvidenceItem,
):
    """Test filtering mappings by target type."""
    service = MappingService(db)

    # Create mappings with different target types
    await create_evidence_mapping(
        db,
        evidence_id=test_evidence_item.id,
        version_id=test_version.id,
        target_type=MappingTargetType.SECTION,
        target_key="ANNEX4.RISK_MANAGEMENT",
        created_by=test_editor_user.id,
    )
    await create_evidence_mapping(
        db,
        evidence_id=test_evidence_item.id,
        version_id=test_version.id,
        target_type=MappingTargetType.FIELD,
        target_key="hr_use_case_type",
        created_by=test_editor_user.id,
    )
    await create_evidence_mapping(
        db,
        evidence_id=test_evidence_item.id,
        version_id=test_version.id,
        target_type=MappingTargetType.REQUIREMENT,
        target_key="REQ_001",
        created_by=test_editor_user.id,
    )
    await db.commit()

    # Filter by SECTION
    section_mappings = await service.list(
        version_id=test_version.id,
        org_id=test_org.id,
        target_type=MappingTargetType.SECTION,
    )

    assert len(section_mappings) == 1
    assert section_mappings[0].target_type == MappingTargetType.SECTION


@pytest.mark.asyncio
async def test_list_mappings_filters_by_target_key_exact(
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_version: SystemVersion,
    test_evidence_item: EvidenceItem,
):
    """Test filtering mappings by exact target key."""
    service = MappingService(db)

    # Create mappings with different target keys
    await create_evidence_mapping(
        db,
        evidence_id=test_evidence_item.id,
        version_id=test_version.id,
        target_type=MappingTargetType.SECTION,
        target_key="ANNEX4.RISK_MANAGEMENT",
        created_by=test_editor_user.id,
    )
    await create_evidence_mapping(
        db,
        evidence_id=test_evidence_item.id,
        version_id=test_version.id,
        target_type=MappingTargetType.FIELD,
        target_key="ANNEX4.DATA_GOVERNANCE",
        created_by=test_editor_user.id,
    )
    await db.commit()

    # Filter by exact key
    mappings = await service.list(
        version_id=test_version.id,
        org_id=test_org.id,
        target_key="ANNEX4.RISK_MANAGEMENT",
    )

    assert len(mappings) == 1
    assert mappings[0].target_key == "ANNEX4.RISK_MANAGEMENT"


@pytest.mark.asyncio
async def test_list_mappings_filters_by_target_key_prefix(
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_version: SystemVersion,
    test_evidence_item: EvidenceItem,
):
    """Test filtering mappings by target key prefix."""
    service = MappingService(db)

    # Create mappings with different target keys
    await create_evidence_mapping(
        db,
        evidence_id=test_evidence_item.id,
        version_id=test_version.id,
        target_type=MappingTargetType.SECTION,
        target_key="ANNEX4.RISK_MANAGEMENT",
        created_by=test_editor_user.id,
    )
    await create_evidence_mapping(
        db,
        evidence_id=test_evidence_item.id,
        version_id=test_version.id,
        target_type=MappingTargetType.FIELD,
        target_key="ANNEX4.DATA_GOVERNANCE",
        created_by=test_editor_user.id,
    )
    await create_evidence_mapping(
        db,
        evidence_id=test_evidence_item.id,
        version_id=test_version.id,
        target_type=MappingTargetType.REQUIREMENT,
        target_key="REQ_001",
        created_by=test_editor_user.id,
    )
    await db.commit()

    # Filter by prefix
    mappings = await service.list(
        version_id=test_version.id,
        org_id=test_org.id,
        target_key="ANNEX4*",
    )

    assert len(mappings) == 2
    for mapping in mappings:
        assert mapping.target_key.startswith("ANNEX4")


@pytest.mark.asyncio
async def test_delete_mapping_success(
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_version: SystemVersion,
    test_evidence_mapping: EvidenceMapping,
):
    """Test deleting a mapping successfully."""
    service = MappingService(db)

    await service.delete(
        mapping_id=test_evidence_mapping.id,
        version_id=test_version.id,
        current_user=test_editor_user,
    )
    await db.commit()

    # Verify deletion
    query = select(EvidenceMapping).where(EvidenceMapping.id == test_evidence_mapping.id)
    result = await db.execute(query)
    deleted_mapping = result.scalar_one_or_none()

    assert deleted_mapping is None


@pytest.mark.asyncio
async def test_delete_mapping_not_found(
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_version: SystemVersion,
):
    """Test deleting nonexistent mapping raises 404."""
    from uuid import uuid4
    from fastapi import HTTPException

    service = MappingService(db)

    with pytest.raises(HTTPException) as exc_info:
        await service.delete(
            mapping_id=uuid4(),
            version_id=test_version.id,
            current_user=test_editor_user,
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_mapping_query_respects_organization_boundaries(
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_version: SystemVersion,
    test_evidence_item: EvidenceItem,
):
    """Test that mappings respect organization boundaries."""
    from src.models.enums import UserRole
    from tests.conftest import create_user, create_ai_system, create_version, create_evidence_item

    # Create second organization with its own data
    org2 = Organization(name="Other Organization")
    db.add(org2)
    await db.flush()

    user2 = await create_user(db, org2.id, "user2@test.com", role=UserRole.EDITOR)
    system2 = await create_ai_system(db, org2.id, "System 2", owner_user_id=user2.id)
    version2 = await create_version(db, system2.id, "1.0.0", created_by=user2.id)
    evidence2 = await create_evidence_item(
        db,
        org_id=org2.id,
        type=EvidenceType.NOTE,
        title="Org2 Evidence",
        created_by=user2.id,
        type_metadata={"content": "Test"},
    )
    await db.commit()

    # Create mapping in org2
    await create_evidence_mapping(
        db,
        evidence_id=evidence2.id,
        version_id=version2.id,
        target_type=MappingTargetType.SECTION,
        target_key="ANNEX4.RISK_MANAGEMENT",
        created_by=user2.id,
    )
    await db.commit()

    # List mappings as test_org user - should only see test_org mappings
    service = MappingService(db)
    mappings = await service.list(
        version_id=test_version.id,
        org_id=test_org.id,
    )

    # Should not include org2's mappings
    for mapping in mappings:
        assert mapping.version_id != version2.id
