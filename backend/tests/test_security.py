"""
Security unit tests for Argon2id hashing, JWT token validation, and information disclosure checks.
"""
from datetime import timedelta
import pytest
from jose import jwt
from app.core.config import settings
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token
)
from fastapi import HTTPException


def test_argon2id_password_hashing():
    raw_password = "ComplexPassword123!"
    hashed = hash_password(raw_password)

    # Stored password must be hashed and NOT equal to plain password
    assert hashed != raw_password
    assert "$argon2id$" in hashed

    # Verification must succeed for correct password and fail for wrong password
    assert verify_password(raw_password, hashed) is True
    assert verify_password("WrongPassword123!", hashed) is False


def test_jwt_token_claims_and_decoding():
    token = create_access_token(
        data={"sub": "user-12345", "email": "test@pulseops.io", "role": "user"},
        expires_delta=timedelta(minutes=15)
    )

    payload = decode_access_token(token)
    assert payload["sub"] == "user-12345"
    assert payload["email"] == "test@pulseops.io"
    assert payload["role"] == "user"
    assert payload["type"] == "access"
    assert "exp" in payload
    assert "iat" in payload


def test_expired_jwt_token_rejected():
    # Create token expired 10 seconds ago
    expired_token = create_access_token(
        data={"sub": "user-12345", "email": "test@pulseops.io", "role": "user"},
        expires_delta=timedelta(seconds=-10)
    )

    with pytest.raises(HTTPException) as exc_info:
        decode_access_token(expired_token)
    assert exc_info.value.status_code == 401
    assert "expired" in exc_info.value.detail.lower()


def test_tampered_jwt_signature_rejected():
    valid_token = create_access_token(data={"sub": "user-12345"})
    tampered_token = valid_token[:-4] + "abcd"

    with pytest.raises(HTTPException) as exc_info:
        decode_access_token(tampered_token)
    assert exc_info.value.status_code == 401


def test_jwt_token_signed_with_wrong_secret_rejected():
    payload = {"sub": "user-12345", "type": "access"}
    wrong_secret_token = jwt.encode(payload, "wrong-secret-key-1234567890", algorithm=settings.JWT_ALGORITHM)

    with pytest.raises(HTTPException) as exc_info:
        decode_access_token(wrong_secret_token)
    assert exc_info.value.status_code == 401
