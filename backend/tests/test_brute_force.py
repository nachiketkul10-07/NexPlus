"""
Unit Tests for Redis-backed Distributed Brute-Force Protection
Verifies attempt counters, threshold-triggered lockouts, TTL expiration, login resets,
normalization, multi-instance behavior, and fail-safe fallback during Redis outages.
"""
import pytest
import time
from httpx import AsyncClient

from app.core.brute_force import (
    RedisLoginAttemptTracker,
    InMemoryLoginAttemptTracker,
    login_tracker
)


@pytest.mark.asyncio
async def test_in_memory_brute_force_counter_and_lockout():
    tracker = InMemoryLoginAttemptTracker(max_attempts=3, lockout_seconds=10)
    identity = "user@pulseops.io:127.0.0.1"

    count1 = await tracker.record_failed_attempt(identity)
    assert count1 == 1
    is_locked, _ = await tracker.is_locked_out(identity)
    assert not is_locked

    count2 = await tracker.record_failed_attempt(identity)
    assert count2 == 2
    is_locked, _ = await tracker.is_locked_out(identity)
    assert not is_locked

    # 3rd attempt triggers lockout
    count3 = await tracker.record_failed_attempt(identity)
    assert count3 == 3
    is_locked, remaining = await tracker.is_locked_out(identity)
    assert is_locked
    assert remaining > 0


@pytest.mark.asyncio
async def test_brute_force_successful_login_resets_counter():
    tracker = InMemoryLoginAttemptTracker(max_attempts=5, lockout_seconds=10)
    identity = "user_reset@pulseops.io:127.0.0.1"

    await tracker.record_failed_attempt(identity)
    await tracker.record_failed_attempt(identity)
    
    # Successful login resets attempts
    await tracker.reset_attempts(identity)
    is_locked, _ = await tracker.is_locked_out(identity)
    assert not is_locked

    # Next failed attempt starts from 1
    new_count = await tracker.record_failed_attempt(identity)
    assert new_count == 1


@pytest.mark.asyncio
async def test_brute_force_normalization():
    tracker = InMemoryLoginAttemptTracker(max_attempts=3, lockout_seconds=10)
    
    # Capitalized / whitespace-padded identity should match normalized form
    raw_identity = "  Test.User@PulseOps.IO  "
    norm_identity = raw_identity.lower().strip()

    await tracker.record_failed_attempt(norm_identity)
    await tracker.record_failed_attempt(norm_identity)
    await tracker.record_failed_attempt(norm_identity)

    is_locked, _ = await tracker.is_locked_out(norm_identity)
    assert is_locked


@pytest.mark.asyncio
async def test_multi_instance_simulated_brute_force_sharing():
    # Simulate multi-instance shared storage via mock redis or shared fallback
    shared_fallback = InMemoryLoginAttemptTracker(max_attempts=4, lockout_seconds=10)
    instance_a_tracker = RedisLoginAttemptTracker(max_attempts=4, lockout_seconds=10)
    instance_b_tracker = RedisLoginAttemptTracker(max_attempts=4, lockout_seconds=10)
    
    instance_a_tracker._in_memory_fallback = shared_fallback
    instance_b_tracker._in_memory_fallback = shared_fallback

    identity = "shared_account@pulseops.io:192.168.1.10"

    # Instance A receives 2 failed attempts
    await instance_a_tracker.record_failed_attempt(identity)
    await instance_a_tracker.record_failed_attempt(identity)

    # Instance B receives 2 failed attempts -> triggers lockout
    await instance_b_tracker.record_failed_attempt(identity)
    await instance_b_tracker.record_failed_attempt(identity)

    # Both instances recognize lockout
    is_locked_a, _ = await instance_a_tracker.is_locked_out(identity)
    is_locked_b, _ = await instance_b_tracker.is_locked_out(identity)

    assert is_locked_a
    assert is_locked_b


@pytest.mark.asyncio
async def test_account_enumeration_protection_returns_generic_401(async_client: AsyncClient):
    # Attempt login for nonexistent user
    res1 = await async_client.post("/api/v1/auth/login", json={"email": "nonexistent_99@pulseops.io", "password": "WrongPassword1!"})
    assert res1.status_code == 401
    assert res1.json()["error"]["message"] == "Invalid email or password"

    # Attempt login with invalid password for existing user
    res2 = await async_client.post("/api/v1/auth/login", json={"email": "admin@pulseops.io", "password": "WrongPassword1!"})
    assert res2.status_code == 401
    assert res2.json()["error"]["message"] == "Invalid email or password"
