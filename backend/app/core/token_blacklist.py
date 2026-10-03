"""
JWT Token Blacklist & Revocation Core Module
Manages revoked JWT tokens in Redis using token unique identifiers (JTI).
Does NOT store raw JWTs, passwords, or sensitive payloads in Redis keys.
TTLs are set strictly to remaining token expiration lifetime.
"""
from typing import Optional
from redis.exceptions import RedisError
from fastapi import HTTPException, status

from app.core.config import settings
from app.core.logging import logger
from app.core.redis import get_redis_client

# Memory fallback for unit tests or offline fallback when Redis is absent
_in_memory_blacklist = set()


async def blacklist_token(jti: str, ttl_seconds: int) -> bool:
    """
    Blacklists a token JTI for the remaining duration of its lifetime.
    If ttl_seconds <= 0, the token is already expired and no entry is created.
    """
    if not jti or ttl_seconds <= 0:
        return False

    client = get_redis_client()
    redis_key = f"jwt:blacklist:{jti}"

    if client is not None:
        try:
            await client.setex(redis_key, ttl_seconds, "revoked")
            logger.info(f"JWT Token Revoked | JTI: {jti} | TTL: {ttl_seconds}s")
            return True
        except Exception as exc:
            logger.error(f"Redis Token Blacklist Error | Reason: {exc.__class__.__name__}")

    if settings.is_production:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Session revocation temporarily unavailable.")

    # Fallback to local memory set if Redis is offline
    _in_memory_blacklist.add(jti)
    return True


async def is_token_blacklisted(jti: str) -> bool:
    """
    Checks if a token JTI has been revoked.
    Returns True if blacklisted, False otherwise.
    """
    if not jti:
        return False

    client = get_redis_client()
    redis_key = f"jwt:blacklist:{jti}"

    if client is not None:
        try:
            exists = await client.exists(redis_key)
            return bool(exists)
        except Exception as exc:
            logger.error(f"Redis Blacklist Check Error | Reason: {exc.__class__.__name__}")
            if settings.is_production:
                raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Session verification temporarily unavailable.")
            # Fallback to checking local memory fallback
            return jti in _in_memory_blacklist

    if settings.is_production:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Session verification temporarily unavailable.")
    return jti in _in_memory_blacklist


async def clear_blacklist() -> None:
    """Clears the token blacklist (used for test setup/teardown)."""
    _in_memory_blacklist.clear()
    client = get_redis_client()
    if client is not None:
        try:
            keys = await client.keys("jwt:blacklist:*")
            if keys:
                await client.delete(*keys)
        except Exception:
            pass
