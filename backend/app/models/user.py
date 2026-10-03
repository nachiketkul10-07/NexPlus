"""
User ORM Model for Authentication and Authorization
"""
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from uuid import UUID, uuid4
from sqlalchemy import String, Text, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, GUID

if TYPE_CHECKING:
    from app.models.incident import Incident, IncidentEvent


class User(Base, TimestampMixin):
    """
    User entity representing a human operator or admin who can access PulseOps.
    """
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid4
    )
    email: Mapped[str] = mapped_column(
        String(320),
        unique=True,
        index=True,
        nullable=False
    )
    full_name: Mapped[str] = mapped_column(
        String(120),
        nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(
        "password_hash",
        Text,
        nullable=False
    )
    role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="user"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # Relationships
    assigned_incidents: Mapped[List["Incident"]] = relationship(
        "Incident",
        back_populates="assignee",
        foreign_keys="Incident.assignee_user_id"
    )
    incident_events: Mapped[List["IncidentEvent"]] = relationship(
        "IncidentEvent",
        back_populates="actor",
        foreign_keys="IncidentEvent.actor_user_id"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email!r}, role={self.role!r})>"
