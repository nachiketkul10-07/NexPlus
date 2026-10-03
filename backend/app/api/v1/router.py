"""
Main API v1 Router Registration
Aggregates all version 1 route modules.
"""
from fastapi import APIRouter
from app.api.v1.endpoints import health, auth, services, telemetry, alerts, incidents, tasks

api_v1_router = APIRouter()

# Register Health module
api_v1_router.include_router(health.router, tags=["Health"])

# Register Auth module
api_v1_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])

# Register Services module
api_v1_router.include_router(services.router, prefix="/services", tags=["Services"])

# Register Telemetry Ingestion & Query module
api_v1_router.include_router(telemetry.router, prefix="/telemetry", tags=["Telemetry"])

# Register Alerts module
api_v1_router.include_router(alerts.router, prefix="/alerts", tags=["Alerts"])

# Register Incidents module
api_v1_router.include_router(incidents.router, prefix="/incidents", tags=["Incidents"])

# Register Tasks module
api_v1_router.include_router(tasks.router, prefix="/tasks", tags=["Tasks"])


# Aliases for /api/v1/metrics and /api/v1/logs endpoints
@api_v1_router.get("/metrics", tags=["Metrics"])
async def metrics_alias(
    req: telemetry.Request,
    telemetry_repo=telemetry.Depends(telemetry.get_telemetry_repository),
    current_user=telemetry.Depends(telemetry.require_authenticated_user),
    service_id=telemetry.Query(None),
    metric_name=telemetry.Query(None),
    from_ts=telemetry.Query(None, alias="from"),
    to_ts=telemetry.Query(None, alias="to"),
    limit=telemetry.Query(300, ge=1, le=1000)
):
    return await telemetry.query_metrics(
        telemetry_repo=telemetry_repo,
        current_user=current_user,
        service_id=service_id,
        metric_name=metric_name,
        from_ts=from_ts,
        to_ts=to_ts,
        limit=limit
    )

@api_v1_router.get("/logs", tags=["Logs"])
async def logs_alias(
    req: telemetry.Request,
    telemetry_repo=telemetry.Depends(telemetry.get_telemetry_repository),
    current_user=telemetry.Depends(telemetry.require_authenticated_user),
    service_id=telemetry.Query(None),
    level=telemetry.Query(None),
    from_ts=telemetry.Query(None, alias="from"),
    to_ts=telemetry.Query(None, alias="to"),
    limit=telemetry.Query(100, ge=1, le=500)
):
    return await telemetry.query_logs(
        telemetry_repo=telemetry_repo,
        current_user=current_user,
        service_id=service_id,
        level=level,
        from_ts=from_ts,
        to_ts=to_ts,
        limit=limit
    )


