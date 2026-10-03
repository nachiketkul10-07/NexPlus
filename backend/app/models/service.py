"""
Service ORM Model representing Monitored Applications
"""
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from uuid import UUID, uuid4
from sqlalchemy import String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, GUID

if TYPE_CHECKING:
    from app.models.telemetry import TelemetryEvent, Metric, LogEntry
    from app.models.alert import AlertRule, Alert
    from app.models.incident import Incident


class Service(Base, TimestampMixin):
    """
    Service entity representing a monitored application or service (e.g. demo-app).
    """
    __tablename__ = "services"

    id: Mapped[UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid4
    )
    identifier: Mapped[str] = mapped_column(
        String(80),
        unique=True,
        index=True,
        nullable=False
    )
    name: Mapped[str] = mapped_column(
        String(120),
        nullable=False
    )
    environment: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="development"
    )
    base_url: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    repository_url: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    health_path: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        default="/api/health"
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="unknown"
    )
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    ingest_key_hash: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )

    # Relationships
    telemetry_events: Mapped[List["TelemetryEvent"]] = relationship(
        "TelemetryEvent",
        back_populates="service",
        cascade="all, delete-orphan"
    )
    metrics: Mapped[List["Metric"]] = relationship(
        "Metric",
        back_populates="service",
        cascade="all, delete-orphan"
    )
    logs: Mapped[List["LogEntry"]] = relationship(
        "LogEntry",
        back_populates="service",
        cascade="all, delete-orphan"
    )
    alert_rules: Mapped[List["AlertRule"]] = relationship(
        "AlertRule",
        back_populates="service"
    )
    alerts: Mapped[List["Alert"]] = relationship(
        "Alert",
        back_populates="service"
    )
    incidents: Mapped[List["Incident"]] = relationship(
        "Incident",
        back_populates="service"
    )

    def __repr__(self) -> str:
        return f"<Service(id={self.id}, identifier={self.identifier!r}, status={self.status!r})>"
