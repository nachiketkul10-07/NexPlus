"""
Telemetry, Metric, and Log Entry ORM Models
"""
from datetime import datetime
from typing import Optional, Dict, Any, TYPE_CHECKING
from uuid import UUID
from sqlalchemy import (
    BigInteger, SmallInteger, Integer, Float, String, Text, DateTime,
    ForeignKey, Index, JSON, func
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GUID

if TYPE_CHECKING:
    from app.models.service import Service


class TelemetryEvent(Base):
    """
    Telemetry event representing an observed request/outcome from an instrumented service.
    """
    __tablename__ = "telemetry_events"
    __table_args__ = (
        Index("ix_telemetry_events_service_occurred", "service_id", "occurred_at"),
        Index("ix_telemetry_events_service_outcome_occurred", "service_id", "outcome", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True
    )
    service_id: Mapped[UUID] = mapped_column(
        GUID,
        ForeignKey("services.id", ondelete="RESTRICT"),
        nullable=False
    )
    request_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )
    method: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True
    )
    endpoint: Mapped[Optional[str]] = mapped_column(
        String(300),
        nullable=True
    )
    status_code: Mapped[Optional[int]] = mapped_column(
        SmallInteger,
        nullable=True
    )
    duration_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )
    outcome: Mapped[str] = mapped_column(
        String(24),
        nullable=False
    )
    error_type: Mapped[Optional[str]] = mapped_column(
        String(160),
        nullable=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        "metadata",
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
        default=dict
    )

    # Relationships
    service: Mapped["Service"] = relationship(
        "Service",
        back_populates="telemetry_events"
    )


class Metric(Base):
    """
    Metric snapshot aggregate value used by charts and alert evaluation rules.
    """
    __tablename__ = "metrics"
    __table_args__ = (
        Index("ix_metrics_service_name_recorded", "service_id", "metric_name", "recorded_at"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True
    )
    service_id: Mapped[UUID] = mapped_column(
        GUID,
        ForeignKey("services.id", ondelete="RESTRICT"),
        nullable=False
    )
    metric_name: Mapped[str] = mapped_column(
        String(80),
        nullable=False
    )
    value: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )
    window_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=60
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    service: Mapped["Service"] = relationship(
        "Service",
        back_populates="metrics"
    )


class LogEntry(Base):
    """
    Application log line/event recorded from a service.
    """
    __tablename__ = "logs"
    __table_args__ = (
        Index("ix_logs_service_occurred", "service_id", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True
    )
    service_id: Mapped[UUID] = mapped_column(
        GUID,
        ForeignKey("services.id", ondelete="RESTRICT"),
        nullable=False
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )
    level: Mapped[str] = mapped_column(
        String(16),
        nullable=False
    )
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    request_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True
    )
    trace_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True
    )
    stack_trace: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        "metadata",
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
        default=dict
    )

    # Relationships
    service: Mapped["Service"] = relationship(
        "Service",
        back_populates="logs"
    )
