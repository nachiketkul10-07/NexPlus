"""
JWT Token Schemas for Authentication
"""
from typing import Optional
from pydantic import BaseModel
from app.schemas.user import UserResponse


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class TokenPayload(BaseModel):
    sub: str  # User ID
    email: str
    role: str
    exp: int
    iat: int
    nbf: Optional[int] = None
    type: str = "access"
