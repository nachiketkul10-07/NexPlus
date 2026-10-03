"""
Incident Management Service for PulseOps
Encapsulates incident escalation from alerts, state machine transitions, deduplication, assignment, timeline logging, and audit tracking.
"""
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.incident import Incident, IncidentEvent
from app.models.alert import AlertRule, Alert
from app.models.service import Service
from app.db.repositories.incident_repository import PostgresIncidentRepository
from app.core.audit import log_audit_event


class IncidentService:
    """Service layer governing incident lifecycle, state machine transitions, and alert escalation."""

    ALLOWED_STATUSES = {"open", "investigating", "resolved"}

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = PostgresIncidentRepository(session)

    async def escalate_alert_to_incident(
        self,
        alert: Alert,
        rule: AlertRule,
        service: Service
    ) -> Optional[Incident]:
        """
        Automated escalation flow: turns a triggered active alert into an operational incident.
        Strictly enforces single active incident deduplication per underlying condition.
        """
        # 1. Check for existing active incident for this condition
        existing = await self.repo.get_active_incident_for_alert(
            service_id=service.id,
            alert_id=alert.id,
            rule_id=rule.id
        )
        if existing:
            # Active incident already exists: do not create duplicate
            return existing

        # 2. Create new incident record
        title = f"{rule.name} on {service.name}"
        description = (
            f"Alert rule '{rule.name}' triggered for metric '{rule.metric_name}'. "
            f"Observed value: {alert.current_value} (Threshold: {rule.operator} {rule.threshold})."
        )

        incident = await self.repo.create_incident(
            service_id=service.id,
            alert_id=alert.id,
            title=title,
            description=description,
            severity=alert.severity,
            status="open",
            detected_at=alert.triggered_at,
        )

        # 3. Create initial timeline event
        await self.repo.add_timeline_event(
            incident_id=incident.id,
            event_type="INCIDENT_CREATED",
            message=f"Incident created automatically from alert rule '{rule.name}'",
            metadata=alert.evidence or {}
        )

        log_audit_event(
            "INCIDENT_CREATED",
            user_id="system",
            email="system@pulseops.io",
            details={
                "incident_id": str(incident.id),
                "service_id": str(service.id),
                "alert_id": str(alert.id),
                "severity": incident.severity
            },
            success=True
        )

        return incident

    async def transition_incident_status(
        self,
        incident: Incident,
        target_status: str,
        actor_user_id: Optional[UUID] = None,
        actor_email: Optional[str] = None,
        resolution_note: Optional[str] = None
    ) -> Incident:
        """
        Executes incident state machine transition.
        Enforces allowed direct paths: OPEN -> INVESTIGATING, OPEN -> RESOLVED, INVESTIGATING -> RESOLVED.
        Rejects invalid transitions (e.g. RESOLVED -> OPEN or RESOLVED -> INVESTIGATING).
        """
        target_status = target_status.lower()
        if target_status not in self.ALLOWED_STATUSES:
            raise ValueError(f"Invalid incident status '{target_status}'. Must be one of {self.ALLOWED_STATUSES}.")

        current_status = incident.status.lower()

        if current_status == target_status:
            return incident

        if current_status == "resolved":
            raise ValueError("Resolved incidents cannot be reopened or state-transitioned.")

        if current_status == "investigating" and target_status == "open":
            raise ValueError("Cannot transition incident from investigating back to open.")

        # Valid transitions
        now = datetime.now(timezone.utc)
        updates: Dict[str, Any] = {"status": target_status}

        if target_status == "investigating":
            if not incident.investigating_at:
                updates["investigating_at"] = now
            event_type = "STATUS_CHANGED"
            event_msg = "Incident status updated to INVESTIGATING"

        elif target_status == "resolved":
            updates["resolved_at"] = now
            if resolution_note:
                updates["resolution_note"] = resolution_note
            event_type = "INCIDENT_RESOLVED"
            event_msg = f"Incident resolved. {resolution_note or ''}".strip()

        updated_incident = await self.repo.update_incident(incident, updates)

        # Append timeline event
        await self.repo.add_timeline_event(
            incident_id=incident.id,
            event_type=event_type,
            message=event_msg,
            actor_user_id=actor_user_id,
            metadata={"previous_status": current_status, "new_status": target_status}
        )

        log_audit_event(
            "INCIDENT_STATUS_CHANGED",
            user_id=str(actor_user_id) if actor_user_id else "system",
            email=actor_email or "user@pulseops.io",
            details={
                "incident_id": str(incident.id),
                "from_status": current_status,
                "to_status": target_status,
            },
            success=True
        )

        return updated_incident

    async def assign_incident(
        self,
        incident: Incident,
        assignee_user_id: Optional[UUID],
        actor_user_id: Optional[UUID] = None,
        actor_email: Optional[str] = None
    ) -> Incident:
        """Assigns or unassigns an incident responder."""
        updates = {"assignee_user_id": assignee_user_id}
        updated_incident = await self.repo.update_incident(incident, updates)

        event_type = "ASSIGNED" if assignee_user_id else "UNASSIGNED"
        msg = f"Incident assigned to user {assignee_user_id}" if assignee_user_id else "Incident unassigned"

        await self.repo.add_timeline_event(
            incident_id=incident.id,
            event_type=event_type,
            message=msg,
            actor_user_id=actor_user_id,
            metadata={"assignee_user_id": str(assignee_user_id) if assignee_user_id else None}
        )

        log_audit_event(
            "INCIDENT_ASSIGNED",
            user_id=str(actor_user_id) if actor_user_id else "system",
            email=actor_email or "user@pulseops.io",
            details={
                "incident_id": str(incident.id),
                "assignee_user_id": str(assignee_user_id) if assignee_user_id else None
            },
            success=True
        )

        return updated_incident

    async def add_incident_note(
        self,
        incident: Incident,
        message: str,
        actor_user_id: Optional[UUID] = None,
        actor_email: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> IncidentEvent:
        """Appends a user investigation note to the incident timeline."""
        event = await self.repo.add_timeline_event(
            incident_id=incident.id,
            event_type="NOTE_ADDED",
            message=message,
            actor_user_id=actor_user_id,
            metadata=metadata or {}
        )

        log_audit_event(
            "INCIDENT_NOTE_ADDED",
            user_id=str(actor_user_id) if actor_user_id else "system",
            email=actor_email or "user@pulseops.io",
            details={
                "incident_id": str(incident.id),
                "event_id": event.id
            },
            success=True
        )

        return event
