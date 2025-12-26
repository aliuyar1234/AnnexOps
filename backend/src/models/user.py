"""User model."""
from sqlalchemy import Column, String, Boolean, Integer, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from src.models.base import BaseModel
from src.models.enums import UserRole


class User(BaseModel):
    """User entity representing an individual with access to one organization.

    Users belong to a single organization and have a role that determines
    their permissions. Account lockout is handled via failed_login_attempts
    and locked_until fields.
    """

    __tablename__ = "users"

    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    email = Column(
        String(255),
        nullable=False
    )
    password_hash = Column(
        String(255),
        nullable=False
    )
    role = Column(
        SQLEnum(UserRole, name="user_role", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=UserRole.VIEWER
    )
    is_active = Column(
        Boolean,
        nullable=False,
        default=True
    )
    failed_login_attempts = Column(
        Integer,
        nullable=False,
        default=0
    )
    locked_until = Column(
        DateTime(timezone=True),
        nullable=True
    )
    last_login_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

    # Relationships
    organization = relationship(
        "Organization",
        back_populates="users"
    )
    invitations_sent = relationship(
        "Invitation",
        back_populates="inviter",
        foreign_keys="Invitation.invited_by"
    )
    audit_events = relationship(
        "AuditEvent",
        back_populates="user"
    )

    __table_args__ = (
        # Unique constraint: email unique within organization
        # Index for efficient lookups
        {"schema": None},
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"
