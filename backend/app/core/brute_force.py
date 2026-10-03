"""
Brute Force Protection Abstraction & Redis-backed Implementation
Provides distributed failed login tracking and lockout across application instances.
Falls back seamlessly to in-memory tracking if Redis is unreachable.
"""
from abc import ABC, abstractmethod
import time
import hashlib
from typing import Dict, Tuple, Optional
from redis.exceptions import RedisError
from fastapi import HTTPException, status

from app.core.config import settings
from app.core.logging import logger
from app.core.redis import get_redis_client


class LoginAttemptTrackerInterface(ABC):
    @abstractmethod
    async def record_failed_attempt(self, identifier: str) -> int:
        """Records failed login attempt. Returns current count."""
        pass

    @abstractmethod
    async def reset_attempts(self, identifier: str) -> None:
        """Resets failed attempt counter on successful login."""
        pass

    @abstractmethod
    async def is_locked_out(self, identifier: str) -> Tuple[bool, int]:
        """Returns tuple (is_locked_out: bool, remaining_lockout_seconds: int)."""
        pass


class InMemoryLoginAttemptTracker(LoginAttemptTrackerInterface):
    """
    In-Memory Brute Force Tracker.
    Locks out identifier after 5 consecutive failed attempts for 15 minutes.
    Used for local testing and as an active fallback during Redis outages.
    """

    def __init__(self, max_attempts: int = 5, lockout_seconds: int = 900):
        self.max_attempts = max_attempts
        self.lockout_seconds = lockout_seconds
        # dict mapping identifier -> {"attempts": int, "locked_until": float}
        self._attempts: Dict[str, Dict[str, float]] = {}

    async def record_failed_attempt(self, identifier: str) -> int:
        now = time.time()
        record = self._attempts.get(identifier, {"attempts": 0, "locked_until": 0.0})

        # Reset count if previous lockout expired
        if record["locked_until"] > 0 and now > record["locked_until"]:
            record["attempts"] = 0
            record["locked_until"] = 0.0

        record["attempts"] += 1

        if record["attempts"] >= self.max_attempts:
            record["locked_until"] = now + self.lockout_seconds
            logger.warning(f"BRUTE-FORCE LOCKOUT (InMemory) | Identifier: {identifier} locked out for {self.lockout_seconds}s")

        self._attempts[identifier] = record
        return int(record["attempts"])

    async def reset_attempts(self, identifier: str) -> None:
        if identifier in self._attempts:
            del self._attempts[identifier]
    def clear(self) -> None:
        self._attempts.clear()

    async def is_locked_out(self, identifier: str) -> Tuple[bool, int]:
        now = time.time()
        record = self._attempts.get(identifier)
        if not record:
            return False, 0

        locked_until = record.get("locked_until", 0.0)
        if locked_until > now:
            remaining = int(locked_until - now)
            return True, remaining

        return False, 0

RECORD_FAILED_ATTEMPT_LUA = """
local count_key = KEYS[1]
local lockout_key = KEYS[2]
local max_attempts = tonumber(ARGV[1])
local window_ttl = tonumber(ARGV[2])
local lockout_ttl = tonumber(ARGV[3])

-- Check if currently locked out
local is_locked = redis.call('EXISTS', lockout_key)
if is_locked == 1 then
    local remaining = redis.call('TTL', lockout_key)
    return {max_attempts, remaining, 1}
end

-- Increment failure count
local count = redis.call('INCR', count_key)
if tonumber(count) == 1 then
    redis.call('EXPIRE', count_key, window_ttl)
end

local remaining_ttl = redis.call('TTL', count_key)

if tonumber(count) >= max_attempts then
    redis.call('SET', lockout_key, '1', 'EX', lockout_ttl)
    redis.call('DEL', count_key)
    return {count, lockout_ttl, 1}
end

return {count, remaining_ttl, 0}
"""


