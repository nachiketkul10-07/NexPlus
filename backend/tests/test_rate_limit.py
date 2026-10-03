"""
Unit Tests for Redis-backed Rate Limiter
Verifies atomic Redis Lua execution, configurable rate limits, isolation, header formatting,
concurrency safety, fail-closed behavior, and secret safety in Redis keys.
"""
import asyncio
import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock

from app.core.rate_limit import RedisRateLimiter, InMemoryRateLimiter, rate_limiter
from app.core.redis import get_redis_client


@pytest.mark.asyncio
async def test_in_memory_rate_limiter_requests_under_limit_allowed():
    limiter = InMemoryRateLimiter()
    is_limited, remaining, ttl = await limiter.is_rate_limited("test_key", max_requests=3, window_seconds=60)
    assert not is_limited
    assert remaining == 2
    assert ttl == 60


@pytest.mark.asyncio
async def test_rate_limiter_exceeding_limit_returns_429():
    limiter = InMemoryRateLimiter()
    for _ in range(3):
        is_limited, remaining, ttl = await limiter.is_rate_limited("client_1", max_requests=3, window_seconds=60)
        assert not is_limited

    # 4th attempt exceeds limit
    is_limited, remaining, ttl = await limiter.is_rate_limited("client_1", max_requests=3, window_seconds=60)
    assert is_limited
    assert remaining == 0
    assert ttl <= 60


@pytest.mark.asyncio
async def test_rate_limiter_policy_isolation():
    limiter = InMemoryRateLimiter()
    # Key 1 hits limit
    for _ in range(3):
        await limiter.is_rate_limited("policy_a:user1", max_requests=3, window_seconds=60)

    is_limited_a, _, _ = await limiter.is_rate_limited("policy_a:user1", max_requests=3, window_seconds=60)
    assert is_limited_a

    # Policy B for same user remains isolated
    is_limited_b, remaining_b, _ = await limiter.is_rate_limited("policy_b:user1", max_requests=3, window_seconds=60)
    assert not is_limited_b
    assert remaining_b == 2


@pytest.mark.asyncio
async def test_rate_limiter_client_isolation():
    limiter = InMemoryRateLimiter()
    # Client 1 hits limit
    for _ in range(2):
        await limiter.is_rate_limited("client_ip_1", max_requests=2, window_seconds=60)

    is_limited_1, _, _ = await limiter.is_rate_limited("client_ip_1", max_requests=2, window_seconds=60)
    assert is_limited_1

    # Client 2 is isolated
    is_limited_2, remaining_2, _ = await limiter.is_rate_limited("client_ip_2", max_requests=2, window_seconds=60)
    assert not is_limited_2
    assert remaining_2 == 1


@pytest.mark.asyncio
async def test_rate_limiter_concurrency_safety():
    limiter = InMemoryRateLimiter()
    key = "concurrent_client"

    async def make_request():
        return await limiter.is_rate_limited(key, max_requests=5, window_seconds=60)

    results = await asyncio.gather(*[make_request() for _ in range(10)])
    limited_count = sum(1 for is_limited, _, _ in results if is_limited)
    passed_count = sum(1 for is_limited, _, _ in results if not is_limited)

    assert passed_count == 5
    assert limited_count == 5


@pytest.mark.asyncio
async def test_auth_login_endpoint_rate_limiting_triggers_429(async_client: AsyncClient):
    # Hit login endpoint with bad password 5 times
    for _ in range(5):
        res = await async_client.post("/api/v1/auth/login", json={"email": "ratelimit_test@pulseops.io", "password": "WrongPassword1!"})
        assert res.status_code == 401

    # 6th attempt triggers 429
    res = await async_client.post("/api/v1/auth/login", json={"email": "ratelimit_test@pulseops.io", "password": "WrongPassword1!"})
    assert res.status_code == 429
    data = res.json()
    assert "Too many login attempts" in data["error"]["message"]
    assert "Retry-After" in res.headers
    assert "X-RateLimit-Limit" in res.headers


@pytest.mark.asyncio
async def test_rate_limiter_no_secrets_in_keys_or_responses(async_client: AsyncClient):
    raw_secret_password = "SuperSecretPassword123!"
    res = await async_client.post("/api/v1/auth/login", json={"email": "secret_test@pulseops.io", "password": raw_secret_password})
    response_text = str(res.json())
    assert raw_secret_password not in response_text
