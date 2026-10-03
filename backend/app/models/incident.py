"""
Incident, Incident Timeline Event, and AI Analysis ORM Models
"""
from datetime import datetime
from typing import Optional, Dict, List, Any, TYPE_CHECKING
from uuid import UUID, uuid4
from sqlalchemy import (
    BigInteger, Integer, String, Text, DateTime, ForeignKey, Index, JSON, func
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, GUID

if TYPE_CHECKING:
    from app.models.service import Service
    from app.models.alert import Alert
    from app.models.user import User


class Incident(Base, TimestampMixin):
    """Trackable operational problem representing an active or historical incident."""
    __tablename__ = "incidents"
    __table_args__ = (
        Index("ix_incidents_service_status_opened", "service_id", "status", "opened_at"),
    )

    id: Mapped[UUID] = mapped_column(GUID, primary_key=True, default=uuid4)
    service_id: Mapped[UUID] = mapped_column(
        GUID, ForeignKey("services.id", ondelete="RESTRICT"), nullable=False
    )
    alert_id: Mapped[Optional[UUID]] = mapped_column(
        GUID, ForeignKey("alerts.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    assignee_user_id: Mapped[Optional[UUID]] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    investigating_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    service: Mapped["Service"] = relationship("Service", back_populates="incidents")
    originating_alert: Mapped[Optional["Alert"]] = relationship("Alert", back_populates="incidents")
    assignee: Mapped[Optional["User"]] = relationship("User", back_populates="assigned_incidents", foreign_keys=[assignee_user_id])
    timeline_events: Mapped[List["IncidentEvent"]] = relationship("IncidentEvent", back_populates="incident", cascade="all, delete-orphan")
    ai_analyses: Mapped[List["AIAnalysis"]] = relationship("AIAnalysis", back_populates="incident", cascade="all, delete-orphan")


class IncidentEvent(Base):
    """Append-only timeline entry for an incident investigation."""
    __tablename__ = "incident_events"
    __table_args__ = (
        Index("ix_incident_events_incident_created", "incident_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True
    )
    incident_id: Mapped[UUID] = mapped_column(
        GUID, ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_user_id: Mapped[Optional[UUID]] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        "metadata", JSON().with_variant(JSONB(), "postgresql"), nullable=True, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    incident: Mapped["Incident"] = relationship("Incident", back_populates="timeline_events")
    actor: Mapped[Optional["User"]] = relationship("User", back_populates="incident_events", foreign_keys=[actor_user_id])


class AIAnalysis(Base):
    """Generated advisory analysis snapshot of incident evidence."""
    __tablename__ = "ai_analyses"
    __table_args__ = (
        Index("ix_ai_analyses_incident_created", "incident_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(GUID, primary_key=True, default=uuid4)
    incident_id: Mapped[UUID] = mapped_column(
        GUID, ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False
    )
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1")
    evidence_snapshot: Mapped[Dict[str, Any]] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    possible_factors: Mapped[Optional[List[str]]] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=True, default=list)
    limitations_note: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    incident: Mapped["Incident"] = relationship("Incident", back_populates="ai_analyses")

