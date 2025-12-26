"""Organization model."""
from sqlalchemy import Column, String, CheckConstraint
from sqlalchemy.orm import relationship
from src.models.base import BaseModel


class Organization(BaseModel):
    """Organization entity representing a company or team.

    An organization is the top-level tenant entity that owns users,
    systems, and other resources.
    """

    __tablename__ = "organizations"

    name = Column(
        String(255),
        nullable=False,
        unique=True,
        index=True
    )

    # Relationships
    users = relationship(
        "User",
        back_populates="organization",
        cascade="all, delete-orphan"
    )
    invitations = relationship(
        "Invitation",
        back_populates="organization",
        cascade="all, delete-orphan"
    )
    audit_events = relationship(
        "AuditEvent",
        back_populates="organization",
        cascade="all, delete-orphan"
    )
    evidence_items = relationship(
        "EvidenceItem",
        back_populates="organization",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "LENGTH(name) > 0",
            name="organization_name_not_empty"
        ),
    )

    def __repr__(self) -> str:
        return f"<Organization(id={self.id}, name={self.name})>"
