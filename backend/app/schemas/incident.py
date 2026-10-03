"""
Incident and Incident Timeline Event Schemas for PulseOps
Pydantic data models for incident creation, updates, responses, and timeline history.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


class IncidentBase(BaseModel):
    """Base incident properties."""
    title: str = Field(..., min_length=1, max_length=180, description="Incident human-readable summary")
    description: Optional[str] = Field(None, description="Detailed problem description")
    severity: str = Field(..., pattern="^(critical|warning|info)$", description="Severity level: critical, warning, info")


class IncidentCreate(IncidentBase):
    """Payload for manual or programmatic incident creation."""
    service_id: UUID = Field(..., description="Target affected service UUID")
    alert_id: Optional[UUID] = Field(None, description="Originating triggered alert UUID if applicable")


class IncidentUpdate(BaseModel):
    """Payload for updating incident lifecycle status, assignee, or resolution note."""
    status: Optional[str] = Field(None, pattern="^(open|investigating|resolved)$", description="Lifecycle status transition")
    assignee_user_id: Optional[UUID] = Field(None, description="Assigned responder user UUID")
    resolution_note: Optional[str] = Field(None, description="Resolution analysis or remediation note")


class IncidentResponse(IncidentBase):
    """Complete incident response DTO."""
    id: UUID
    service_id: UUID
    alert_id: Optional[UUID] = None
    status: str
    assignee_user_id: Optional[UUID] = None
    detected_at: datetime
    opened_at: datetime
    investigating_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    resolution_note: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    # Preloaded display relations
    service_name: Optional[str] = None
    assignee_email: Optional[str] = None
    assignee_name: Optional[str] = None
    originating_alert_rule_name: Optional[str] = None
    evidence: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class IncidentEventCreate(BaseModel):
    """Payload for appending a timeline note or investigation entry."""
    event_type: str = Field(default="NOTE_ADDED", max_length=40, description="Event classification")
    message: str = Field(..., min_length=1, description="Timeline entry message")
    metadata_json: Optional[Dict[str, Any]] = Field(default_factory=dict, alias="metadata", description="Safe context metadata")

    model_config = ConfigDict(populate_by_name=True)


class IncidentEventResponse(BaseModel):
    """Append-only incident timeline event DTO."""
    id: int
    incident_id: UUID
    event_type: str
    actor_user_id: Optional[UUID] = None
    actor_name: Optional[str] = None
    message: str
    metadata_json: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
