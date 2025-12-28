"""AuditEvent model."""

from sqlalchemy import Column, ForeignKey, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import relationship

from src.models.base import BaseModel
from src.models.enums import AuditAction


class AuditEvent(BaseModel):
    """Immutable audit trail for administrative actions.

    Audit events track all important actions in the system for compliance
    and security purposes. Records are append-only and cannot be modified
    or deleted.
    """

    __tablename__ = "audit_events"

    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action = Column(
        SQLEnum(
            AuditAction,
            name="audit_action",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(UUID(as_uuid=True), nullable=False)
    diff_json = Column(JSONB, nullable=True)
    ip_address = Column(INET, nullable=True)

    # Relationships
    organization = relationship("Organization", back_populates="audit_events")
    user = relationship("User", back_populates="audit_events")

    __table_args__ = (
        # Index for efficient entity lookups
        {"schema": None},
    )

    def __repr__(self) -> str:
        return f"<AuditEvent(id={self.id}, action={self.action}, entity_type={self.entity_type})>"
