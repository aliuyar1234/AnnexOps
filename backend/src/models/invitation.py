"""Invitation model."""
from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.models.base import BaseModel
from src.models.enums import UserRole


class Invitation(BaseModel):
    """Invitation entity for pending user invitations.

    Invitations are created by admins to invite new users to join their
    organization. Each invitation has a unique token, expires after 7 days,
    and can only be used once.
    """

    __tablename__ = "invitations"

    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False
    )
    email = Column(
        String(255),
        nullable=False
    )
    role = Column(
        SQLEnum(UserRole, name="user_role", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False
    )
    token_hash = Column(
        String(255),
        nullable=False,
        unique=True,
        index=True
    )
    invited_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True
    )
    accepted_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

    # Relationships
    organization = relationship(
        "Organization",
        back_populates="invitations"
    )
    inviter = relationship(
        "User",
        back_populates="invitations_sent",
        foreign_keys=[invited_by]
    )

    def __repr__(self) -> str:
        return f"<Invitation(id={self.id}, email={self.email}, org_id={self.org_id})>"
