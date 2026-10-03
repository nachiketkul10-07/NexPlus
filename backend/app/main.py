"""
PulseOps Backend Entry Point
Assembles FastAPI application, registers middleware stack, exception handlers, and API v1 routers.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, status, HTTPException, Depends
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field, ConfigDict

from app.core.config import settings
from app.core.logging import logger
from app.core.errors import (
    http_exception_handler,
    validation_exception_handler,
    unhandled_exception_handler,
)
from app.core.redis import init_redis, close_redis, check_redis_health
from app.db.init_db import init_db
from app.middleware.request_id import RequestIdMiddleware
from app.middleware.logging import HTTPLoggingMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.size_limit import PayloadSizeLimitMiddleware
from app.api.v1.router import api_v1_router
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response
from app.core.telemetry import init_telemetry
from app.middleware.metrics import PrometheusMetricsMiddleware
from app.middleware.cookie_csrf import CookieCSRFMiddleware



@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI Application Lifespan Context Manager"""
    settings.validate_production_settings()
    # Startup: Initialize Database & Seed Default Users
    await init_db()
    # Startup: Initialize Redis Pool
    await init_redis()
    if settings.is_production:
        from app.core.redis import redis_manager
        if not await redis_manager.ping():
            raise RuntimeError("Production Redis connection is required for shared rate limits and token revocation.")
    yield
    # Shutdown: Cleanly Close Redis Pool
    await close_redis()


def create_application() -> FastAPI:
    """FastAPI Application Factory"""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description="PulseOps Incident-Monitoring & Observability Platform Backend API",
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
        openapi_url=None if settings.is_production else "/openapi.json",
        lifespan=lifespan
    )

    # 1. Register Custom Exception Handlers
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(404, http_exception_handler)
    app.add_exception_handler(405, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # 2. Register Middleware Stack (Executed in reverse order of registration)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    app.add_middleware(CookieCSRFMiddleware)
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.trusted_hosts_list if settings.is_production else ["*"],
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(HTTPLoggingMiddleware)
    app.add_middleware(PayloadSizeLimitMiddleware)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(PrometheusMetricsMiddleware)

    # 3. Initialize OpenTelemetry Instrumentation
    init_telemetry(app)

    # 3. Include API Routers
    app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)

    # 4. Top-level Root Health Check Endpoint
    @app.get("/health", status_code=status.HTTP_200_OK, tags=["Health"])
    async def top_level_health():
        redis_health = await check_redis_health()
        return {
            "status": "healthy",
            "service": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
            "dependencies": {
                "redis": redis_health["status"]
            }
        }

    # 4.1 Prometheus Operational Metrics Endpoint
    @app.get("/metrics", include_in_schema=False)
    async def metrics_endpoint():
        if not settings.PROMETHEUS_ENABLED:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Metrics collection disabled."
            )
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    if not settings.is_production:
        # Test-only routes add unnecessary attack surface to a deployed API.
        class ValidationTestModel(BaseModel):
            name: str = Field(..., min_length=2)
            count: int = Field(..., ge=1)

        @app.post("/test-validation", status_code=status.HTTP_200_OK, include_in_schema=False)
        async def test_validation(payload: ValidationTestModel):
            return {"status": "ok", "data": payload}

        @app.get("/test-unhandled-error", include_in_schema=False)
        async def test_unhandled_error():
            raise RuntimeError("Test unhandled exception for error shielding verification")

        from app.api.deps import require_authenticated_user, require_admin, verify_resource_ownership
        from app.schemas.user import UserResponse, UserInDB
        from app.api.deps import get_current_user

        @app.get("/test-protected-user", include_in_schema=False)
        async def test_protected_user(current_user: UserResponse = Depends(require_authenticated_user)):
            return {"status": "authenticated", "user": current_user}

        @app.get("/test-protected-admin", include_in_schema=False)
        async def test_protected_admin(current_user: UserResponse = Depends(require_admin)):
            return {"status": "admin_granted", "user": current_user}

        @app.get("/test-resource-ownership/{owner_id}", include_in_schema=False)
        async def test_resource_ownership(
            owner_id: str,
            current_user: UserInDB = Depends(get_current_user)
        ):
            verify_resource_ownership(owner_id, current_user)
            return {"status": "access_granted", "owner_id": owner_id, "accessor_id": str(current_user.id)}

    return app


app = create_application()

