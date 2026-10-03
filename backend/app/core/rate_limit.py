"""
Rate Limiter Abstraction & Redis-backed Implementation
Provides server-side atomic rate limiting using Redis Lua scripts.
Supports configurable policy rates, atomic INCR+EXPIRE execution, rate-limit response headers,
fail-closed security behavior, and in-memory fallback during Redis outages.
"""
from abc import ABC, abstractmethod
import time
from typing import Tuple, Optional, Dict, List
from redis.exceptions import RedisError
from fastapi import HTTPException, status
import hashlib

from app.core.config import settings
from app.core.logging import logger
from app.core.redis import get_redis_client


RATE_LIMIT_LUA_SCRIPT = """
local current = redis.call('INCR', KEYS[1])
if tonumber(current) == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
local ttl = redis.call('TTL', KEYS[1])
return {current, ttl}
"""


class RateLimiterInterface(ABC):
    """Abstract interface for server-side rate limiting."""

    @abstractmethod
    async def is_rate_limited(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
        fail_closed: bool = False
    ) -> Tuple[bool, int, int]:
        """
        Check if key exceeds rate limit.
        Returns tuple: (is_limited: bool, remaining_requests: int, reset_ttl_seconds: int)
        """
        pass


class NoOpRateLimiter(RateLimiterInterface):
    """Placeholder rate limiter that permits all requests."""

    async def is_rate_limited(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
        fail_closed: bool = False
    ) -> Tuple[bool, int, int]:
        return False, max_requests, 0


class InMemoryRateLimiter(RateLimiterInterface):
    """
    In-memory fallback rate limiter using sliding timestamp window.
    Ensures rate limiting remains active even during Redis connection outages.
    """

    def __init__(self) -> None:
        self._history: Dict[str, List[float]] = {}

    async def is_rate_limited(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
        fail_closed: bool = False
    ) -> Tuple[bool, int, int]:
        now = time.time()
        timestamps = [t for t in self._history.get(key, []) if t > (now - window_seconds)]
        
        if len(timestamps) >= max_requests:
            oldest = timestamps[0]
            ttl = max(1, int(window_seconds - (now - oldest)))
            self._history[key] = timestamps
            return True, 0, ttl

        timestamps.append(now)
        self._history[key] = timestamps
        remaining = max(0, max_requests - len(timestamps))
        return False, remaining, window_seconds
    def clear(self) -> None:
        self._history.clear()


class RedisRateLimiter(RateLimiterInterface):
    """
    Atomic Redis-backed Rate Limiter using Lua scripts.
    Guarantees atomic counter increment and TTL expiration setting.
    Falls back gracefully to in-memory rate limiting when Redis is unavailable.
    """

    def __init__(self) -> None:
        self._fallback_limiter = InMemoryRateLimiter()

    async def is_rate_limited(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
        fail_closed: bool = False
    ) -> Tuple[bool, int, int]:
        client = get_redis_client()

        def unavailable(reason: str) -> Tuple[bool, int, int]:
            safe_key = hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
            logger.error(f"RATE_LIMITER_UNAVAILABLE | KeyHash: {safe_key} | Reason: {reason}")
            if settings.is_production and fail_closed:
                raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Security service temporarily unavailable.")
            return (False, max_requests, 0) if settings.is_production else (False, max_requests, 0)

        if client is None:
            if settings.is_production and fail_closed:
                return unavailable("redis client missing")
            logger.warning("RATE_LIMITER_REDIS_UNAVAILABLE | Using local development fallback")
            return await self._fallback_limiter.is_rate_limited(key, max_requests, window_seconds, fail_closed)

        redis_key = f"rate_limit:{hashlib.sha256(key.encode('utf-8')).hexdigest()}"
        try:
            # Execute atomic Lua script
            result = await client.eval(RATE_LIMIT_LUA_SCRIPT, 1, redis_key, window_seconds)
            current_count = int(result[0])
            ttl_seconds = max(0, int(result[1]))

            remaining = max(0, max_requests - current_count)
            is_limited = current_count > max_requests

            if is_limited:
                logger.warning(f"RATE_LIMIT_EXCEEDED | Key: {key} | Count: {current_count}/{max_requests} | TTL: {ttl_seconds}s")

            return is_limited, remaining, ttl_seconds
        except Exception as exc:
            if settings.is_production and fail_closed:
                return unavailable(exc.__class__.__name__)
            logger.error(f"Redis Rate Limiter Error | Reason: {exc.__class__.__name__} | Using local development fallback")
            return await self._fallback_limiter.is_rate_limited(key, max_requests, window_seconds, fail_closed)
    async def clear(self) -> None:
        self._fallback_limiter.clear()
        client = get_redis_client()
        if client is not None:
            try:
                keys = await client.keys("rate_limit:*")
                if keys:
                    await client.delete(*keys)
            except Exception:
                pass


# Global Rate Limiter Instance
rate_limiter = RedisRateLimiter()


