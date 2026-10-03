"""
Health Endpoint for API v1
"""
from datetime import datetime, timezone
from typing import Dict, Any
from fastapi import APIRouter, status
from app.core.config import settings
from app.core.redis import check_redis_health

router = APIRouter()


@router.get("/health", status_code=status.HTTP_200_OK)
async def get_v1_health() -> Dict[str, Any]:
    """Returns application health and dependency readiness status for API v1."""
    redis_health = await check_redis_health()
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dependencies": {
            "database": "connected",
            "redis": redis_health["status"]
        },
        "redis": redis_health
    }

