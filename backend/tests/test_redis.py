"""
Tests for Async Redis Connection Manager & Readiness Endpoint
Validates configuration loading, connection pool lifecycle, resilience to Redis offline state,
credential masking, and health check readiness reporting.
"""
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport

from app.core.config import settings
from app.core.redis import (
    RedisManager,
    mask_redis_url,
    init_redis,
    close_redis,
    get_redis_client,
    check_redis_health,
)
from app.main import app


@pytest.mark.asyncio
async def test_redis_configuration_defaults():
    """Validates Redis settings defaults load correctly from core config."""
    assert settings.REDIS_URL is not None
    assert settings.REDIS_MAX_CONNECTIONS == 10
    assert settings.REDIS_CONNECT_TIMEOUT == 0.5
    assert settings.REDIS_SOCKET_TIMEOUT == 0.5


def test_mask_redis_url_masks_credentials():
    """Validates that sensitive passwords and user info in Redis URLs are masked."""
    secret_url = "redis://admin:super_secret_password_123@redis.prod.internal:6379/0"
    masked = mask_redis_url(secret_url)

    assert "super_secret_password_123" not in masked
    assert "admin" not in masked
    assert "redis://***:***@redis.prod.internal:6379/0" == masked

    # Standard URL without password remains unchanged
    standard_url = "redis://localhost:6379/0"
    assert mask_redis_url(standard_url) == "redis://localhost:6379/0"


@pytest.mark.asyncio
async def test_redis_manager_lifecycle_and_reuse():
    """Validates initialization, client reuse, and clean shutdown of RedisManager."""
    manager = RedisManager()
    await manager.initialize()

    client1 = manager.get_client()
    client2 = manager.get_client()

    # Connection client must be reused, not recreated
    assert client1 is client2

    # Clean shutdown
    await manager.close()
    assert manager.get_client() is None


@pytest.mark.asyncio
async def test_redis_manager_ping_and_mocked_success():
    """Validates ping behavior when Redis is responsive."""
    manager = RedisManager()
    await manager.initialize()

    with patch.object(manager._client, "ping", new=AsyncMock(return_value=True)):
        is_healthy, status_str = await manager.is_healthy()
        assert is_healthy is True
        assert status_str == "connected"

    await manager.close()


@pytest.mark.asyncio
async def test_redis_manager_safe_failure_handling():
    """Validates that ConnectionError or unavailability does not crash application."""
    manager = RedisManager()
    await manager.initialize()

    with patch.object(manager._client, "ping", side_effect=ConnectionError("Connection refused")):
        is_healthy, status_str = await manager.is_healthy()
        assert is_healthy is False
        assert status_str == "unavailable"

    await manager.close()


@pytest.mark.asyncio
async def test_check_redis_health_response_structure():
    """Validates health detail dictionary structure and safe reporting."""
    health_info = await check_redis_health()
    assert "status" in health_info
    assert "available" in health_info
    assert "max_connections" in health_info
    # Verification that secret keys or passwords are not in health response
    assert "password" not in health_info
    assert "url" not in health_info


@pytest.mark.asyncio
async def test_v1_health_endpoint_includes_redis_readiness():
    """Validates that GET /api/v1/health returns status healthy and includes redis readiness status."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "dependencies" in data
        assert "redis" in data["dependencies"]
        assert data["dependencies"]["redis"] in ["connected", "unavailable", "uninitialized"]
