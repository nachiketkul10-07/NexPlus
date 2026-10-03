"""
Telemetry Repository Implementation for PostgreSQL
Manages async persistence and querying of HTTP telemetry events, metrics, and log entries.
"""
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.telemetry import TelemetryEvent, Metric, LogEntry
from app.schemas.telemetry import TelemetryEventCreate, MetricCreate, LogCreate


class PostgresTelemetryRepository:
    """Async repository for Telemetry ORM models."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ------------------------------------------------------------------
    # Telemetry Events
    # ------------------------------------------------------------------
    async def create_event(self, service_id: UUID, event_in: TelemetryEventCreate) -> TelemetryEvent:
        """Persists a single HTTP request telemetry event and auto-derives metric & log records."""
        occurred_at = event_in.timestamp or datetime.now(timezone.utc)
        duration_ms = event_in.duration_ms if event_in.duration_ms is not None else event_in.response_time_ms

        event = TelemetryEvent(
            service_id=service_id,
            request_id=event_in.request_id,
            occurred_at=occurred_at,
            method=event_in.method,
            endpoint=event_in.endpoint,
            status_code=event_in.status_code,
            duration_ms=duration_ms,
            outcome=event_in.outcome,
            error_type=event_in.error_type,
            error_message=event_in.error_message,
            metadata_json=event_in.metadata or {}
        )
        self.session.add(event)

        # Auto-derive Metric snapshots for real metrics pipeline
        dur_val = float(duration_ms) if duration_ms is not None else 0.0
        err_val = 1.0 if (event_in.status_code and event_in.status_code >= 400) else 0.0

        latency_metric = Metric(
            service_id=service_id,
            metric_name="avg_latency_ms",
            value=dur_val,
            window_seconds=60,
            recorded_at=occurred_at
        )
        error_rate_metric = Metric(
            service_id=service_id,
            metric_name="error_rate",
            value=err_val,
            window_seconds=60,
            recorded_at=occurred_at
        )
        requests_metric = Metric(
            service_id=service_id,
            metric_name="http_requests_total",
            value=1.0,
            window_seconds=60,
            recorded_at=occurred_at
        )
        self.session.add(latency_metric)
        self.session.add(error_rate_metric)
        self.session.add(requests_metric)

        # Auto-derive Log record for real application logs pipeline
        log_level = "INFO"
        if event_in.status_code and event_in.status_code >= 500:
            log_level = "CRITICAL" if event_in.status_code >= 503 else "ERROR"
        elif (event_in.status_code and event_in.status_code >= 400) or (dur_val >= 1000):
            log_level = "WARN"

        msg_parts = [f"HTTP {event_in.method or 'GET'} {event_in.endpoint or '/'}" ]
        if event_in.status_code:
            msg_parts.append(f"status {event_in.status_code}")
        msg_parts.append(f"duration {dur_val:.1f}ms")
        if event_in.error_message:
            msg_parts.append(f"- {event_in.error_message}")
        log_msg = " ".join(msg_parts)

        log_record = LogEntry(
            service_id=service_id,
            occurred_at=occurred_at,
            level=log_level,
            message=log_msg,
            request_id=event_in.request_id,
            trace_id=None,
            stack_trace=event_in.error_message if log_level in ("ERROR", "CRITICAL") else None,
            metadata_json=event_in.metadata or {}
        )
        self.session.add(log_record)

        return event

    async def create_events_batch(self, service_id: UUID, events_in: List[TelemetryEventCreate]) -> List[TelemetryEvent]:
        """Persists a batch of telemetry events."""
        records = []
        for event_in in events_in:
            rec = await self.create_event(service_id, event_in)
            records.append(rec)
        return records

    async def query_events(
        self,
        service_id: Optional[UUID] = None,
        from_ts: Optional[datetime] = None,
        to_ts: Optional[datetime] = None,
        limit: int = 100
    ) -> List[TelemetryEvent]:
        """Query recent telemetry events with optional filters."""
        stmt = select(TelemetryEvent)
        conditions = []

        if service_id:
            conditions.append(TelemetryEvent.service_id == service_id)
        if from_ts:
            conditions.append(TelemetryEvent.occurred_at >= from_ts)
        if to_ts:
            conditions.append(TelemetryEvent.occurred_at <= to_ts)

        if conditions:
            stmt = stmt.where(and_(*conditions))

        stmt = stmt.order_by(TelemetryEvent.occurred_at.desc()).limit(min(limit, 500))
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------
    async def create_metric(self, service_id: UUID, metric_in: MetricCreate) -> Metric:
        """Persists a single metric observation."""
        recorded_at = metric_in.recorded_at or metric_in.timestamp or datetime.now(timezone.utc)

        metric = Metric(
            service_id=service_id,
            metric_name=metric_in.metric_name,
            value=metric_in.value,
            window_seconds=metric_in.window_seconds,
            recorded_at=recorded_at
        )
        self.session.add(metric)
        return metric

    async def create_metrics_batch(self, service_id: UUID, metrics_in: List[MetricCreate]) -> List[Metric]:
        """Persists a batch of metric observations."""
        records = []
        for metric_in in metrics_in:
            rec = await self.create_metric(service_id, metric_in)
            records.append(rec)
        return records

    async def query_metrics(
        self,
        service_id: Optional[UUID] = None,
        metric_name: Optional[str] = None,
        from_ts: Optional[datetime] = None,
        to_ts: Optional[datetime] = None,
        limit: int = 300
    ) -> List[Metric]:
        """Query recorded metrics with optional filters."""
        stmt = select(Metric)
        conditions = []

        if service_id:
            conditions.append(Metric.service_id == service_id)
        if metric_name:
            conditions.append(Metric.metric_name == metric_name)
        if from_ts:
            conditions.append(Metric.recorded_at >= from_ts)
        if to_ts:
            conditions.append(Metric.recorded_at <= to_ts)

        if conditions:
            stmt = stmt.where(and_(*conditions))

        stmt = stmt.order_by(Metric.recorded_at.desc()).limit(min(limit, 1000))
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # ------------------------------------------------------------------
    # Log Entries
    # ------------------------------------------------------------------
    async def create_log(self, service_id: UUID, log_in: LogCreate) -> LogEntry:
        """Persists a single log entry."""
        occurred_at = log_in.occurred_at or log_in.timestamp or datetime.now(timezone.utc)

        log_entry = LogEntry(
            service_id=service_id,
            occurred_at=occurred_at,
            level=log_in.level,
            message=log_in.message,
            request_id=log_in.request_id,
            trace_id=log_in.trace_id,
            stack_trace=log_in.stack_trace,
            metadata_json=log_in.metadata or {}
        )
        self.session.add(log_entry)
        return log_entry

    async def create_logs_batch(self, service_id: UUID, logs_in: List[LogCreate]) -> List[LogEntry]:
        """Persists a batch of log entries."""
        records = []
        for log_in in logs_in:
            rec = await self.create_log(service_id, log_in)
            records.append(rec)
        return records

    async def query_logs(
        self,
        service_id: Optional[UUID] = None,
        level: Optional[str] = None,
        from_ts: Optional[datetime] = None,
        to_ts: Optional[datetime] = None,
        limit: int = 100
    ) -> List[LogEntry]:
        """Query application log lines with optional filters."""
        stmt = select(LogEntry)
        conditions = []

        if service_id:
            conditions.append(LogEntry.service_id == service_id)
        if level:
            conditions.append(LogEntry.level == level.upper())
        if from_ts:
            conditions.append(LogEntry.occurred_at >= from_ts)
        if to_ts:
            conditions.append(LogEntry.occurred_at <= to_ts)

        if conditions:
            stmt = stmt.where(and_(*conditions))

        stmt = stmt.order_by(LogEntry.occurred_at.desc()).limit(min(limit, 500))
        res = await self.session.execute(stmt)
        return list(res.scalars().all())