class RedisLoginAttemptTracker(LoginAttemptTrackerInterface):
    """
    Distributed Redis-backed Brute Force Tracker.
    Stores failure counts and lockouts in Redis with TTL.
    Falls back gracefully to in-memory tracking if Redis is unreachable.
    """

    def __init__(self, max_attempts: int = 5, lockout_seconds: int = 900) -> None:
        self.max_attempts = max_attempts
        self.lockout_seconds = lockout_seconds
        self._in_memory_fallback = InMemoryLoginAttemptTracker(max_attempts, lockout_seconds)

    @staticmethod
    def _unavailable(identifier: str, reason: str) -> None:
        key_hash = hashlib.sha256(identifier.lower().strip().encode("utf-8")).hexdigest()[:12]
        logger.error(f"LOGIN_PROTECTION_UNAVAILABLE | IdentifierHash: {key_hash} | Reason: {reason}")
        if settings.is_production:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Login protection temporarily unavailable.")

    @staticmethod
    def _redis_identifier(identifier: str) -> str:
        return hashlib.sha256(identifier.lower().strip().encode("utf-8")).hexdigest()

    async def record_failed_attempt(self, identifier: str) -> int:
        client = get_redis_client()
        if client is None:
            self._unavailable(identifier, "redis client missing")
            return await self._in_memory_fallback.record_failed_attempt(identifier)

        norm_id = identifier.lower().strip()
        redis_id = self._redis_identifier(norm_id)
        count_key = f"brute:count:{redis_id}"
        lockout_key = f"brute:lockout:{redis_id}"

        try:
            result = await client.eval(
                RECORD_FAILED_ATTEMPT_LUA,
                2,
                count_key,
                lockout_key,
                self.max_attempts,
                self.lockout_seconds,
                self.lockout_seconds
            )
            count = int(result[0])
            is_locked = int(result[2]) == 1

            if is_locked:
                key_hash = hashlib.sha256(norm_id.encode("utf-8")).hexdigest()[:12]
                logger.warning(f"LOGIN_LOCKOUT (Redis) | IdentifierHash: {key_hash} locked out for {self.lockout_seconds}s")

            return count
        except Exception as exc:
            self._unavailable(identifier, exc.__class__.__name__)
            return await self._in_memory_fallback.record_failed_attempt(identifier)

    async def reset_attempts(self, identifier: str) -> None:
        client = get_redis_client()
        norm_id = identifier.lower().strip()
        await self._in_memory_fallback.reset_attempts(norm_id)

        if client is None:
            self._unavailable(identifier, "redis client missing")
            return

        redis_id = self._redis_identifier(norm_id)
        count_key = f"brute:count:{redis_id}"
        lockout_key = f"brute:lockout:{redis_id}"
        try:
            await client.delete(count_key, lockout_key)
        except Exception as exc:
            self._unavailable(identifier, exc.__class__.__name__)

    async def is_locked_out(self, identifier: str) -> Tuple[bool, int]:
        client = get_redis_client()
        norm_id = identifier.lower().strip()

        if client is None:
            self._unavailable(identifier, "redis client missing")
            return await self._in_memory_fallback.is_locked_out(norm_id)

        lockout_key = f"brute:lockout:{self._redis_identifier(norm_id)}"
        try:
            ttl = await client.ttl(lockout_key)
            if ttl is not None and ttl > 0:
                key_hash = hashlib.sha256(norm_id.encode("utf-8")).hexdigest()[:12]
                logger.warning(f"LOGIN_ATTEMPT_BLOCKED (Redis) | IdentifierHash: {key_hash} | Remaining TTL: {ttl}s")
                return True, int(ttl)
            return False, 0
        except Exception as exc:
            self._unavailable(identifier, exc.__class__.__name__)
            return await self._in_memory_fallback.is_locked_out(norm_id)
    async def clear(self) -> None:
        self._in_memory_fallback.clear()
        client = get_redis_client()
        if client is not None:
            try:
                keys = await client.keys("brute:*")
                if keys:
                    await client.delete(*keys)
            except Exception:
                pass


# Global Login Attempt Tracker Instance
login_tracker = RedisLoginAttemptTracker()

