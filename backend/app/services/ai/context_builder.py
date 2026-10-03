"""
Incident Context Builder & Secret Redactor for NexPulse AI Assistant
Constructs bounded, sanitized, and prompt-injection-safe incident context.
"""
import re
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.core.config import settings
from app.models.incident import Incident, IncidentEvent
from app.models.telemetry import TelemetryEvent, Metric, LogEntry
from app.models.alert import Alert, AlertRule


# Regex patterns for secret scrubbing
SECRET_PATTERNS = [
    (r'(?i)(bearer\s+)[A-Za-z0-9\-\._~\+\/]+=*', r'\1[REDACTED_TOKEN]'),
    (r'(?i)(jwt|access_token|refresh_token|token|password|pass|secret|api_key|ingest_key|authorization)\s*[:=]\s*["\']?[A-Za-z0-9\-\._~\+\/]{8,}["\']?', r'\1: "[REDACTED_SECRET]"'),
    (r'pik_live_[a-f0-9]{32,}', '[REDACTED_INGEST_KEY]'),
    (r'eyJ[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*', '[REDACTED_JWT]'),
]


def redact_secrets_from_text(text: str) -> str:
    """Scrubs sensitive credentials, tokens, and keys from raw text string."""
    if not text:
        return ""
    sanitized = text
    for pattern, replacement in SECRET_PATTERNS:
        sanitized = re.sub(pattern, replacement, sanitized)
    return sanitized


def sanitize_dict_secrets(data: Any) -> Any:
    """Recursively scrubs secret keys and values from dictionary/list payloads."""
    if isinstance(data, dict):
        cleaned = {}
        for key, value in data.items():
            key_lower = str(key).lower()
            if any(s in key_lower for s in ["password", "token", "secret", "authorization", "ingest_key", "api_key", "cookie"]):
                cleaned[key] = "[REDACTED_SECRET]"
            else:
                cleaned[key] = sanitize_dict_secrets(value)
        return cleaned
    elif isinstance(data, list):
        return [sanitize_dict_secrets(item) for item in data]
    elif isinstance(data, str):
        return redact_secrets_from_text(data)
    return data
class IncidentContextBuilder:
    """Queries and packages bounded, sanitized incident context for AI analysis."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def build_context(self, incident: Incident) -> Dict[str, Any]:
        """Collects telemetry, alert evidence, timeline events, and logs for an incident."""
        incident_info = {
            "id": str(incident.id),
            "title": redact_secrets_from_text(incident.title),
            "description": redact_secrets_from_text(incident.description or "No description provided."),
            "severity": incident.severity,
            "status": incident.status,
            "opened_at": incident.opened_at.isoformat() if incident.opened_at else None,
            "resolved_at": incident.resolved_at.isoformat() if incident.resolved_at else None,
            "resolution_note": redact_secrets_from_text(incident.resolution_note or ""),
            "service": {
                "id": str(incident.service_id),
                "name": incident.service.name if incident.service else "Unknown Service",
                "environment": incident.service.environment if incident.service else "unknown",
                "status": incident.service.status if incident.service else "unknown",
            },
        }

        alert_info = None
        if incident.originating_alert:
            alert = incident.originating_alert
            alert_info = {
                "alert_id": str(alert.id),
                "status": alert.status,
                "severity": alert.severity,
                "triggered_at": alert.triggered_at.isoformat() if alert.triggered_at else None,
                "rule_name": alert.rule.name if alert.rule else "Unknown Rule",
                "metric_name": alert.rule.metric_name if alert.rule else None,
                "threshold": alert.threshold_value,
                "current_value": alert.current_value,
                "evidence_snapshot": sanitize_dict_secrets(alert.evidence or {}),
            }

        timeline_stmt = (
            select(IncidentEvent)
            .where(IncidentEvent.incident_id == incident.id)
            .order_by(IncidentEvent.created_at.desc())
            .limit(15)
        )
        timeline_res = await self.session.execute(timeline_stmt)
        events = timeline_res.scalars().all()

        timeline_list = []
        for ev in reversed(events):
            timeline_list.append({
                "event_type": ev.event_type,
                "created_at": ev.created_at.isoformat(),
                "message": redact_secrets_from_text(ev.message),
                "actor": ev.actor.full_name if ev.actor else ("System" if ev.actor_user_id is None else "User"),
            })

        log_stmt = (
            select(LogEntry)
            .where(LogEntry.service_id == incident.service_id)
            .order_by(LogEntry.occurred_at.desc())
            .limit(settings.AI_MAX_LOG_ENTRIES)
        )
        log_res = await self.session.execute(log_stmt)
        log_entries = log_res.scalars().all()

        logs_list = []
        for log in reversed(log_entries):
            logs_list.append({
                "timestamp": log.occurred_at.isoformat(),
                "level": log.level,
                "message": redact_secrets_from_text(log.message),
                "request_id": log.request_id,
            })

        metric_stmt = (
            select(Metric)
            .where(Metric.service_id == incident.service_id)
            .order_by(Metric.recorded_at.desc())
            .limit(settings.AI_MAX_METRIC_POINTS)
        )
        metric_res = await self.session.execute(metric_stmt)
        metric_entries = metric_res.scalars().all()

        metrics_list = []
        for m in reversed(metric_entries):
            metrics_list.append({
                "timestamp": m.recorded_at.isoformat(),
                "metric_name": m.metric_name,
                "value": m.value,
                "unit": "value",
            })

        context_payload = {
            "incident": incident_info,
            "originating_alert": alert_info,
            "timeline": timeline_list,
            "recent_logs": logs_list,
            "recent_metrics": metrics_list,
        }

        serialized = json.dumps(context_payload, indent=2)
        if len(serialized) > settings.AI_MAX_CONTEXT_CHARS:
            context_payload["recent_logs"] = logs_list[:5]
            context_payload["recent_metrics"] = metrics_list[:10]
            context_payload["truncated"] = True

        return context_payload
