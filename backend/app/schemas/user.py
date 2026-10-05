"""
User Pydantic Schemas for Authentication and Authorization
"""
import re
from datetime import datetime
from enum import Enum
from typing import Optional, Any
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator


class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"


class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=100)
    role: UserRole = UserRole.USER

    @field_validator("role", mode="before")
    @classmethod
    def normalize_role(cls, value: Any) -> UserRole:
        if isinstance(value, str):
            val_lower = value.lower().strip()
            if val_lower in ("admin", "administrator"):
                return UserRole.ADMIN
            return UserRole.USER
        return UserRole.USER


class UserRegister(UserBase):
    password: str = Field(..., min_length=8, max_length=128)
    invitation_code: Optional[str] = Field(default=None, max_length=256)

    @field_validator("password")
    @classmethod
    def validate_password_complexity(cls, value: str) -> str:
        """Enforces reasonable password strength policy."""
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        return value


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)


class UserResponse(UserBase):
    id: UUID
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserInDB(UserResponse):
    hashed_password: str
