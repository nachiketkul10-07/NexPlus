"""
PulseOps Async Redis Connection & Pool Manager
Provides application-level async Redis connection pool lifecycle, ping/health checks,
and credential-masked error logging without business logic dependencies.
"""
from typing import Optional, Tuple, Dict, Any
from urllib.parse import urlparse
import redis.asyncio as redis
from redis.exceptions import RedisError, ConnectionError, TimeoutError

from app.core.config import settings
from app.core.logging import logger


def mask_redis_url(url: str) -> str:
    """
    Masks sensitive password credentials in a Redis URL string for safe logging.
    Example: redis://user:secretpass@localhost:6379/0 -> redis://***:***@localhost:6379/0
    """
    if not url:
        return "[EMPTY_REDIS_URL]"
    try:
        parsed = urlparse(url)
        if parsed.password or parsed.username:
            netloc = parsed.netloc
            if "@" in netloc:
                user_info, host_port = netloc.rsplit("@", 1)
                netloc = f"***:***@{host_port}"
            masked = parsed._replace(netloc=netloc).geturl()
            return masked
        return url
    except Exception:
        return "[MASKED_REDIS_URL]"


class RedisManager:
    """
    Manages asynchronous Redis connection pool and client lifecycle.
    Prevents repeated connection creation per request and safely handles connection dropouts.
    """

    def __init__(self) -> None:
        self._pool: Optional[redis.ConnectionPool] = None
        self._client: Optional[redis.Redis] = None
        self._is_initialized: bool = False

    async def initialize(self) -> None:
        """Initializes connection pool using configuration settings."""
        if self._is_initialized and self._client is not None:
            return

        masked_url = mask_redis_url(settings.REDIS_URL)
        try:
            self._pool = redis.ConnectionPool.from_url(
                settings.REDIS_URL,
                max_connections=settings.REDIS_MAX_CONNECTIONS,
                socket_connect_timeout=settings.REDIS_CONNECT_TIMEOUT,
                socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
                decode_responses=True,
            )
            self._client = redis.Redis(connection_pool=self._pool)
            self._is_initialized = True
            logger.info(f"Redis Connection Pool initialized | Target: {masked_url} | MaxConns: {settings.REDIS_MAX_CONNECTIONS}")
        except Exception as exc:
            logger.error(f"Failed to initialize Redis Connection Pool | Target: {masked_url} | Error: {exc.__class__.__name__}")
            self._client = None
            self._pool = None
            self._is_initialized = False

    def get_client(self) -> Optional[redis.Redis]:
        """Returns the initialized async Redis client instance, or None if uninitialized."""
        if not self._is_initialized or self._client is None:
            return None
        return self._client

    async def ping(self) -> bool:
        """
        Executes a lightweight Redis PING command.
        Returns True if Redis responds with PONG, False otherwise.
        Never throws exceptions to callers and masks log output.
        """
        if not self._is_initialized or self._client is None:
            return False

        masked_url = mask_redis_url(settings.REDIS_URL)
        try:
            pong = await self._client.ping()
            return bool(pong)
        except (ConnectionError, TimeoutError, RedisError, OSError) as exc:
            logger.warning(f"Redis Healthcheck PING Failed | Target: {masked_url} | Reason: {exc.__class__.__name__}")
            return False
        except Exception as exc:
            logger.warning(f"Unexpected Redis Healthcheck PING Error | Reason: {exc.__class__.__name__}")
            return False

    async def is_healthy(self) -> Tuple[bool, str]:
        """
        Checks Redis readiness status.
        Returns tuple: (is_healthy: bool, status_description: str)
        """
        if not self._is_initialized or self._client is None:
            return False, "uninitialized"

        is_alive = await self.ping()
        if is_alive:
            return True, "connected"
        return False, "unavailable"

    async def close(self) -> None:
        """Closes Redis client and connection pool cleanly on application shutdown."""
        masked_url = mask_redis_url(settings.REDIS_URL)
        if self._client is not None:
            try:
                await self._client.aclose()
            except Exception as exc:
                logger.warning(f"Error closing Redis client: {exc.__class__.__name__}")
            self._client = None

        if self._pool is not None:
            try:
                await self._pool.disconnect()
            except Exception as exc:
                logger.warning(f"Error disconnecting Redis pool: {exc.__class__.__name__}")
            self._pool = None

        self._is_initialized = False
        logger.info(f"Redis Connection Pool cleanly closed | Target: {masked_url}")


# Global Singleton Manager Instance
redis_manager = RedisManager()


async def init_redis() -> None:
    """Helper function to initialize global Redis manager."""
    await redis_manager.initialize()


async def close_redis() -> None:
    """Helper function to cleanly shutdown global Redis manager."""
    await redis_manager.close()


def get_redis_client() -> Optional[redis.Redis]:
    """Dependency helper to acquire active Redis client."""
    return redis_manager.get_client()


async def check_redis_health() -> Dict[str, Any]:
    """
    Returns Redis health and readiness details for health check routes without leaking credentials.
    """
    is_healthy, status_str = await redis_manager.is_healthy()
    return {
        "status": status_str,
        "available": is_healthy,
        "max_connections": settings.REDIS_MAX_CONNECTIONS,
    }
