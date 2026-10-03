"""
Services Management API Endpoints
Provides registration and listing of monitored applications.
"""
from typing import List, Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import require_authenticated_user, get_service_repository
from app.db.repositories.service_repository import PostgresServiceRepository
from app.schemas.service import (
    ServiceCreate, ServiceCreatedResponse, ServiceResponse,
    GitHubRepositoryPreview, GitHubRepositoryPreviewRequest,
)
from app.schemas.user import UserResponse
from app.core.rate_limit import rate_limiter
from app.services.github_repository import GitHubRepositoryError, fetch_repository_preview

router = APIRouter()


@router.post("/github/preview", response_model=GitHubRepositoryPreview)
async def preview_github_repository(
    payload: GitHubRepositoryPreviewRequest,
    current_user: Annotated[UserResponse, Depends(require_authenticated_user)],
):
    """Fetch public repository metadata or use a one-time read-only token for a private repo."""
    limited, _, retry_after = await rate_limiter.is_rate_limited(
        key=f"github_preview:{current_user.id}", max_requests=10, window_seconds=60, fail_closed=True
    )
    if limited:
        raise HTTPException(status_code=429, detail="Repository preview rate limit exceeded.", headers={"Retry-After": str(retry_after)})
    access_token = payload.access_token.get_secret_value().strip() if payload.access_token else None
    try:
        return await fetch_repository_preview(payload.repository_url, access_token)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except GitHubRepositoryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from None


@router.post("", response_model=ServiceCreatedResponse, status_code=status.HTTP_201_CREATED)
async def register_service(
    service_in: ServiceCreate,
    service_repo: Annotated[PostgresServiceRepository, Depends(get_service_repository)],
    current_user: Annotated[UserResponse, Depends(require_authenticated_user)]
):
    """
    Registers a new monitored service and returns its ingestion key ONCE.
    Requires an authenticated user session.
    """
    existing = await service_repo.get_by_identifier(service_in.identifier)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Service identifier '{service_in.identifier}' is already registered."
        )

    service, raw_ingest_key = await service_repo.create_service(service_in)

    return ServiceCreatedResponse(
        id=service.id,
        identifier=service.identifier,
        name=service.name,
        environment=service.environment,
        base_url=service.base_url,
        health_path=service.health_path,
        repository_url=service.repository_url,
        status=service.status,
        last_seen_at=service.last_seen_at,
        ingest_key=raw_ingest_key,
        created_at=service.created_at,
        updated_at=service.updated_at
    )


@router.get("", response_model=List[ServiceResponse], status_code=status.HTTP_200_OK)
async def list_services(
    service_repo: Annotated[PostgresServiceRepository, Depends(get_service_repository)],
    current_user: Annotated[UserResponse, Depends(require_authenticated_user)]
):
    """Lists all registered monitored services."""
    services = await service_repo.list_services()
    return services


@router.get("/{service_id}", response_model=ServiceResponse, status_code=status.HTTP_200_OK)
async def get_service_detail(
    service_id: UUID,
    service_repo: Annotated[PostgresServiceRepository, Depends(get_service_repository)],
    current_user: Annotated[UserResponse, Depends(require_authenticated_user)]
):
    """Retrieves service configuration and current state."""
    service = await service_repo.get_by_id(service_id)
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service with ID '{service_id}' not found."
        )
    return service
