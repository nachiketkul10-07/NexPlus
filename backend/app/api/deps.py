"""
FastAPI Dependencies for Authentication, Authorization & Telemetry Ingestion
Provides dependencies for token validation, role enforcement, ownership checks, and service ingestion key verification.
"""
from typing import Annotated, Optional, Union
from uuid import UUID
from fastapi import Depends, HTTPException, Header, Cookie, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError

from app.core.security import decode_access_token
from app.core.config import settings
from app.core.token_blacklist import is_token_blacklisted
from app.core.audit import log_audit_event
from app.core.rate_limit import rate_limiter
from app.db.session import get_db
from app.db.repositories.user_repository import PostgresUserRepository, UserRepositoryInterface
from app.db.repositories.service_repository import PostgresServiceRepository
from app.db.repositories.telemetry_repository import PostgresTelemetryRepository
from app.models.service import Service
from app.schemas.user import UserInDB, UserResponse, UserRole
from sqlalchemy.ext.asyncio import AsyncSession

# OAuth2 Bearer token extraction endpoint definition
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_user_repository(
    session: Annotated[AsyncSession, Depends(get_db)]
) -> UserRepositoryInterface:
    """Dependency provider for PostgreSQL user repository bound to request async session."""
    return PostgresUserRepository(session)


async def get_current_user(
    repo: Annotated[UserRepositoryInterface, Depends(get_user_repository)],
    token: Annotated[Optional[str], Depends(oauth2_scheme)] = None,
    session_cookie: Annotated[Optional[str], Cookie(alias=settings.SESSION_COOKIE_NAME)] = None,
) -> UserInDB:
    """
    Validates Bearer access token and returns corresponding database user.
    Raises HTTP 401 Unauthorized if token is missing, invalid, expired, or revoked.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        token = token or session_cookie
        if not token:
            raise credentials_exception
        payload = decode_access_token(token)
        user_id: str = payload.get("sub")
        jti: Optional[str] = payload.get("jti")
        if user_id is None:
            log_audit_event("AUTH_FAILED", details={"reason": "missing_sub_claim"}, success=False)
            raise credentials_exception

        if jti and await is_token_blacklisted(jti):
            log_audit_event("AUTH_FAILED", user_id=user_id, details={"reason": "token_revoked"}, success=False)
            raise credentials_exception

    except HTTPException:
        log_audit_event("AUTH_FAILED", details={"reason": "invalid_or_expired_token"}, success=False)
        raise

    user = await repo.get_by_id(user_id)
    if user is None or not user.is_active:
        log_audit_event("AUTH_FAILED", user_id=user_id, details={"reason": "user_not_found_or_inactive"}, success=False)
        raise credentials_exception

    return user


async def require_authenticated_user(
    current_user: Annotated[UserInDB, Depends(get_current_user)]
) -> UserResponse:
    """Dependency for routes requiring any authenticated user."""
    return UserResponse.model_validate(current_user)


async def require_admin(
    current_user: Annotated[UserInDB, Depends(get_current_user)]
) -> UserResponse:
    """
    Dependency for routes requiring System Administrator role.
    Raises HTTP 403 Forbidden if current user is not an admin.
    """
    if current_user.role != UserRole.ADMIN:
        log_audit_event(
            "AUTHZ_FAILURE",
            user_id=str(current_user.id),
            email=current_user.email,
            details={"required_role": "admin", "actual_role": current_user.role},
            success=False
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation forbidden: Administrator privileges required."
        )
    return UserResponse.model_validate(current_user)


def verify_resource_ownership(resource_owner_id: str, current_user: UserInDB) -> bool:
    """
    Helper function verifying that current user is either the owner of a resource or an admin.
    Raises HTTP 403 Forbidden if authorization fails.
    """
    if str(current_user.id) == str(resource_owner_id) or current_user.role == UserRole.ADMIN:
        return True

    log_audit_event(
        "AUTHZ_FAILURE",
        user_id=str(current_user.id),
        email=current_user.email,
        details={"resource_owner_id": resource_owner_id, "action": "resource_access_denied"},
        success=False
    )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Operation forbidden: You do not have permission to access or modify this resource."
    )


async def get_service_repository(
    session: Annotated[AsyncSession, Depends(get_db)]
) -> PostgresServiceRepository:
    """Dependency provider for PostgreSQL service repository bound to request async session."""
    return PostgresServiceRepository(session)


async def get_telemetry_repository(
    session: Annotated[AsyncSession, Depends(get_db)]
) -> PostgresTelemetryRepository:
    """Dependency provider for PostgreSQL telemetry repository bound to request async session."""
    return PostgresTelemetryRepository(session)

from app.db.repositories.alert_repository import PostgresAlertRepository


async def get_alert_repository(
    session: Annotated[AsyncSession, Depends(get_db)]
) -> PostgresAlertRepository:
    """Dependency provider for PostgreSQL alert repository bound to request async session."""
    return PostgresAlertRepository(session)


from app.db.repositories.incident_repository import PostgresIncidentRepository


async def get_incident_repository(
    session: Annotated[AsyncSession, Depends(get_db)]
) -> PostgresIncidentRepository:
    """Dependency provider for PostgreSQL incident repository bound to request async session."""
    return PostgresIncidentRepository(session)


async def get_authenticated_service(
    service_repo: Annotated[PostgresServiceRepository, Depends(get_service_repository)],
    x_ingest_key: Optional[str] = Header(None, alias="X-Ingest-Key"),
    x_service_key: Optional[str] = Header(None, alias="X-Service-Key"),
    authorization: Optional[str] = Header(None)
) -> Service:
    """
    Authenticates a telemetry ingestion request using service-specific ingest credential.
    Checks X-Ingest-Key, X-Service-Key, or Bearer Authorization headers.
    """
    raw_key = None
    if x_ingest_key:
        raw_key = x_ingest_key
    elif x_service_key:
        raw_key = x_service_key
    elif authorization and authorization.startswith("Bearer "):
        raw_key = authorization.replace("Bearer ", "").strip()

    if not raw_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing service ingestion credential (X-Ingest-Key, X-Service-Key, or Bearer token required)"
        )

    service = await service_repo.get_by_ingest_key(raw_key)
    if not service:
        log_audit_event("INGEST_AUTH_FAILED", details={"reason": "invalid_ingest_key"}, success=False)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid service ingestion key"
        )

    limited, _, retry_after = await rate_limiter.is_rate_limited(
        key=f"telemetry_ingest:{service.id}",
        max_requests=settings.RATE_LIMIT_TELEMETRY_PER_MINUTE,
        window_seconds=60,
        fail_closed=True,
    )
    if limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Telemetry ingestion rate limit exceeded.",
            headers={"Retry-After": str(retry_after)},
        )

    return service


def verify_service_ownership(
    authenticated_service: Service,
    requested_service_id: Optional[Union[UUID, str]]
) -> None:
    """
    Verifies server-side that the authenticated service credential matches any requested service target.
    Prevents cross-service telemetry data injection.
    """
    if requested_service_id is None:
        return

    req_str = str(requested_service_id).strip()
    auth_id_str = str(authenticated_service.id).strip()
    auth_identifier = str(authenticated_service.identifier).strip()

    if req_str != auth_id_str and req_str != auth_identifier:
        log_audit_event(
            "CROSS_SERVICE_INGEST_DENIED",
            details={
                "authenticated_service_id": auth_id_str,
                "requested_service_id": req_str
            },
            success=False
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Service ingestion key is not authorized for the specified target service"
        )
