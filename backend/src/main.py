"""FastAPI application entry point."""

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.deps import get_current_user
from src.api.middleware import (
    RateLimitMiddleware,
    RequestLoggingMiddleware,
    SecurityHeadersMiddleware,
)
from src.api.routes import (
    assessments,
    attachments,
    audit_admin,
    auth,
    evidence,
    exports,
    llm,
    log_admin,
    logging,
    metrics,
    mappings,
    organizations,
    sections,
    systems,
    users,
    versions,
)
from src.core.config import get_settings
from src.models.user import User
from src.schemas.auth import UserResponse

settings = get_settings()
docs_enabled = settings.api_docs_enabled
if docs_enabled is None:
    docs_enabled = settings.environment != "production"

app = FastAPI(
    title="AnnexOps API",
    description="Organization & Authentication API for AnnexOps",
    version="1.0.0",
    docs_url="/api/docs" if docs_enabled else None,
    redoc_url="/api/redoc" if docs_enabled else None,
    openapi_url="/api/openapi.json" if docs_enabled else None,
)

# Middleware configuration (order matters - applied in reverse order)
# 1. Request logging (outermost - logs all requests)
app.add_middleware(RequestLoggingMiddleware)

# 2. Security headers
app.add_middleware(SecurityHeadersMiddleware)

# 3. Rate limiting (applied before routing)
app.add_middleware(RateLimitMiddleware)

# 4. CORS (applied after rate limiting)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


app.include_router(organizations.router, prefix="/api/organizations", tags=["organizations"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(systems.router, prefix="/api/systems", tags=["systems"])
app.include_router(assessments.router, prefix="/api/systems", tags=["assessments"])
app.include_router(attachments.router, prefix="/api/systems", tags=["attachments"])
app.include_router(versions.router, prefix="/api/systems", tags=["versions"])
app.include_router(evidence.router, prefix="/api/evidence", tags=["evidence"])
app.include_router(mappings.router, prefix="/api/systems", tags=["mappings"])
app.include_router(sections.router, prefix="/api/systems", tags=["sections"])
app.include_router(exports.router, prefix="/api", tags=["exports"])
app.include_router(log_admin.router, prefix="/api", tags=["logging"])
app.include_router(logging.router, prefix="/api/v1", tags=["logging"])
app.include_router(llm.router, prefix="/api", tags=["llm"])
app.include_router(metrics.router, prefix="/api", tags=["metrics"])
app.include_router(audit_admin.router, prefix="/api/admin", tags=["audit"])

# Register /me endpoint at root /api level (per OpenAPI spec)


@app.get("/api/me", response_model=UserResponse, tags=["auth"])
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information."""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        role=current_user.role.value,
        is_active=current_user.is_active,
        last_login_at=current_user.last_login_at,
        created_at=current_user.created_at,
    )
