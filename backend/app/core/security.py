"""
Security and Cryptography Core Functions
Handles Argon2 password hashing, JWT token creation/verification, and service ingest key hashing.
"""
import uuid
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from fastapi import HTTPException, status
from jose import JWTError, jwt, ExpiredSignatureError
from passlib.context import CryptContext

from app.core.config import settings
from app.core.logging import logger

# Password Hashing Setup using Argon2id
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hashes a plaintext password using Argon2id."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plaintext password against an Argon2id hash."""
    return pwd_context.verify(plain_password, hashed_password)


def generate_ingest_key() -> str:
    """Generates a high-entropy secret service ingestion key."""
    return f"pik_live_{secrets.token_hex(24)}"


def hash_ingest_key(ingest_key: str) -> str:
    """Hashes a service ingestion key using SHA-256 for fast, safe DB lookup."""
    clean_key = ingest_key.strip()
    return hashlib.sha256(clean_key.encode("utf-8")).hexdigest()


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Generates a signed JWT Access Token.
    Includes jti, sub, email, role, iat, exp claims. Does NOT include passwords or secrets.
    """
    to_encode = data.copy()
    now = datetime.now(timezone.utc)

    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    if "jti" not in to_encode:
        to_encode["jti"] = str(uuid.uuid4())

    to_encode.update({
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "nbf": int(now.timestamp()),
        "type": "access"
    })

    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decodes and validates a signed JWT Access Token.
    Raises HTTPException 401 if token is expired, tampered, or invalid.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        if payload.get("type") != "access":
            raise credentials_exception
        if not payload.get("sub"):
            raise credentials_exception
        return payload
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError:
        raise credentials_exception

