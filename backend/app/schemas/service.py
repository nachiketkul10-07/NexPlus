"""
Pydantic Schemas for Services Management
Defines request/response contracts for registering and retrieving monitored services.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict
from pydantic import field_validator


class ServiceBase(BaseModel):
    identifier: str = Field(..., min_length=2, max_length=80, pattern=r"^[a-z0-9][a-z0-9._-]*$", description="Unique stable slug for service (e.g. demo-app)")
    name: str = Field(..., min_length=2, max_length=120, description="Display name for service")
    description: Optional[str] = Field(default=None, max_length=2000)
    framework: Optional[str] = Field(default=None, max_length=80)
    language: Optional[str] = Field(default=None, max_length=40)
    environment: str = Field(default="development", max_length=32, description="Target environment (development, staging, production)")
    base_url: Optional[str] = Field(default=None, max_length=500, description="Base URL of monitored app")
    health_path: str = Field(default="/api/health", max_length=200, description="Relative health check path")

    @field_validator("identifier", mode="before")
    @classmethod
    def normalize_identifier(cls, value: str) -> str:
        return value.strip().lower()


class ServiceCreate(ServiceBase):
    pass


class ServiceCreatedResponse(ServiceBase):
    id: UUID
    status: str
    is_active: bool = True
    last_seen_at: Optional[datetime] = None
    ingest_key: str = Field(..., description="Raw service ingestion key. Shown ONLY ONCE upon creation.")
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ServiceResponse(ServiceBase):
    id: UUID
    status: str
    is_active: bool = True
    last_seen_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ServiceIngestKeyResponse(BaseModel):
    service_id: UUID
    identifier: str
    ingest_key: str = Field(..., description="Replacement key; shown only once.")
