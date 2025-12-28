"""Pydantic schemas for evidence endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from src.models.enums import Classification, EvidenceType


# Type-specific metadata schemas
class UrlMetadata(BaseModel):
    """Metadata schema for URL type evidence."""

    url: HttpUrl = Field(..., description="URL to external resource")
    accessed_at: datetime | None = Field(None, description="Timestamp when URL was accessed")
    # Note: 'title' field removed as it's redundant with evidence.title


class GitMetadata(BaseModel):
    """Metadata schema for Git type evidence."""

    repo_url: HttpUrl = Field(..., description="Git repository URL")
    commit_hash: str = Field(
        ..., min_length=40, max_length=40, description="Git commit hash (40 char hex)"
    )
    file_path: str | None = Field(None, description="Path to file in repository")
    branch: str | None = Field(None, description="Git branch name")

    @field_validator("commit_hash")
    @classmethod
    def validate_commit_hash(cls, v: str) -> str:
        """Validate commit hash is valid hex string."""
        if not all(c in "0123456789abcdefABCDEF" for c in v):
            raise ValueError("commit_hash must be a valid hexadecimal string")
        return v.lower()


class TicketMetadata(BaseModel):
    """Metadata schema for Ticket type evidence."""

    ticket_id: str = Field(..., min_length=1, description="Ticket identifier")
    ticket_system: str = Field(
        ..., min_length=1, description="Ticket system name (e.g., jira, github)"
    )
    ticket_url: HttpUrl | None = Field(None, description="URL to ticket")


class NoteMetadata(BaseModel):
    """Metadata schema for Note type evidence."""

    content: str = Field(..., min_length=1, description="Markdown content of the note")


class UploadMetadata(BaseModel):
    """Metadata schema for Upload type evidence."""

    storage_uri: str = Field(..., description="Storage location URI")
    checksum_sha256: str = Field(..., min_length=64, max_length=64, description="SHA-256 checksum")
    file_size: int = Field(..., gt=0, description="File size in bytes")
    mime_type: str = Field(..., min_length=1, description="MIME type of file")
    original_filename: str = Field(
        ..., min_length=1, max_length=255, description="Original filename"
    )


class CreateEvidenceRequest(BaseModel):
    """Request schema for creating an evidence item."""

    type: EvidenceType
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    tags: list[str] = Field(default_factory=list, max_length=20)
    classification: Classification = Classification.INTERNAL
    type_metadata: dict = Field(..., description="Type-specific metadata")

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        """Validate tag constraints."""
        if len(v) > 20:
            raise ValueError("Maximum 20 tags allowed")
        for tag in v:
            if len(tag) < 1 or len(tag) > 50:
                raise ValueError("Each tag must be 1-50 characters")
        return v

    @field_validator("type_metadata")
    @classmethod
    def validate_type_metadata(cls, v: dict, info) -> dict:
        """Validate type_metadata structure based on evidence type."""
        from pydantic import ValidationError

        # Get the type field from values
        evidence_type = info.data.get("type")

        # Validate using appropriate schema based on type
        try:
            if evidence_type == EvidenceType.UPLOAD:
                UploadMetadata(**v)
            elif evidence_type == EvidenceType.URL:
                UrlMetadata(**v)
            elif evidence_type == EvidenceType.GIT:
                GitMetadata(**v)
            elif evidence_type == EvidenceType.TICKET:
                TicketMetadata(**v)
            elif evidence_type == EvidenceType.NOTE:
                NoteMetadata(**v)
            else:
                raise ValueError(f"Unknown evidence type: {evidence_type}")
        except ValidationError as e:
            # Convert Pydantic validation error to readable message
            error_msgs = []
            for error in e.errors():
                field = " -> ".join(str(loc) for loc in error["loc"])
                msg = error["msg"]
                error_msgs.append(f"{field}: {msg}")
            raise ValueError(
                f"{evidence_type.value} metadata validation failed: {'; '.join(error_msgs)}"
            ) from None

        return v


class EvidenceResponse(BaseModel):
    """Response schema for evidence item."""

    id: UUID
    org_id: UUID
    type: EvidenceType
    title: str
    description: str | None = None
    tags: list[str]
    classification: Classification
    type_metadata: dict
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    usage_count: int | None = Field(
        None,
        description="Number of mappings referencing this evidence (only populated when listing)",
    )
    duplicate_of: UUID | None = Field(
        None, description="ID of evidence with same checksum (duplicate warning)"
    )

    model_config = ConfigDict(from_attributes=True)


class UploadUrlRequest(BaseModel):
    """Request schema for presigned upload URL generation."""

    filename: str = Field(..., min_length=1, max_length=255)
    mime_type: str = Field(..., min_length=1)


class UploadUrlResponse(BaseModel):
    """Response schema for presigned upload URL."""

    upload_url: str
    storage_uri: str
    expires_in: int = 3600


class EvidenceListResponse(BaseModel):
    """Response schema for evidence list with pagination metadata."""

    items: list[EvidenceResponse]
    total: int = Field(
        ..., description="Total count of items matching filters (without pagination)"
    )
    limit: int = Field(..., description="Maximum number of items per page")
    offset: int = Field(..., description="Number of items skipped")


class VersionSummary(BaseModel):
    """Summary information about a system version."""

    id: UUID
    label: str
    system_id: UUID
    system_name: str

    model_config = ConfigDict(from_attributes=True)


class EvidenceDetailResponse(EvidenceResponse):
    """Response schema for evidence item detail with additional metadata.

    Extends EvidenceResponse with usage count and list of mapped versions.
    """

    usage_count: int = Field(..., description="Number of mappings referencing this evidence")
    mapped_versions: list[VersionSummary] = Field(
        default_factory=list, description="System versions this evidence is mapped to"
    )

    model_config = ConfigDict(from_attributes=True)


class UpdateEvidenceRequest(BaseModel):
    """Request schema for updating an evidence item.

    All fields are optional. Only provided fields will be updated.
    """

    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    tags: list[str] | None = Field(None, max_length=20)
    classification: Classification | None = None
    type_metadata: dict | None = None

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str] | None) -> list[str] | None:
        """Validate tag constraints."""
        if v is None:
            return v
        if len(v) > 20:
            raise ValueError("Maximum 20 tags allowed")
        for tag in v:
            if len(tag) < 1 or len(tag) > 50:
                raise ValueError("Each tag must be 1-50 characters")
        return v

    @field_validator("type_metadata")
    @classmethod
    def validate_type_metadata(cls, v: dict | None, info) -> dict | None:
        """Validate type_metadata structure if provided.

        Note: This validator cannot check against evidence type since
        type is not updatable. The service layer must validate against
        the existing evidence type.
        """
        if v is None:
            return v
        # Type validation will be done in service layer
        # where we have access to the existing evidence type
        return v
