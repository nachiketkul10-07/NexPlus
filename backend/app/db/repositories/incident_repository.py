"""
Incident & Incident Event Repository Implementation for PostgreSQL
Manages async persistence, timeline event appending, deduplication, and querying of incidents.
"""
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy import select, and_, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.incident import Incident, IncidentEvent
from app.models.alert import Alert
from app.models.service import Service
from app.models.user import User
from app.schemas.incident import IncidentCreate, IncidentUpdate, IncidentEventCreate


class PostgresIncidentRepository:
    """Async repository for Incident and IncidentEvent ORM models."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_incident(
        self,
        service_id: UUID,
        title: str,
        severity: str,
        alert_id: Optional[UUID] = None,
        description: Optional[str] = None,
        status: str = "open",
        detected_at: Optional[datetime] = None,
    ) -> Incident:
        """Creates and persists a new Incident record."""
        now = datetime.now(timezone.utc)
        incident = Incident(
            service_id=service_id,
            alert_id=alert_id,
            title=title,
            description=description,
            severity=severity,
            status=status,
            detected_at=detected_at or now,
            opened_at=now,
        )
        self.session.add(incident)
        await self.session.flush()
        await self.session.refresh(incident)
        return incident

    async def get_active_incident_for_alert(
        self,
        service_id: UUID,
        alert_id: Optional[UUID] = None,
        rule_id: Optional[UUID] = None
    ) -> Optional[Incident]:
        """
        Checks if an active (non-resolved) incident already exists for an alert condition.
        Prevents duplicate active incidents for the same underlying active condition.
        """
        conditions = [
            Incident.service_id == service_id,
            Incident.status.in_(["open", "investigating"])
        ]

        if alert_id is not None:
            conditions.append(Incident.alert_id == alert_id)
        elif rule_id is not None:
            stmt = (
                select(Incident)
                .join(Alert, Incident.alert_id == Alert.id)
                .where(
                    and_(
                        Incident.service_id == service_id,
                        Alert.rule_id == rule_id,
                        Incident.status.in_(["open", "investigating"])
                    )
                )
                .order_by(desc(Incident.opened_at))
            )
            res = await self.session.execute(stmt)
            return res.scalars().first()
        else:
            return None

        stmt = select(Incident).where(and_(*conditions)).order_by(desc(Incident.opened_at))
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def get_incident_by_id(self, incident_id: UUID) -> Optional[Incident]:
        """Fetches an Incident by primary key ID with eager loaded relationships."""
        stmt = (
            select(Incident)
            .options(
                selectinload(Incident.service),
                selectinload(Incident.originating_alert).selectinload(Alert.rule),
                selectinload(Incident.assignee),
                selectinload(Incident.timeline_events).selectinload(IncidentEvent.actor)
            )
            .where(Incident.id == incident_id)
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def list_incidents(
        self,
        service_id: Optional[UUID] = None,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        assignee_user_id: Optional[UUID] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Incident]:
        """Queries recent incidents with optional filters and eager preloaded relations."""
        stmt = (
            select(Incident)
            .options(
                selectinload(Incident.service),
                selectinload(Incident.originating_alert).selectinload(Alert.rule),
                selectinload(Incident.assignee)
            )
        )
        conditions = []

        if service_id:
            conditions.append(Incident.service_id == service_id)
        if status:
            conditions.append(Incident.status == status.lower())
        if severity:
            conditions.append(Incident.severity == severity.lower())
        if assignee_user_id:
            conditions.append(Incident.assignee_user_id == assignee_user_id)

        if conditions:
            stmt = stmt.where(and_(*conditions))

        stmt = stmt.order_by(desc(Incident.opened_at)).offset(offset).limit(min(limit, 100))
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def update_incident(self, incident: Incident, updates: Dict[str, Any]) -> Incident:
        """Updates fields on an existing Incident instance."""
        for field, value in updates.items():
            if hasattr(incident, field):
                setattr(incident, field, value)

        await self.session.flush()
        await self.session.refresh(incident)
        return incident

    async def add_timeline_event(
        self,
        incident_id: UUID,
        event_type: str,
        message: str,
        actor_user_id: Optional[UUID] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> IncidentEvent:
        """Appends an append-only timeline event record to an incident."""
        event = IncidentEvent(
            incident_id=incident_id,
            event_type=event_type,
            message=message,
            actor_user_id=actor_user_id,
            metadata_json=metadata or {}
        )
        self.session.add(event)
        await self.session.flush()
        await self.session.refresh(event)
        return event

    async def get_timeline_events(self, incident_id: UUID) -> List[IncidentEvent]:
        """Retrieves timeline event records for an incident in chronological order."""
        stmt = (
            select(IncidentEvent)
            .options(selectinload(IncidentEvent.actor))
            .where(IncidentEvent.incident_id == incident_id)
            .order_by(IncidentEvent.created_at.asc())
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())
