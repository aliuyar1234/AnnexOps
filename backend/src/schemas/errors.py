"""Error response schemas matching OpenAPI specification."""
from pydantic import BaseModel, Field
from typing import Optional


class ErrorResponse(BaseModel):
    """Standard error response schema.

    Used for all error responses (4xx, 5xx) across the API.
    """

    error: str = Field(
        ...,
        description="Error type identifier",
        examples=["invalid_credentials", "account_locked", "permission_denied"]
    )
    message: str = Field(
        ...,
        description="Human-readable error message",
        examples=["Invalid email or password", "Account is temporarily locked"]
    )
    details: Optional[dict] = Field(
        None,
        description="Additional error context (field validation errors, etc.)",
        examples=[{"email": "Invalid email format"}]
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "error": "invalid_credentials",
                    "message": "Invalid email or password"
                },
                {
                    "error": "account_locked",
                    "message": "Account is temporarily locked. Try again in 5 minutes."
                },
                {
                    "error": "validation_error",
                    "message": "Request validation failed",
                    "details": {
                        "email": "Invalid email format",
                        "password": "Password must be at least 8 characters"
                    }
                }
            ]
        }
