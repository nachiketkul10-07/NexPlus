"""
Telemetry Ingestion & Query Endpoints
Handles HTTP observations, metric snapshots, application logs, and telemetry query contracts.
Ingestion rate limits are enforced per authenticated service in the service-auth dependency.
"""
from datetime import datetime
from typing import List, Optional, Union, Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, Query, Request, status, HTTPException
from pydantic import Field

from app.api.deps import (
    get_authenticated_service,
    verify_service_ownership,
    get_telemetry_repository,
    get_service_repository,
    require_authenticated_user,
)
from app.core.metrics import (
    TELEMETRY_EVENTS_INGESTED_TOTAL,
    TELEMETRY_METRICS_INGESTED_TOTAL,
    TELEMETRY_LOGS_INGESTED_TOTAL,
    TELEMETRY_INGESTION_ERRORS_TOTAL
)

from app.db.repositories.telemetry_repository import PostgresTelemetryRepository
from app.db.repositories.service_repository import PostgresServiceRepository
from app.models.service import Service
from app.schemas.telemetry import (
    TelemetryEventCreate, TelemetryEventResponse,
    MetricCreate, MetricResponse,
    LogCreate, LogResponse,
    UnifiedTelemetryBatchPayload, IngestionResponse
)
from app.schemas.user import UserResponse, UserRole

router = APIRouter()

EventBatch = Annotated[List[TelemetryEventCreate], Field(max_length=100)]
MetricBatch = Annotated[List[MetricCreate], Field(max_length=100)]
LogBatch = Annotated[List[LogCreate], Field(max_length=100)]


async def _visible_service_ids(
    service_repo: PostgresServiceRepository,
    current_user: UserResponse,
    requested_service_id: Optional[UUID],
) -> Optional[List[UUID]]:
    """Return a user's service scope and reject an explicitly inaccessible service."""
    if current_user.role == UserRole.ADMIN:
        if requested_service_id is not None and not await service_repo.get_by_id(requested_service_id):
            raise HTTPException(status_code=404, detail="Service not found.")
        return None

    services = await service_repo.list_services_for_user(current_user.id)
    visible_ids = [service.id for service in services]
    if requested_service_id is not None and requested_service_id not in visible_ids:
        raise HTTPException(status_code=404, detail="Service not found.")
    return visible_ids


# ----------------------------------------------------------------------
# INGESTION ENDPOINTS (Service Authentication Required)
# ----------------------------------------------------------------------

