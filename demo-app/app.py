"""
PulseOps Controllable Demo Application
Simulates normal, slow, and error traffic patterns for PulseOps observability.
"""
import os
import time
import asyncio
import httpx
from urllib.parse import urljoin
from datetime import datetime, timezone
from typing import Dict, List, Any
from fastapi import FastAPI, Query, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

app = FastAPI(
    title="PulseOps Demo Application",
    description="Controllable target application monitored by PulseOps",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

demo_origins = [
    origin.strip()
    for origin in os.getenv(
        "DEMO_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174"
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=demo_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Accept", "Content-Type"],
)


class StripServicePrefix:
    """Allow this app to serve both locally at `/` and on Vercel at `/demo`."""

    def __init__(self, app, prefix: str):
        self.app = app
        self.prefix = prefix.rstrip("/")

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            path = scope.get("path", "")
            if path == self.prefix or path.startswith(self.prefix + "/"):
                scope = dict(scope)
                scope["path"] = path[len(self.prefix):] or "/"
                raw_path = scope.get("raw_path")
                if raw_path:
                    scope["raw_path"] = raw_path[len(self.prefix.encode("ascii")): ] or b"/"
        await self.app(scope, receive, send)


# Services can receive the original public path (including their route prefix).
# This is a no-op for local requests and for routes Vercel has already rewritten.
app.add_middleware(StripServicePrefix, prefix="/demo")

# Telemetry client settings
_vercel_host = os.getenv("VERCEL_URL")
_default_ingest_url = (
    f"https://{_vercel_host}/api/v1/telemetry/events"
    if _vercel_host
    else "http://localhost:8000/api/v1/telemetry/events"
)
_api_service_url = os.getenv("NEXPULSE_API_URL")
if _api_service_url:
    # Vercel service bindings route this server-to-server request directly to
    # the API service, avoiding its public deployment-protection/routing layer.
    INGEST_URL = urljoin(
        _api_service_url.rstrip("/") + "/",
        "api/v1/telemetry/events",
    )
else:
    INGEST_URL = os.getenv("PULSEOPS_INGEST_URL", _default_ingest_url)
# The checked-in fallback only supports the explicitly local demo seed. Vercel
# deployments must provide the per-service key through encrypted environment config.
INGEST_KEY = os.getenv("PULSEOPS_INGEST_KEY") or (None if os.getenv("VERCEL") else "pik_dev_demo_app_secret_key_12345")
ENABLE_TELEMETRY = os.getenv("ENABLE_TELEMETRY", "true").lower() in ("true", "1", "yes")
# OpenTelemetry Instrumentation for Demo Application
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    OTEL_SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "pulseops-demo-app")
    OTEL_ENABLED = os.getenv("OTEL_ENABLED", "true").lower() in ("true", "1", "yes")

    if OTEL_ENABLED:
        resource = Resource.create(attributes={SERVICE_NAME: OTEL_SERVICE_NAME})
        provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(provider)
        FastAPIInstrumentor().instrument_app(app, tracer_provider=provider)
except Exception as _otel_exc:
    pass



async def _post_telemetry(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Asynchronously dispatches HTTP telemetry observation to PulseOps ingestion engine."""
    if not ENABLE_TELEMETRY:
        return {"accepted": False, "status_code": None, "reason": "disabled"}
    if not INGEST_KEY:
        return {"accepted": False, "status_code": None, "reason": "missing_key"}
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.post(
                INGEST_URL,
                json=payload,
                headers={"X-Ingest-Key": INGEST_KEY}
            )
            # Treat every 2xx response (including the API's 202 Accepted) as
            # successful ingestion. Keep this explicit so the demo summary and
            # the API's accepted response contract cannot disagree.
            accepted = 200 <= response.status_code < 300
            return {"accepted": accepted, "status_code": response.status_code}
    except httpx.HTTPError:
        # Keep the demo target available when NexPulse is offline, but report
        # the failed delivery to the scenario caller instead of claiming success.
        return {"accepted": False, "status_code": None, "reason": "unreachable"}


@app.middleware("http")
async def telemetry_middleware(request: Request, call_next):
    """Observes request lifecycle and reports telemetry to PulseOps."""
    start_time = time.time()
    error_msg = None
    status_code = 500
    response = None

    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    except Exception as exc:
        error_msg = str(exc)
        raise exc
    finally:
        duration_ms = int((time.time() - start_time) * 1000)
        outcome = "success"
        if status_code >= 400:
            outcome = "error"
        elif duration_ms >= 1000:
            outcome = "slow"

        # Ignore doc URLs and internal favicon requests
        if not request.url.path.startswith(("/docs", "/redoc", "/openapi.json", "/favicon.ico")):
            payload = {
                "service_id": "demo-app",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "method": request.method,
                "endpoint": request.url.path,
                "status_code": status_code,
                "duration_ms": duration_ms,
                "outcome": outcome,
                "error_type": "HTTPError" if status_code >= 400 else None,
                "error_message": error_msg or (f"HTTP {status_code}" if status_code >= 400 else None),
                "metadata": {"source": "demo-app-instrumentation"}
            }
            # Await the outbound request so serverless runtimes don't freeze the
            # function before telemetry has been delivered.
            delivery = await _post_telemetry(payload)
            # Attach delivery outcome to this request's response. This remains
            # correctly correlated when the demo scenarios run concurrently.
            if response is not None:
                response.headers["X-NexPulse-Telemetry-Accepted"] = (
                    "true" if delivery.get("accepted") else "false"
                )
                delivery_status = delivery.get("status_code")
                if delivery_status is not None:
                    response.headers["X-NexPulse-Telemetry-Status"] = str(delivery_status)
                delivery_reason = delivery.get("reason")
                if delivery_reason:
                    response.headers["X-NexPulse-Telemetry-Reason"] = delivery_reason


# Global Exception Handler to prevent stack trace leaks
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail}
        )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal Server Error"}
    )


# Standard example data
SAMPLE_USERS: List[Dict[str, Any]] = [
    {"id": 1, "username": "alice", "email": "alice@example.com", "role": "admin", "status": "active"},
    {"id": 2, "username": "bob", "email": "bob@example.com", "role": "developer", "status": "active"},
    {"id": 3, "username": "charlie", "email": "charlie@example.com", "role": "viewer", "status": "inactive"}
]

SAMPLE_ORDERS: List[Dict[str, Any]] = [
    {"id": "ord-101", "user_id": 1, "item": "Cloud Monitoring License", "amount": 199.99, "status": "completed"},
    {"id": "ord-102", "user_id": 2, "item": "Telemetry Ingest Pack", "amount": 49.50, "status": "processing"},
    {"id": "ord-103", "user_id": 1, "item": "Incident Automation Plugin", "amount": 29.00, "status": "completed"}
]


@app.get("/", status_code=status.HTTP_200_OK)
async def get_root() -> Dict[str, str]:
    """Root endpoint returning basic application metadata."""
    return {
        "service": "demo-app",
        "status": "running",
        "version": "1.0.0"
    }


@app.get("/api/health", status_code=status.HTTP_200_OK)
async def get_health() -> Dict[str, Any]:
    """Healthy service status endpoint."""
    return {
        "status": "healthy",
        "service": "demo-app",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/api/users", status_code=status.HTTP_200_OK)
async def get_users() -> List[Dict[str, Any]]:
    """Returns a list of sample users."""
    return SAMPLE_USERS


@app.get("/api/orders", status_code=status.HTTP_200_OK)
async def get_orders() -> List[Dict[str, Any]]:
    """Returns a list of sample orders."""
    return SAMPLE_ORDERS


@app.get("/api/slow", status_code=status.HTTP_200_OK)
async def get_slow(
    delay: float = Query(
        default=3.0,
        ge=0.0,
        le=10.0,
        description="Simulated latency in seconds (0.0 to 10.0)"
    )
) -> Dict[str, Any]:
    """
    Intentionally delays response using non-blocking async sleep.
    Bounded between 0.0s and 10.0s to prevent resource exhaustion attacks.
    """
    await asyncio.sleep(delay)
    return {
        "status": "completed",
        "requested_delay_seconds": delay,
        "message": f"Response completed after {delay} second(s)"
    }


@app.get("/api/error")
async def get_error():
    """
    Intentionally raises HTTP 500 error to simulate application failures.
    """
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Simulated server failure endpoint triggered"
    )


@app.post("/api/demo/run", status_code=status.HTTP_200_OK)
async def run_demo_scenario() -> Dict[str, Any]:
    """Generate a small, repeatable mix of successful, slow, and failed requests."""
    paths = [
        "/api/health",
        "/api/users",
        "/api/orders",
        "/api/slow?delay=1.1",
        "/api/error",
        "/api/error",
    ]
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://demo-app.local") as client:
        results = await asyncio.gather(*(client.get(path) for path in paths))

    failed = sum(1 for result in results if result.status_code >= 400)
    telemetry_accepted = sum(
        1 for result in results
        if result.headers.get("X-NexPulse-Telemetry-Accepted") == "true"
    )
    telemetry_failed = len(results) - telemetry_accepted
    failure_statuses = sorted({
        int(result.headers["X-NexPulse-Telemetry-Status"])
        for result in results
        if result.headers.get("X-NexPulse-Telemetry-Accepted") != "true"
        and result.headers.get("X-NexPulse-Telemetry-Status", "").isdigit()
    })
    return {
        "status": "completed",
        "requests_generated": len(results),
        "successful_requests": len(results) - failed,
        "failed_requests": failed,
        "slow_requests": 1,
        "telemetry_accepted": telemetry_accepted,
        "telemetry_failed": telemetry_failed,
        "telemetry_failure_statuses": failure_statuses,
    }

