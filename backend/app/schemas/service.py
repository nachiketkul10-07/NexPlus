"""
Pydantic Schemas for Services Management
Defines request/response contracts for registering and retrieving monitored services.
"""
from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict
from pydantic import SecretStr, field_validator

from app.services.github_repository import canonicalize_github_url


class ServiceBase(BaseModel):
    identifier: str = Field(..., min_length=2, max_length=80, description="Unique slug for service (e.g. demo-app)")
    name: str = Field(..., min_length=2, max_length=120, description="Display name for service")
    environment: str = Field(default="development", max_length=32, description="Target environment (development, staging, production)")
    base_url: Optional[str] = Field(default=None, max_length=500, description="Base URL of monitored app")
    health_path: str = Field(default="/api/health", max_length=200, description="Relative health check path")
    repository_url: Optional[str] = Field(default=None, max_length=300, description="Linked GitHub repository")

    @field_validator("repository_url")
    @classmethod
    def normalize_repository_url(cls, value: Optional[str]) -> Optional[str]:
        if value is None or not value.strip():
            return None
        return canonicalize_github_url(value)[2]


class GitHubRepositoryPreviewRequest(BaseModel):
    repository_url: str = Field(..., min_length=1, max_length=300)
    access_token: Optional[SecretStr] = Field(default=None, max_length=255, repr=False)


class GitHubRepositoryPreview(BaseModel):
    full_name: str
    repository_url: str
    description: Optional[str] = None
    default_branch: str
    language: Optional[str] = None
    private: bool
    archived: bool
    manifest_files: List[str]


class ServiceCreate(ServiceBase):
    pass


class ServiceCreatedResponse(ServiceBase):
    id: UUID
    status: str
    last_seen_at: Optional[datetime] = None
    ingest_key: str = Field(..., description="Raw service ingestion key. Shown ONLY ONCE upon creation.")
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ServiceResponse(ServiceBase):
    id: UUID
    status: str
    last_seen_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ServiceIngestKeyResponse(BaseModel):
    service_id: UUID
    identifier: str
    ingest_key: str = Field(..., description="Replacement key; shown only once.")
