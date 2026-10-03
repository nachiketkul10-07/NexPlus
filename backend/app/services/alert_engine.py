"""
Alert Engine Core Evaluation Pipeline for PulseOps
Evaluates metric threshold rules against telemetry data, manages alert lifecycle, state transitions, deduplication, and cooldowns.
"""
import math
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.alert import AlertRule, Alert
from app.models.service import Service
from app.models.telemetry import TelemetryEvent, Metric
from app.db.repositories.alert_repository import PostgresAlertRepository
from app.db.repositories.telemetry_repository import PostgresTelemetryRepository
from app.db.repositories.service_repository import PostgresServiceRepository
from app.schemas.alert import AlertEvaluationSummary
from app.core.metrics import (
    ALERT_EVALUATIONS_TOTAL,
    ALERTS_TRIGGERED_TOTAL,
    INCIDENTS_CREATED_TOTAL
)



class AlertEngine:
    """
    Deterministic Alert Evaluation Engine.
    Processes telemetry & metric snapshot data against active rules.
    Does NOT create incidents (Incident creation is deferred to Phase 8).
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.alert_repo = PostgresAlertRepository(session)
        self.telemetry_repo = PostgresTelemetryRepository(session)
        self.service_repo = PostgresServiceRepository(session)

    async def evaluate_rule(self, rule_id: UUID) -> AlertEvaluationSummary:
        """Evaluates a single alert rule by ID."""
        rule = await self.alert_repo.get_rule_by_id(rule_id)
        if not rule or not rule.enabled:
            return AlertEvaluationSummary(
                rules_evaluated=0,
                alerts_triggered=0,
                alerts_updated=0,
                alerts_resolved=0
            )

        return await self._process_rules([rule])

    async def evaluate_all_rules(self, service_id: Optional[UUID] = None) -> AlertEvaluationSummary:
        """Evaluates all enabled alert rules (optionally filtered by target service)."""
        rules = await self.alert_repo.list_rules(service_id=service_id, enabled_only=True)
        return await self._process_rules(rules)

    async def _process_rules(self, rules: List[AlertRule]) -> AlertEvaluationSummary:
        rules_evaluated = 0
        alerts_triggered = 0
        alerts_updated = 0
        alerts_resolved = 0

        # Fetch all active services for evaluation
        all_services = await self.service_repo.list_services()

        for rule in rules:
            rules_evaluated += 1

            # Determine target services for this rule
            if rule.service_id is not None:
                target_services = [s for s in all_services if s.id == rule.service_id]
            else:
                target_services = all_services

            for service in target_services:
                trig, upd, res = await self._evaluate_rule_for_service(rule, service)
                alerts_triggered += trig
                alerts_updated += upd
                alerts_resolved += res

        ALERT_EVALUATIONS_TOTAL.inc(rules_evaluated)

        return AlertEvaluationSummary(
            rules_evaluated=rules_evaluated,
            alerts_triggered=alerts_triggered,
            alerts_updated=alerts_updated,
            alerts_resolved=alerts_resolved
        )
    async def _evaluate_rule_for_service(
        self,
        rule: AlertRule,
        service: Service
    ) -> Tuple[int, int, int]:
        """Evaluates a single rule for a target service and updates alert state."""
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(seconds=rule.window_seconds)

        # 1. Compute observed value for rule metric
        observed_val, evidence_meta = await self._calculate_observed_value(
            service_id=service.id,
            metric_name=rule.metric_name,
            window_start=window_start,
            now=now
        )

        # 2. Check if threshold condition is crossed
        is_crossed = self._evaluate_condition(
            value=observed_val,
            operator=rule.operator,
            threshold=rule.threshold
        )

        trig = 0
        upd = 0
        res = 0

        # 3. Handle Alert Lifecycle, Deduplication, and Cooldown
        active_alert = await self.alert_repo.get_active_alert(rule.id, service.id)

        evidence_payload = {
            "metric_name": rule.metric_name,
            "observed_value": observed_val,
            "threshold_value": rule.threshold,
            "operator": rule.operator,
            "window_seconds": rule.window_seconds,
            "evaluated_at": now.isoformat(),
            **evidence_meta
        }

        if is_crossed:
            if active_alert:
                # Active alert exists: update last_seen_at and observed value (Deduplication!)
                await self.alert_repo.update_alert(
                    active_alert,
                    {
                        "last_seen_at": now,
                        "current_value": observed_val,
                        "evidence": evidence_payload
                    }
                )
                upd = 1
            else:
                # Check cooldown: after an alert resolves, cooldown is measured from resolved_at.
                latest_alert = await self.alert_repo.get_latest_alert_for_rule(rule.id, service.id)
                in_cooldown = False

                if latest_alert and latest_alert.status == "resolved":
                    # Cooldown is measured strictly from resolved_at timestamp
                    ref_time = latest_alert.resolved_at or latest_alert.last_seen_at
                    if ref_time:
                        if ref_time.tzinfo is None:
                            ref_time = ref_time.replace(tzinfo=timezone.utc)
                        if now.tzinfo is None:
                            now = now.replace(tzinfo=timezone.utc)
                        elapsed = (now - ref_time).total_seconds()
                        if elapsed < rule.cooldown_seconds:
                            in_cooldown = True

                if not in_cooldown:
                    # Create NEW Alert
                    new_alert = await self.alert_repo.create_alert(
                        rule_id=rule.id,
                        service_id=service.id,
                        severity=rule.severity,
                        current_value=observed_val,
                        threshold_value=rule.threshold,
                        evidence=evidence_payload,
                        status="active"
                    )
                    trig = 1
                    ALERTS_TRIGGERED_TOTAL.labels(severity=rule.severity or "warning").inc()

                    # Escalate alert to incident if create_incident is enabled on the rule
                    if rule.create_incident:
                        from app.services.incident_service import IncidentService
                        inc_service = IncidentService(self.session)
                        await inc_service.escalate_alert_to_incident(new_alert, rule, service)
                        INCIDENTS_CREATED_TOTAL.labels(severity=rule.severity or "warning").inc()
        else:
            if active_alert:
                # Condition cleared: Resolve existing active alert
                await self.alert_repo.update_alert(
                    active_alert,
                    {
                        "status": "resolved",
                        "resolved_at": now,
                        "last_seen_at": now,
                        "current_value": observed_val,
                        "evidence": evidence_payload
                    }
                )
                res = 1

        return trig, upd, res
    async def _calculate_observed_value(
        self,
        service_id: UUID,
        metric_name: str,
        window_start: datetime,
        now: datetime
    ) -> Tuple[float, Dict[str, Any]]:
        """Calculates current metric value from stored telemetry events or metric snapshots."""
        metric_lower = metric_name.lower().strip()

        if metric_lower == "error_rate":
            events = await self.telemetry_repo.query_events(
                service_id=service_id,
                from_ts=window_start,
                to_ts=now,
                limit=500
            )
            total = len(events)
            if total > 0:
                errors = sum(
                    1 for e in events
                    if (e.status_code is not None and e.status_code >= 400)
                    or e.outcome in ("error", "failure")
                )
                rate = round(errors / float(total), 4)
                return rate, {"total_requests": total, "failed_requests": errors, "source": "telemetry_events"}

            # Fallback to recorded metrics
            m_list = await self.telemetry_repo.query_metrics(
                service_id=service_id,
                metric_name="error_rate",
                from_ts=window_start,
                to_ts=now,
                limit=100
            )
            if m_list:
                avg_val = round(sum(m.value for m in m_list) / len(m_list), 4)
                return avg_val, {"sample_count": len(m_list), "source": "metrics_snapshots"}

            return 0.0, {"total_requests": 0, "source": "no_data"}

        elif metric_lower in ("avg_latency_ms", "latency", "duration_ms", "response_time"):
            events = await self.telemetry_repo.query_events(
                service_id=service_id,
                from_ts=window_start,
                to_ts=now,
                limit=500
            )
            durations = [e.duration_ms for e in events if e.duration_ms is not None]
            if durations:
                avg_latency = round(sum(durations) / float(len(durations)), 2)
                return avg_latency, {"sample_count": len(durations), "source": "telemetry_events"}

            # Fallback to metrics
            m_list = await self.telemetry_repo.query_metrics(
                service_id=service_id,
                metric_name=metric_name,
                from_ts=window_start,
                to_ts=now,
                limit=100
            )
            if m_list:
                avg_val = round(sum(m.value for m in m_list) / float(len(m_list)), 2)
                return avg_val, {"sample_count": len(m_list), "source": "metrics_snapshots"}

            return 0.0, {"sample_count": 0, "source": "no_data"}

        elif metric_lower in ("service_health", "service_status", "health"):
            svc = await self.service_repo.get_by_id(service_id)
            if svc and svc.status.lower() in ("unhealthy", "degraded", "down"):
                return 0.0, {"service_status": svc.status, "source": "service_record"}
            return 1.0, {"service_status": svc.status if svc else "unknown", "source": "service_record"}

        else:
            # Generic metric query
            m_list = await self.telemetry_repo.query_metrics(
                service_id=service_id,
                metric_name=metric_name,
                from_ts=window_start,
                to_ts=now,
                limit=100
            )
            if m_list:
                avg_val = round(sum(m.value for m in m_list) / float(len(m_list)), 4)
                return avg_val, {"sample_count": len(m_list), "source": "metrics_snapshots"}

            # Try to get most recent metric value if outside window
            m_latest = await self.telemetry_repo.query_metrics(
                service_id=service_id,
                metric_name=metric_name,
                limit=1
            )
            if m_latest:
                return float(m_latest[0].value), {"sample_count": 1, "source": "latest_metric_fallback"}

            return 0.0, {"sample_count": 0, "source": "no_data"}

    @staticmethod
    def _evaluate_condition(value: float, operator: str, threshold: float) -> bool:
        """Deterministically evaluates arithmetic operator condition."""
        if operator == ">":
            return value > threshold
        elif operator == ">=":
            return value >= threshold
        elif operator == "<":
            return value < threshold
        elif operator == "<=":
            return value <= threshold
        elif operator == "=":
            return abs(value - threshold) < 1e-6
        return False
