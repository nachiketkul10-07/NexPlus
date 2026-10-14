"""
Services Management API Endpoints
Provides registration and listing of monitored applications.
"""
from typing import List, Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError

from app.api.deps import require_authenticated_user, require_admin, get_service_repository
from app.db.repositories.service_repository import PostgresServiceRepository
from app.schemas.service import (
    ServiceCreate, ServiceCreatedResponse, ServiceResponse,
    ServiceIngestKeyResponse,
)
from app.schemas.user import UserResponse, UserRole

router = APIRouter()


@router.post("", response_model=ServiceCreatedResponse, status_code=status.HTTP_201_CREATED)
async def register_service(
    service_in: ServiceCreate,
    response: Response,
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

    service, raw_ingest_key = await service_repo.create_service(service_in, current_user.id)
    # Persist the credential hash before returning the only copy of the raw key.
    # This avoids returning a key that another serverless request cannot yet find.
    try:
        await service_repo.session.commit()
    except IntegrityError:
        await service_repo.session.rollback()
        raise HTTPException(status_code=409, detail="That service identifier is already registered.") from None
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Pragma"] = "no-cache"

    return ServiceCreatedResponse(
        id=service.id,
        identifier=service.identifier,
        name=service.name,
        environment=service.environment,
        base_url=service.base_url,
        health_path=service.health_path,
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
    services = await service_repo.list_services_for_user(
        current_user.id,
        is_admin=current_user.role == UserRole.ADMIN,
    )
    return services


@router.get("/{service_id}", response_model=ServiceResponse, status_code=status.HTTP_200_OK)
async def get_service_detail(
    service_id: UUID,
    service_repo: Annotated[PostgresServiceRepository, Depends(get_service_repository)],
    current_user: Annotated[UserResponse, Depends(require_authenticated_user)]
):
    """Retrieves service configuration and current state."""
    service = await service_repo.get_by_id_for_user(
        service_id,
        current_user.id,
        is_admin=current_user.role == UserRole.ADMIN,
    )
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service with ID '{service_id}' not found."
        )
    return service


@router.post("/{service_id}/rotate-ingest-key", response_model=ServiceIngestKeyResponse)
async def rotate_service_ingest_key(
    service_id: UUID,
    response: Response,
    service_repo: Annotated[PostgresServiceRepository, Depends(get_service_repository)],
    current_user: Annotated[UserResponse, Depends(require_admin)],
):
    """Immediately revoke the prior key and return the replacement once (admin only)."""
    service = await service_repo.get_by_id(service_id)
    if service is None:
        raise HTTPException(status_code=404, detail="Service not found.")
    raw_key = await service_repo.rotate_ingest_key(service_id)
    # Revoke the old hash and persist the replacement before exposing the raw key.
    await service_repo.session.commit()
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Pragma"] = "no-cache"
    return ServiceIngestKeyResponse(service_id=service.id, identifier=service.identifier, ingest_key=raw_key)


@router.post("/{service_id}/revoke-ingest-key", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_service_ingest_key(
    service_id: UUID,
    service_repo: Annotated[PostgresServiceRepository, Depends(get_service_repository)],
    current_user: Annotated[UserResponse, Depends(require_admin)],
):
    """Immediately revoke the service's current ingestion key (admin only)."""
    if not await service_repo.revoke_ingest_key(service_id):
        raise HTTPException(status_code=404, detail="Service not found.")
    await service_repo.session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{service_id}/status", response_model=ServiceResponse)
async def set_service_status(
    service_id: UUID,
    is_active: bool,
    service_repo: Annotated[PostgresServiceRepository, Depends(get_service_repository)],
    current_user: Annotated[UserResponse, Depends(require_admin)],
):
    """Activate or deactivate a monitored service (admin only)."""
    service = await service_repo.set_service_active(service_id, is_active)
    if service is None:
        raise HTTPException(status_code=404, detail="Service not found.")
    await service_repo.session.commit()
    await service_repo.session.refresh(service)
    return service


@router.delete("/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_service(
    service_id: UUID,
    service_repo: Annotated[PostgresServiceRepository, Depends(get_service_repository)],
    current_user: Annotated[UserResponse, Depends(require_admin)],
):
    """Permanently remove a service and its telemetry, alerts, and incidents (admin only)."""
    if not await service_repo.delete_service(service_id):
        raise HTTPException(status_code=404, detail="Service not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
