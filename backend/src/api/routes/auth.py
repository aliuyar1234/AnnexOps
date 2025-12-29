"""Authentication endpoints for login, logout, token refresh, and current user."""

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user, require_admin
from src.core.config import get_settings
from src.core.database import get_db
from src.models.user import User
from src.schemas.auth import LoginRequest, LogoutResponse, TokenResponse
from src.schemas.invitation import (
    AcceptInviteRequest,
    AcceptInviteResponse,
    InvitationResponse,
    InviteRequest,
)
from src.services.auth_service import AuthService
from src.services.invitation_service import InvitationService

settings = get_settings()
router = APIRouter()


def get_client_ip(request: Request) -> str | None:
    """Extract client IP address from request.

    Args:
        request: FastAPI request object

    Returns:
        Client IP address or None
    """
    # Try to get real IP from X-Forwarded-For header (if behind proxy)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    # Fall back to direct client host
    return request.client.host if request.client else None


@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def login(
    login_data: LoginRequest,
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """User login endpoint.

    Authenticates user with email and password, returns access token,
    and sets refresh token as httpOnly cookie.

    Tracks failed login attempts and implements account lockout after 5 failures
    with exponential backoff (1, 2, 4, 8, 15 minutes).

    Args:
        login_data: Login credentials (email, password)
        response: FastAPI response object for setting cookies
        request: FastAPI request object for IP tracking
        db: Database session

    Returns:
        TokenResponse with access token and metadata

    Raises:
        HTTPException: 401 if credentials are invalid
        HTTPException: 403 if account is inactive
        HTTPException: 423 if account is locked
    """
    auth_service = AuthService(db)
    client_ip = get_client_ip(request)

    # Authenticate user
    access_token, refresh_token, user = await auth_service.login(
        email=login_data.email, password=login_data.password, ip_address=client_ip
    )

    cookie_secure = (
        settings.refresh_cookie_secure
        if settings.refresh_cookie_secure is not None
        else settings.environment == "production"
    )

    # Set refresh token as httpOnly cookie for security
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=refresh_token,
        httponly=True,
        secure=cookie_secure,
        samesite=settings.refresh_cookie_samesite,
        path=settings.refresh_cookie_path,
        domain=settings.refresh_cookie_domain,
        max_age=settings.jwt_refresh_token_expire_days * 24 * 60 * 60,  # 7 days in seconds
    )

    # Commit transaction
    await db.commit()

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,  # Convert to seconds
    )


@router.post("/logout", response_model=LogoutResponse, status_code=status.HTTP_200_OK)
async def logout(
    response: Response,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """User logout endpoint.

    Logs out current user and clears refresh token cookie.

    Args:
        response: FastAPI response object for clearing cookies
        request: FastAPI request object for IP tracking
        current_user: Current authenticated user
        db: Database session

    Returns:
        LogoutResponse with success message

    Raises:
        HTTPException: 401 if not authenticated
    """
    auth_service = AuthService(db)
    client_ip = get_client_ip(request)

    # Log logout event
    await auth_service.logout(user=current_user, ip_address=client_ip)

    # Clear refresh token cookie
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        httponly=True,
        secure=settings.refresh_cookie_secure
        if settings.refresh_cookie_secure is not None
        else settings.environment == "production",
        samesite=settings.refresh_cookie_samesite,
        path=settings.refresh_cookie_path,
        domain=settings.refresh_cookie_domain,
    )

    # Commit transaction
    await db.commit()

    return LogoutResponse(message="Logged out successfully")


@router.post("/refresh", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def refresh_token(
    refresh_token: str | None = Cookie(None, alias=settings.refresh_cookie_name),
    db: AsyncSession = Depends(get_db),
):
    """Refresh access token endpoint.

    Creates new access token from refresh token cookie.

    Args:
        refresh_token: Refresh token from httpOnly cookie
        db: Database session

    Returns:
        TokenResponse with new access token

    Raises:
        HTTPException: 401 if refresh token is invalid or missing
    """
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token not found"
        )

    auth_service = AuthService(db)

    # Create new access token
    access_token = await auth_service.refresh_access_token(refresh_token)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post("/invite", response_model=InvitationResponse, status_code=status.HTTP_201_CREATED)
async def create_invitation(
    invite_data: InviteRequest,
    request: Request,
    current_user: User = Depends(require_admin()),
    db: AsyncSession = Depends(get_db),
):
    """Create invitation endpoint (admin only).

    Creates an invitation for a new user to join the organization.
    Generates a secure token with 7-day expiry and stores SHA-256 hash.
    Plaintext token is returned for email delivery.

    Args:
        invite_data: Invitation details (email, role)
        request: FastAPI request object for IP tracking
        current_user: Current authenticated admin user
        db: Database session

    Returns:
        InvitationResponse with invitation details and plaintext token

    Raises:
        HTTPException: 400 if user exists or duplicate invitation
        HTTPException: 403 if not admin
    """
    invitation_service = InvitationService(db)
    client_ip = get_client_ip(request)

    # Create invitation
    invitation, plaintext_token = await invitation_service.create_invitation(
        email=invite_data.email,
        role=invite_data.role,
        invited_by_user=current_user,
        ip_address=client_ip,
    )

    # Commit transaction
    await db.commit()

    return InvitationResponse(
        id=invitation.id,
        email=invitation.email,
        role=invitation.role.value,
        token=plaintext_token,  # Return plaintext token for email
        expires_at=invitation.expires_at,
    )


@router.post(
    "/accept-invite", response_model=AcceptInviteResponse, status_code=status.HTTP_201_CREATED
)
async def accept_invitation(
    accept_data: AcceptInviteRequest, request: Request, db: AsyncSession = Depends(get_db)
):
    """Accept invitation endpoint.

    Validates invitation token, creates user account with provided password,
    and marks invitation as accepted. Does not require authentication.

    Args:
        accept_data: Token and password
        request: FastAPI request object for IP tracking
        db: Database session

    Returns:
        AcceptInviteResponse with created user details

    Raises:
        HTTPException: 400 if token invalid, expired, or already used
    """
    invitation_service = InvitationService(db)
    client_ip = get_client_ip(request)

    # Accept invitation and create user
    user = await invitation_service.accept_invitation(
        token=accept_data.token, password=accept_data.password, ip_address=client_ip
    )

    # Commit transaction
    await db.commit()

    return AcceptInviteResponse(
        id=user.id,
        email=user.email,
        role=user.role.value,
        org_id=user.org_id,
        is_active=user.is_active,
        created_at=user.created_at,
    )


# Note: /me endpoint is registered in main.py at /api/me (not /api/auth/me)
# per OpenAPI spec requirements
