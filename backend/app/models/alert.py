"""
Alert Rule and Triggered Alert ORM Models
"""
from datetime import datetime
from typing import Optional, Dict, Any, List, TYPE_CHECKING
from uuid import UUID, uuid4
from sqlalchemy import (
    String, Float, Integer, Boolean, DateTime, ForeignKey, Index, JSON, func
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, GUID

if TYPE_CHECKING:
    from app.models.service import Service
    from app.models.incident import Incident


class AlertRule(Base, TimestampMixin):
    """
    Configured rule evaluating threshold logic on incoming metric snapshots.
    """
    __tablename__ = "alert_rules"

    id: Mapped[UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid4
    )
    service_id: Mapped[Optional[UUID]] = mapped_column(
        GUID,
        ForeignKey("services.id", ondelete="RESTRICT"),
        nullable=True
    )
    name: Mapped[str] = mapped_column(
        String(120),
        nullable=False
    )
    metric_name: Mapped[str] = mapped_column(
        String(80),
        nullable=False
    )
    operator: Mapped[str] = mapped_column(
        String(8),
        nullable=False
    )
    threshold: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )
    window_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=60
    )
    severity: Mapped[str] = mapped_column(
        String(16),
        nullable=False
    )
    create_incident: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )
    cooldown_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=300
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )

    # Relationships
    service: Mapped[Optional["Service"]] = relationship(
        "Service",
        back_populates="alert_rules"
    )
    alerts: Mapped[List["Alert"]] = relationship(
        "Alert",
        back_populates="rule",
        cascade="all, delete-orphan"
    )


class Alert(Base):
    """
    Triggered alert instance resulting from a rule match.
    """
    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_service_status_triggered", "service_id", "status", "triggered_at"),
        Index("ix_alerts_rule_service_status", "rule_id", "service_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid4
    )
    rule_id: Mapped[UUID] = mapped_column(
        GUID,
        ForeignKey("alert_rules.id", ondelete="RESTRICT"),
        nullable=False
    )
    service_id: Mapped[UUID] = mapped_column(
        GUID,
        ForeignKey("services.id", ondelete="RESTRICT"),
        nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False
    )
    severity: Mapped[str] = mapped_column(
        String(16),
        nullable=False
    )
    current_value: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True
    )
    threshold_value: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True
    )
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    evidence: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
        default=dict
    )

    # Relationships
    rule: Mapped["AlertRule"] = relationship(
        "AlertRule",
        back_populates="alerts"
    )
    service: Mapped["Service"] = relationship(
        "Service",
        back_populates="alerts"
    )
    incidents: Mapped[List["Incident"]] = relationship(
        "Incident",
        back_populates="originating_alert"
    )
