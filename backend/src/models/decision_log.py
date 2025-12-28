"""Decision log model for storing ingested decision events."""

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from src.models.base import BaseModel


class DecisionLog(BaseModel):
    """Stored decision event (immutable record)."""

    __tablename__ = "decision_logs"

    version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("system_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_id = Column(
        String(255),
        nullable=False,
    )
    event_time = Column(
        DateTime(timezone=True),
        nullable=False,
    )
    event_json = Column(
        JSONB,
        nullable=False,
    )
    ingested_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    system_version = relationship(
        "SystemVersion",
        backref="decision_logs",
    )

    __table_args__ = (
        Index("idx_logs_version_time", "version_id", "event_time"),
        Index("idx_logs_event_id", "version_id", "event_id", unique=True),
        Index("idx_logs_ingested", "ingested_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<DecisionLog(id={self.id}, version_id={self.version_id}, event_id={self.event_id})>"
        )
