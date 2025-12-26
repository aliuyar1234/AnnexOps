"""Organization API endpoints.

Implements organization management endpoints per OpenAPI spec in
specs/001-org-auth/contracts/openapi.yaml
"""
from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.database import get_db
from src.api.deps import get_current_user, require_admin
from src.models.user import User
from src.schemas.organization import (
    CreateOrganizationRequest,
    OrganizationResponse,
    OrganizationUpdateRequest
)
from src.services.org_service import OrganizationService

router = APIRouter()


@router.post(
    "",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create organization (bootstrap only)",
    description="Creates organization with initial admin user. Only allowed when no organizations exist."
)
async def create_organization(
    request: CreateOrganizationRequest,
    db: AsyncSession = Depends(get_db)
) -> OrganizationResponse:
    """Create organization with initial admin user (bootstrap).

    This endpoint is only available when no organization exists yet.
    It creates the organization and provisions an admin user account.

    Args:
        request: Organization creation request with admin credentials
        db: Database session

    Returns:
        Created organization details

    Raises:
        HTTPException: 409 if organization already exists
        HTTPException: 422 if validation fails
    """
    service = OrganizationService(db)
    organization = await service.create(
        name=request.name,
        admin_email=request.admin_email,
        admin_password=request.admin_password
    )
    return OrganizationResponse.model_validate(organization)


@router.get(
    "/{org_id}",
    response_model=OrganizationResponse,
    summary="Get organization details",
    description="Retrieve organization details by ID. Requires authentication."
)
async def get_organization(
    org_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> OrganizationResponse:
    """Get organization by ID.

    Args:
        org_id: Organization ID
        db: Database session
        current_user: Authenticated user

    Returns:
        Organization details

    Raises:
        HTTPException: 404 if organization not found
        HTTPException: 401 if not authenticated
    """
    service = OrganizationService(db)
    organization = await service.get_by_id(org_id)
    return OrganizationResponse.model_validate(organization)


@router.patch(
    "/{org_id}",
    response_model=OrganizationResponse,
    summary="Update organization (admin only)",
    description="Update organization details. Requires admin role."
)
async def update_organization(
    org_id: UUID,
    request: OrganizationUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin())
) -> OrganizationResponse:
    """Update organization details.

    Only admin users can update organization details.
    Creates audit log entry for the change.

    Args:
        org_id: Organization ID
        request: Organization update request
        db: Database session
        current_user: Authenticated admin user

    Returns:
        Updated organization details

    Raises:
        HTTPException: 404 if organization not found
        HTTPException: 403 if user is not admin
        HTTPException: 401 if not authenticated
    """
    service = OrganizationService(db)
    organization = await service.update(
        org_id=org_id,
        user_id=current_user.id,
        name=request.name
    )
    return OrganizationResponse.model_validate(organization)
