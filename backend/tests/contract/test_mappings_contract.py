"""Contract tests for evidence mapping endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import create_access_token
from src.models.ai_system import AISystem
from src.models.enums import MappingTargetType
from src.models.evidence_item import EvidenceItem
from src.models.evidence_mapping import EvidenceMapping
from src.models.organization import Organization
from src.models.system_version import SystemVersion
from src.models.user import User
from tests.conftest import create_evidence_mapping


@pytest.mark.asyncio
async def test_create_mapping_returns_201(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
    test_version: SystemVersion,
    test_evidence_item: EvidenceItem,
):
    """POST /systems/{id}/versions/{vid}/evidence returns 201 with created mapping."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}/evidence",
        json={
            "evidence_id": str(test_evidence_item.id),
            "target_type": "section",
            "target_key": "ANNEX4.RISK_MANAGEMENT",
            "strength": "medium",
            "notes": "Risk management documentation",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["evidence_id"] == str(test_evidence_item.id)
    assert data["version_id"] == str(test_version.id)
    assert data["target_type"] == "section"
    assert data["target_key"] == "ANNEX4.RISK_MANAGEMENT"
    assert data["strength"] == "medium"
    assert data["notes"] == "Risk management documentation"
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_mapping_without_optional_fields_returns_201(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
    test_version: SystemVersion,
    test_evidence_item: EvidenceItem,
):
    """POST /systems/{id}/versions/{vid}/evidence returns 201 without strength/notes."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}/evidence",
        json={
            "evidence_id": str(test_evidence_item.id),
            "target_type": "field",
            "target_key": "hr_use_case_type",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["evidence_id"] == str(test_evidence_item.id)
    assert data["target_type"] == "field"
    assert data["target_key"] == "hr_use_case_type"
    assert data["strength"] is None
    assert data["notes"] is None


@pytest.mark.asyncio
async def test_create_mapping_returns_409_for_duplicate(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
    test_version: SystemVersion,
    test_evidence_item: EvidenceItem,
):
    """POST /systems/{id}/versions/{vid}/evidence returns 409 for duplicate mapping."""
    token = create_access_token({"sub": str(test_editor_user.id)})

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
    response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}/evidence",
        json={
            "evidence_id": str(test_evidence_item.id),
            "target_type": "section",
            "target_key": "ANNEX4.DATA_GOVERNANCE",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_create_mapping_returns_404_for_nonexistent_evidence(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
    test_version: SystemVersion,
):
    """POST /systems/{id}/versions/{vid}/evidence returns 404 for nonexistent evidence."""
    from uuid import uuid4

    token = create_access_token({"sub": str(test_editor_user.id)})

    response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}/evidence",
        json={
            "evidence_id": str(uuid4()),
            "target_type": "section",
            "target_key": "ANNEX4.RISK_MANAGEMENT",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_mapping_returns_404_for_nonexistent_version(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
    test_evidence_item: EvidenceItem,
):
    """POST /systems/{id}/versions/{vid}/evidence returns 404 for nonexistent version."""
    from uuid import uuid4

    token = create_access_token({"sub": str(test_editor_user.id)})

    response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions/{uuid4()}/evidence",
        json={
            "evidence_id": str(test_evidence_item.id),
            "target_type": "section",
            "target_key": "ANNEX4.RISK_MANAGEMENT",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_mapping_returns_403_for_viewer_role(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_viewer_user: User,
    test_ai_system: AISystem,
    test_version: SystemVersion,
    test_evidence_item: EvidenceItem,
):
    """POST /systems/{id}/versions/{vid}/evidence returns 403 for VIEWER role."""
    token = create_access_token({"sub": str(test_viewer_user.id)})

    response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}/evidence",
        json={
            "evidence_id": str(test_evidence_item.id),
            "target_type": "section",
            "target_key": "ANNEX4.RISK_MANAGEMENT",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_mappings_returns_200(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
    test_version: SystemVersion,
    test_evidence_mapping: EvidenceMapping,
):
    """GET /systems/{id}/versions/{vid}/evidence returns 200 with mappings list."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    response = await client.get(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}/evidence",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1

    # Verify nested evidence structure
    mapping = data[0]
    assert "id" in mapping
    assert "evidence_id" in mapping
    assert "evidence" in mapping
    assert "title" in mapping["evidence"]
    assert "type" in mapping["evidence"]


@pytest.mark.asyncio
async def test_list_mappings_with_target_type_filter_returns_200(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
    test_version: SystemVersion,
    test_evidence_item: EvidenceItem,
):
    """GET /systems/{id}/versions/{vid}/evidence?target_type=section returns filtered results."""
    token = create_access_token({"sub": str(test_editor_user.id)})

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
    await db.commit()

    response = await client.get(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}/evidence?target_type=section",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    for mapping in data:
        assert mapping["target_type"] == "section"


@pytest.mark.asyncio
async def test_list_mappings_with_target_key_filter_returns_200(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
    test_version: SystemVersion,
    test_evidence_item: EvidenceItem,
):
    """GET /systems/{id}/versions/{vid}/evidence?target_key=ANNEX4* returns prefix matches."""
    token = create_access_token({"sub": str(test_editor_user.id)})

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
        target_key="hr_use_case_type",
        created_by=test_editor_user.id,
    )
    await db.commit()

    response = await client.get(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}/evidence?target_key=ANNEX4*",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    for mapping in data:
        assert mapping["target_key"].startswith("ANNEX4")


@pytest.mark.asyncio
async def test_delete_mapping_returns_204(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
    test_version: SystemVersion,
    test_evidence_mapping: EvidenceMapping,
):
    """DELETE /systems/{id}/versions/{vid}/evidence/{mapping_id} returns 204."""
    token = create_access_token({"sub": str(test_editor_user.id)})

    response = await client.delete(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}/evidence/{test_evidence_mapping.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_delete_mapping_returns_404_for_nonexistent_mapping(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_editor_user: User,
    test_ai_system: AISystem,
    test_version: SystemVersion,
):
    """DELETE /systems/{id}/versions/{vid}/evidence/{mapping_id} returns 404 for nonexistent mapping."""
    from uuid import uuid4

    token = create_access_token({"sub": str(test_editor_user.id)})

    response = await client.delete(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}/evidence/{uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_mapping_returns_403_for_viewer_role(
    client: AsyncClient,
    db: AsyncSession,
    test_org: Organization,
    test_viewer_user: User,
    test_ai_system: AISystem,
    test_version: SystemVersion,
    test_evidence_mapping: EvidenceMapping,
):
    """DELETE /systems/{id}/versions/{vid}/evidence/{mapping_id} returns 403 for VIEWER role."""
    token = create_access_token({"sub": str(test_viewer_user.id)})

    response = await client.delete(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}/evidence/{test_evidence_mapping.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
