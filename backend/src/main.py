"""FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.core.config import get_settings
from src.api.middleware import RateLimitMiddleware, RequestLoggingMiddleware

settings = get_settings()

app = FastAPI(
    title="AnnexOps API",
    description="Organization & Authentication API for AnnexOps",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# Middleware configuration (order matters - applied in reverse order)
# 1. Request logging (outermost - logs all requests)
app.add_middleware(RequestLoggingMiddleware)

# 2. Rate limiting (applied before routing)
app.add_middleware(RateLimitMiddleware)

# 3. CORS (applied after rate limiting)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend development URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


# Router registration
from src.api.routes import organizations, auth, users, systems, assessments, attachments, versions, evidence, mappings, sections, exports

app.include_router(organizations.router, prefix="/api/organizations", tags=["organizations"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(systems.router, prefix="/api/systems", tags=["systems"])
app.include_router(assessments.router, prefix="/api/systems", tags=["assessments"])
app.include_router(attachments.router, prefix="/api/systems", tags=["attachments"])
app.include_router(versions.router, prefix="/api/systems", tags=["versions"])
app.include_router(evidence.router, prefix="/api/v1/evidence", tags=["evidence"])
app.include_router(mappings.router, prefix="/api/v1/systems", tags=["mappings"])
app.include_router(sections.router, prefix="/api/v1/systems", tags=["sections"])
app.include_router(exports.router, prefix="/api/v1", tags=["exports"])

# Register /me endpoint at root /api level (per OpenAPI spec)
from src.api.deps import get_current_user
from src.schemas.auth import UserResponse
from src.models.user import User
from fastapi import Depends

@app.get("/api/me", response_model=UserResponse, tags=["auth"])
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information."""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        role=current_user.role.value,
        is_active=current_user.is_active,
        last_login_at=current_user.last_login_at,
        created_at=current_user.created_at
    )
