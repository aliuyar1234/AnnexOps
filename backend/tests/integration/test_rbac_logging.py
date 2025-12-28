"""Integration tests for RBAC on logging endpoints (Module F)."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import create_access_token
from src.models.ai_system import AISystem
from src.models.system_version import SystemVersion
from src.models.user import User


@pytest.mark.asyncio
async def test_viewer_cannot_enable_logging(
    client: AsyncClient,
    db: AsyncSession,
    test_ai_system: AISystem,
    test_version: SystemVersion,
    test_viewer_user: User,
):
    """Viewer role cannot enable logging (requires editor+)."""
    token = create_access_token({"sub": str(test_viewer_user.id)})

    response = await client.post(
        f"/api/systems/{test_ai_system.id}/versions/{test_version.id}/logging/enable",
        json={"name": "Should Fail"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403