@router.post("/events", response_model=IngestionResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest_telemetry_events(
    payload: Union[TelemetryEventCreate, EventBatch],
    request: Request,
    service: Annotated[Service, Depends(get_authenticated_service)],
    telemetry_repo: Annotated[PostgresTelemetryRepository, Depends(get_telemetry_repository)],
    service_repo: Annotated[PostgresServiceRepository, Depends(get_service_repository)]
):
    """
    Ingests one or multiple HTTP telemetry events from instrumented services.
    Authenticated via Service Ingest Key (X-Ingest-Key header).
    """
    events_list = payload if isinstance(payload, list) else [payload]
    if not events_list:
        raise HTTPException(status_code=422, detail="At least one event is required.")

    for item in events_list:
        verify_service_ownership(service, item.service_id)

    try:
        await telemetry_repo.create_events_batch(service.id, events_list)
        await service_repo.update_last_seen(service.id)
        await telemetry_repo.session.commit()
    except Exception:
        TELEMETRY_INGESTION_ERRORS_TOTAL.labels(telemetry_type="event").inc()
        raise
    TELEMETRY_EVENTS_INGESTED_TOTAL.labels(telemetry_type="event", outcome="success").inc(len(events_list))

    req_id = getattr(request.state, "request_id", "req_unknown")
    return IngestionResponse(
        status="accepted",
        accepted_count=len(events_list),
        rejected_count=0,
        request_id=req_id
    )


@router.post("/metrics", response_model=IngestionResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest_metrics(
    payload: Union[MetricCreate, MetricBatch],
    request: Request,
    service: Annotated[Service, Depends(get_authenticated_service)],
    telemetry_repo: Annotated[PostgresTelemetryRepository, Depends(get_telemetry_repository)],
    service_repo: Annotated[PostgresServiceRepository, Depends(get_service_repository)]
):
    """
    Ingests metric observations (e.g. error_rate, avg_latency_ms, request_count).
    Authenticated via Service Ingest Key.
    """
    metrics_list = payload if isinstance(payload, list) else [payload]
    if not metrics_list:
        raise HTTPException(status_code=422, detail="At least one metric is required.")

    for item in metrics_list:
        verify_service_ownership(service, item.service_id)

    try:
        await telemetry_repo.create_metrics_batch(service.id, metrics_list)
        await service_repo.update_last_seen(service.id)
        await telemetry_repo.session.commit()

        TELEMETRY_EVENTS_INGESTED_TOTAL.labels(telemetry_type="metric", outcome="success").inc(len(metrics_list))
        TELEMETRY_METRICS_INGESTED_TOTAL.labels(outcome="success").inc(len(metrics_list))
    except Exception:
        TELEMETRY_INGESTION_ERRORS_TOTAL.labels(telemetry_type="metric").inc()
        raise

    req_id = getattr(request.state, "request_id", "req_unknown")
    return IngestionResponse(
        status="accepted",
        accepted_count=len(metrics_list),
        rejected_count=0,
        request_id=req_id
    )


@router.post("/logs", response_model=IngestionResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest_logs(
    payload: Union[LogCreate, LogBatch],
    request: Request,
    service: Annotated[Service, Depends(get_authenticated_service)],
    telemetry_repo: Annotated[PostgresTelemetryRepository, Depends(get_telemetry_repository)],
    service_repo: Annotated[PostgresServiceRepository, Depends(get_service_repository)]
):
    """
    Ingests structured application logs.
    Authenticated via Service Ingest Key.
    """
    logs_list = payload if isinstance(payload, list) else [payload]
    if not logs_list:
        raise HTTPException(status_code=422, detail="At least one log is required.")

    for item in logs_list:
        verify_service_ownership(service, item.service_id)

    try:
        await telemetry_repo.create_logs_batch(service.id, logs_list)
        await service_repo.update_last_seen(service.id)
        await telemetry_repo.session.commit()

        TELEMETRY_EVENTS_INGESTED_TOTAL.labels(telemetry_type="log", outcome="success").inc(len(logs_list))
        TELEMETRY_LOGS_INGESTED_TOTAL.labels(outcome="success").inc(len(logs_list))
    except Exception:
        TELEMETRY_INGESTION_ERRORS_TOTAL.labels(telemetry_type="log").inc()
        raise

    req_id = getattr(request.state, "request_id", "req_unknown")
    return IngestionResponse(
        status="accepted",
        accepted_count=len(logs_list),
        rejected_count=0,
        request_id=req_id
    )


@router.post("/ingest", response_model=IngestionResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest_unified_batch(
    payload: UnifiedTelemetryBatchPayload,
    request: Request,
    service: Annotated[Service, Depends(get_authenticated_service)],
    telemetry_repo: Annotated[PostgresTelemetryRepository, Depends(get_telemetry_repository)],
    service_repo: Annotated[PostgresServiceRepository, Depends(get_service_repository)]
):
    """
    Unified telemetry ingestion endpoint accepting events, metrics, and logs in a single batch.
    Authenticated via Service Ingest Key.
    """
    verify_service_ownership(service, payload.service_id)

    accepted_count = 0
    if payload.events:
        for ev in payload.events:
            verify_service_ownership(service, ev.service_id)
        await telemetry_repo.create_events_batch(service.id, payload.events)
        accepted_count += len(payload.events)

    if payload.metrics:
        for m in payload.metrics:
            verify_service_ownership(service, m.service_id)
        await telemetry_repo.create_metrics_batch(service.id, payload.metrics)
        accepted_count += len(payload.metrics)

    if payload.logs:
        for l in payload.logs:
            verify_service_ownership(service, l.service_id)
        await telemetry_repo.create_logs_batch(service.id, payload.logs)
        accepted_count += len(payload.logs)

    await service_repo.update_last_seen(service.id)
    await telemetry_repo.session.commit()

    if payload.events:
        TELEMETRY_EVENTS_INGESTED_TOTAL.labels(telemetry_type="event", outcome="success").inc(len(payload.events))
    if payload.metrics:
        TELEMETRY_EVENTS_INGESTED_TOTAL.labels(telemetry_type="metric", outcome="success").inc(len(payload.metrics))
        TELEMETRY_METRICS_INGESTED_TOTAL.labels(outcome="success").inc(len(payload.metrics))
    if payload.logs:
        TELEMETRY_EVENTS_INGESTED_TOTAL.labels(telemetry_type="log", outcome="success").inc(len(payload.logs))
        TELEMETRY_LOGS_INGESTED_TOTAL.labels(outcome="success").inc(len(payload.logs))

    req_id = getattr(request.state, "request_id", "req_unknown")
    return IngestionResponse(
        status="accepted",
        accepted_count=accepted_count,
        rejected_count=0,
        request_id=req_id
    )


# ----------------------------------------------------------------------
# QUERY ENDPOINTS (User Session Required)
# ----------------------------------------------------------------------

@router.get("/events", response_model=List[TelemetryEventResponse], status_code=status.HTTP_200_OK)
async def query_telemetry_events(
    telemetry_repo: Annotated[PostgresTelemetryRepository, Depends(get_telemetry_repository)],
    service_repo: Annotated[PostgresServiceRepository, Depends(get_service_repository)],
    current_user: Annotated[UserResponse, Depends(require_authenticated_user)],
    service_id: Optional[UUID] = Query(None, description="Filter by service UUID"),
    from_ts: Optional[datetime] = Query(None, alias="from"),
    to_ts: Optional[datetime] = Query(None, alias="to"),
    limit: int = Query(100, ge=1, le=500)
):
    """Query telemetry events by service or timestamp range."""
    service_ids = await _visible_service_ids(service_repo, current_user, service_id)
    return await telemetry_repo.query_events(
        service_id=service_id, from_ts=from_ts, to_ts=to_ts, limit=limit, service_ids=service_ids
    )


@router.get("/metrics", response_model=List[MetricResponse], status_code=status.HTTP_200_OK)
async def query_metrics(
    telemetry_repo: Annotated[PostgresTelemetryRepository, Depends(get_telemetry_repository)],
    service_repo: Annotated[PostgresServiceRepository, Depends(get_service_repository)],
    current_user: Annotated[UserResponse, Depends(require_authenticated_user)],
    service_id: Optional[UUID] = Query(None, description="Filter by service UUID"),
    metric_name: Optional[str] = Query(None, description="Metric name filter (e.g. error_rate)"),
    from_ts: Optional[datetime] = Query(None, alias="from"),
    to_ts: Optional[datetime] = Query(None, alias="to"),
    limit: int = Query(300, ge=1, le=1000)
):
    """Query recorded metric snapshots."""
    service_ids = await _visible_service_ids(service_repo, current_user, service_id)
    return await telemetry_repo.query_metrics(
        service_id=service_id,
        metric_name=metric_name,
        from_ts=from_ts,
        to_ts=to_ts,
        limit=limit,
        service_ids=service_ids,
    )


@router.get("/logs", response_model=List[LogResponse], status_code=status.HTTP_200_OK)
async def query_logs(
    telemetry_repo: Annotated[PostgresTelemetryRepository, Depends(get_telemetry_repository)],
    service_repo: Annotated[PostgresServiceRepository, Depends(get_service_repository)],
    current_user: Annotated[UserResponse, Depends(require_authenticated_user)],
    service_id: Optional[UUID] = Query(None, description="Filter by service UUID"),
    level: Optional[str] = Query(None, description="Log level filter (e.g. ERROR)"),
    from_ts: Optional[datetime] = Query(None, alias="from"),
    to_ts: Optional[datetime] = Query(None, alias="to"),
    limit: int = Query(100, ge=1, le=500)
):
    """Query application log records."""
    service_ids = await _visible_service_ids(service_repo, current_user, service_id)
    return await telemetry_repo.query_logs(
        service_id=service_id,
        level=level,
        from_ts=from_ts,
        to_ts=to_ts,
        limit=limit,
        service_ids=service_ids,
    )
