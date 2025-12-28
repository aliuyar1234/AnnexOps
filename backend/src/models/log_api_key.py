"""Log API key model for decision event ingestion."""

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.models.base import BaseModel


class LogApiKey(BaseModel):
    """API key entity for authenticating decision log ingestion."""

    __tablename__ = "log_api_keys"

    version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("system_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key_hash = Column(
        String(64),
        nullable=False,
        unique=True,
    )
    name = Column(
        String(100),
        nullable=False,
    )
    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
    )
    revoked_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_used_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    system_version = relationship(
        "SystemVersion",
        backref="log_api_keys",
    )
    creator = relationship(
        "User",
        foreign_keys=[created_by],
    )

    def __repr__(self) -> str:
        return (
            f"<LogApiKey(id={self.id}, version_id={self.version_id}, revoked_at={self.revoked_at})>"
        )
