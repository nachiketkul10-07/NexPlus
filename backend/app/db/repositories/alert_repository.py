"""
Alert & Alert Rule Repository Implementation for PostgreSQL
Manages async persistence and querying of alert rules and triggered alert events.
"""
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.alert import AlertRule, Alert
from app.models.service import Service
from app.schemas.alert import AlertRuleCreate, AlertRuleUpdate


class PostgresAlertRepository:
    """Async repository for AlertRule and Alert ORM models."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ------------------------------------------------------------------
    # Alert Rules
    # ------------------------------------------------------------------
    async def create_rule(self, rule_in: AlertRuleCreate) -> AlertRule:
        """Creates and persists a new alert evaluation rule."""
        rule = AlertRule(
            service_id=rule_in.service_id,
            name=rule_in.name,
            metric_name=rule_in.metric_name,
            operator=rule_in.operator,
            threshold=rule_in.threshold,
            window_seconds=rule_in.window_seconds,
            severity=rule_in.severity,
            create_incident=rule_in.create_incident,
            cooldown_seconds=rule_in.cooldown_seconds,
            enabled=rule_in.enabled,
        )
        self.session.add(rule)
        await self.session.flush()
        await self.session.refresh(rule)
        return rule

    async def get_rule_by_id(self, rule_id: UUID) -> Optional[AlertRule]:
        """Fetches an AlertRule by primary key ID."""
        stmt = select(AlertRule).where(AlertRule.id == rule_id)
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def list_rules(
        self,
        service_id: Optional[UUID] = None,
        enabled_only: bool = False
    ) -> List[AlertRule]:
        """Lists alert rules with optional service and enabled state filters."""
        stmt = select(AlertRule)
        conditions = []

        if service_id is not None:
            conditions.append((AlertRule.service_id == service_id) | (AlertRule.service_id.is_(None)))
        if enabled_only:
            conditions.append(AlertRule.enabled.is_(True))

        if conditions:
            stmt = stmt.where(and_(*conditions))

        stmt = stmt.order_by(AlertRule.created_at.desc())
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def update_rule(self, rule: AlertRule, updates: Dict[str, Any]) -> AlertRule:
        """Updates fields on an existing AlertRule instance."""
        for field, value in updates.items():
            if value is not None and hasattr(rule, field):
                setattr(rule, field, value)

        await self.session.flush()
        await self.session.refresh(rule)
        return rule

    async def delete_rule(self, rule: AlertRule) -> None:
        """Deletes an AlertRule from the database."""
        await self.session.delete(rule)
        await self.session.flush()

    # ------------------------------------------------------------------
    # Triggered Alerts
    # ------------------------------------------------------------------
    async def create_alert(
        self,
        rule_id: UUID,
        service_id: UUID,
        severity: str,
        current_value: Optional[float],
        threshold_value: Optional[float],
        evidence: Optional[Dict[str, Any]] = None,
        status: str = "active"
    ) -> Alert:
        """Creates and persists a new triggered Alert record."""
        now = datetime.now(timezone.utc)
        alert = Alert(
            rule_id=rule_id,
            service_id=service_id,
            status=status,
            severity=severity,
            current_value=current_value,
            threshold_value=threshold_value,
            triggered_at=now,
            last_seen_at=now,
            evidence=evidence or {}
        )
        self.session.add(alert)
        await self.session.flush()
        await self.session.refresh(alert)
        return alert

    async def get_active_alert(self, rule_id: UUID, service_id: UUID) -> Optional[Alert]:
        """Queries active/firing alert for a specific rule and service target."""
        stmt = (
            select(Alert)
            .where(
                and_(
                    Alert.rule_id == rule_id,
                    Alert.service_id == service_id,
                    Alert.status == "active"
                )
            )
            .order_by(desc(Alert.triggered_at))
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def get_latest_alert_for_rule(self, rule_id: UUID, service_id: UUID) -> Optional[Alert]:
        """Queries the most recent alert for a specific rule and service target regardless of status."""
        stmt = (
            select(Alert)
            .where(
                and_(
                    Alert.rule_id == rule_id,
                    Alert.service_id == service_id
                )
            )
            .order_by(desc(Alert.last_seen_at))
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def update_alert(self, alert: Alert, updates: Dict[str, Any]) -> Alert:
        """Updates fields on an existing Alert instance."""
        for field, value in updates.items():
            if hasattr(alert, field):
                setattr(alert, field, value)

        await self.session.flush()
        await self.session.refresh(alert)
        return alert

    async def get_alert_by_id(self, alert_id: UUID) -> Optional[Alert]:
        """Fetches a triggered Alert by primary key ID with rule & service relationships."""
        stmt = (
            select(Alert)
            .options(selectinload(Alert.rule), selectinload(Alert.service))
            .where(Alert.id == alert_id)
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def list_alerts(
        self,
        service_id: Optional[UUID] = None,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 100
    ) -> List[Alert]:
        """Queries recent triggered alerts with optional filters and preloaded relations."""
        stmt = select(Alert).options(selectinload(Alert.rule), selectinload(Alert.service))
        conditions = []

        if service_id:
            conditions.append(Alert.service_id == service_id)
        if status:
            conditions.append(Alert.status == status.lower())
        if severity:
            conditions.append(Alert.severity == severity.lower())

        if conditions:
            stmt = stmt.where(and_(*conditions))

        stmt = stmt.order_by(desc(Alert.triggered_at)).limit(min(limit, 500))
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

        """Deletes an AlertRule from the database."""
        await self.session.delete(rule)
        await self.session.flush()
