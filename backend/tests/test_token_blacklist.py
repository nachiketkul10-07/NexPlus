"""
Unit and Integration Tests for JWT Token Blacklist & Revocation
Tests JTI claim generation, token revocation, blacklist TTL, logout idempotency, and 401 error handling.
"""
import pytest
from datetime import timedelta
from fastapi import status

from app.core.security import create_access_token, decode_access_token
from app.core.token_blacklist import blacklist_token, is_token_blacklisted, clear_blacklist


async def get_auth_headers(client, email: str = "user@pulseops.io", password: str = "UserPass123!"):
    res = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == status.HTTP_200_OK
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_jwt_access_token_includes_unique_jti():
    """Verify that every created access token contains a unique JTI claim."""
    token1 = create_access_token(data={"sub": "user-100", "role": "user"})
    token2 = create_access_token(data={"sub": "user-100", "role": "user"})

    payload1 = decode_access_token(token1)
    payload2 = decode_access_token(token2)

    assert "jti" in payload1
    assert "jti" in payload2
    assert payload1["jti"] != payload2["jti"]


@pytest.mark.asyncio
async def test_blacklist_token_revocation():
    """Verify revoking a token by JTI blocks validation."""
    await clear_blacklist()
    token = create_access_token(data={"sub": "user-200", "role": "user"})
    payload = decode_access_token(token)
    jti = payload["jti"]

    # Initially not blacklisted
    assert await is_token_blacklisted(jti) is False

    # Blacklist token with 60s TTL
    success = await blacklist_token(jti, ttl_seconds=60)
    assert success is True

    # Now blacklisted
    assert await is_token_blacklisted(jti) is True


@pytest.mark.asyncio
async def test_expired_token_blacklist_ttl_skips_negative_ttl():
    """Verify already expired tokens (ttl <= 0) do not create permanent blacklist entries."""
    await clear_blacklist()
    jti = "expired-jti-123"

    success = await blacklist_token(jti, ttl_seconds=-10)
    assert success is False
    assert await is_token_blacklisted(jti) is False


@pytest.mark.asyncio
async def test_logout_endpoint_revokes_token_idempotently(async_client):
    """Verify POST /api/v1/auth/logout revokes current token and behaves idempotently on repeat."""
    await clear_blacklist()
    headers = await get_auth_headers(async_client, "user@pulseops.io", "UserPass123!")

    # Initial me request succeeds
    res_me1 = await async_client.get("/api/v1/auth/me", headers=headers)
    assert res_me1.status_code == status.HTTP_200_OK

    # Logout
    res_logout1 = await async_client.post("/api/v1/auth/logout", headers=headers)
    assert res_logout1.status_code == status.HTTP_200_OK
    assert res_logout1.json()["message"] == "Successfully logged out."

    # Subsequent request using the same token MUST be rejected with HTTP 401
    res_me2 = await async_client.get("/api/v1/auth/me", headers=headers)
    assert res_me2.status_code == status.HTTP_401_UNAUTHORIZED

    # Repeat logout with the same token is safe (returns safe 401 or safe idempotent outcome)
    res_logout2 = await async_client.post("/api/v1/auth/logout", headers=headers)
    assert res_logout2.status_code == status.HTTP_401_UNAUTHORIZED

