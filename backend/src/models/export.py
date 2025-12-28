"""Export model for Annex IV documentation exports."""
from sqlalchemy import BigInteger, Boolean, Column, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.models.base import BaseModel


class Export(BaseModel):
    """Export entity for tracking Annex IV documentation exports.

    Exports can be full snapshots or diffs between versions.
    """

    __tablename__ = "exports"

    version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("system_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    export_type = Column(
        String(20),
        nullable=False,
        server_default="full",
    )
    snapshot_hash = Column(
        String(64),
        nullable=False,
    )
    storage_uri = Column(
        String(500),
        nullable=False,
    )
    file_size = Column(
        BigInteger,
        nullable=False,
    )
    include_diff = Column(
        Boolean,
        nullable=False,
        server_default="false",
    )
    compare_version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("system_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    completeness_score = Column(
        Numeric(5, 2),
        nullable=False,
    )
    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
    )

    # Relationships
    system_version = relationship(
        "SystemVersion",
        foreign_keys=[version_id],
        backref="exports",
    )
    compare_version = relationship(
        "SystemVersion",
        foreign_keys=[compare_version_id],
    )
    creator = relationship(
        "User",
        foreign_keys=[created_by],
    )

    def __repr__(self) -> str:
        return f"<Export(id={self.id}, type={self.export_type}, version_id={self.version_id})>"
