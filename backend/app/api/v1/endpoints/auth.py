"""
Authentication API Endpoints for PulseOps
Includes user registration, login, logout, and current user identity (/me).
"""
import time
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from app.api.deps import get_user_repository, require_authenticated_user
from app.core.config import settings
from app.core.security import verify_password, create_access_token, decode_access_token
from app.core.token_blacklist import blacklist_token
from app.core.audit import log_audit_event
from app.core.brute_force import login_tracker
from app.core.rate_limit import rate_limiter
from app.db.repositories.user_repository import UserRepositoryInterface
from app.schemas.user import UserRegister, UserLogin, UserResponse, UserRole
from app.schemas.token import Token

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_in: UserRegister,
    request: Request,
    repo: Annotated[UserRepositoryInterface, Depends(get_user_repository)]
) -> UserResponse:
    """
    Registers a new user account.
    Hashes password with Argon2id. Never returns password or password hash.
    SECURITY CONTROL: Public registration forces role to UserRole.USER regardless
    of client input. Public callers cannot assign themselves the admin role.
    Rate limited with fail-closed security control.
    """
    if settings.is_production and not settings.ALLOW_PUBLIC_REGISTRATION:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Public registration is disabled.")

    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"auth_register:{client_ip}"
    is_limited, remaining, ttl_seconds = await rate_limiter.is_rate_limited(
        key=rate_key,
        max_requests=5,
        window_seconds=300,
        fail_closed=True
    )
    if is_limited:
        log_audit_event("RATE_LIMIT_EXCEEDED", details={"policy": "AUTH_REGISTER", "client_ip": client_ip}, success=False)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Registration rate limit exceeded. Please try again in {ttl_seconds} seconds.",
            headers={
                "Retry-After": str(ttl_seconds),
                "X-RateLimit-Limit": "5",
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(ttl_seconds)
            }
        )

    existing_user = await repo.get_by_email(user_in.email)
    if existing_user:
        log_audit_event("USER_REGISTERED", email=user_in.email, details={"reason": "email_already_exists"}, success=False)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists."
        )

    # Force standard user role for public registration
    user_in.role = UserRole.USER

    try:
        db_user = await repo.create_user(user_in)
    except ValueError as e:
        log_audit_event("USER_REGISTERED", email=user_in.email, details={"reason": str(e)}, success=False)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    log_audit_event("USER_REGISTERED", user_id=str(db_user.id), email=db_user.email, success=True)
    return UserResponse.model_validate(db_user)


@router.post("/login", response_model=Token, status_code=status.HTTP_200_OK)
async def login_user(
    credentials: UserLogin,
    request: Request,
    repo: Annotated[UserRepositoryInterface, Depends(get_user_repository)]
) -> Token:
    """
    Authenticates user credentials and issues a signed JWT access token.
    Uses safe error messages ("Invalid email or password") to prevent email enumeration.
    Supports atomic Redis-backed rate limiting (fail-closed) and distributed brute force tracking.
    """
    client_ip = request.client.host if request.client else "unknown"
    norm_email = credentials.email.lower().strip()
    rate_key = f"auth_login:{norm_email}:{client_ip}"

    # 1. Rate Limiting Check (Fail-Closed)
    is_limited, remaining, ttl_seconds = await rate_limiter.is_rate_limited(
        key=rate_key,
        max_requests=settings.RATE_LIMIT_LOGIN_PER_MINUTE,
        window_seconds=60,
        fail_closed=True
    )
    if is_limited:
        log_audit_event("RATE_LIMIT_EXCEEDED", details={"policy": "AUTH_LOGIN", "client_ip": client_ip}, success=False)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many login attempts. Please try again in {ttl_seconds} seconds.",
            headers={
                "Retry-After": str(ttl_seconds),
                "X-RateLimit-Limit": str(settings.RATE_LIMIT_LOGIN_PER_MINUTE),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(ttl_seconds)
            }
        )

    track_id = f"{norm_email}:{client_ip}"

    # 2. Check distributed brute-force lockout status
    is_locked, remaining_secs = await login_tracker.is_locked_out(track_id)
    if is_locked:
        log_audit_event(
            "LOGIN_ATTEMPT_BLOCKED",
            email=norm_email,
            details={"reason": "locked_out", "remaining_seconds": remaining_secs},
            success=False
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Account temporarily locked due to failed attempts. Try again in {remaining_secs} seconds.",
            headers={"Retry-After": str(remaining_secs)}
        )

    user = await repo.get_by_email(credentials.email)
    if not user or not verify_password(credentials.password, user.hashed_password):
        await login_tracker.record_failed_attempt(track_id)
        log_audit_event("LOGIN_FAILED", email=norm_email, details={"reason": "invalid_credentials"}, success=False)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        log_audit_event("LOGIN_FAILED", user_id=str(user.id), email=user.email, details={"reason": "account_inactive"}, success=False)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account is inactive."
        )

    # 3. Successful login: reset failed attempts counter
    await login_tracker.reset_attempts(track_id)
    log_audit_event("LOGIN_SUCCESS", user_id=str(user.id), email=user.email, success=True)

    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value if hasattr(user.role, "value") else str(user.role)
        }
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user)
    )


@router.post("/session", status_code=status.HTTP_200_OK)
async def create_browser_session(
    credentials: UserLogin,
    request: Request,
    response: Response,
    repo: Annotated[UserRepositoryInterface, Depends(get_user_repository)],
):
    """Starts a browser session without exposing its bearer token to JavaScript."""
    token = await login_user(credentials, request, repo)
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=token.access_token,
        max_age=token.expires_in,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite="strict",
        path="/",
    )
    return {"user": token.user}


@router.post("/session/logout", status_code=status.HTTP_200_OK)
async def destroy_browser_session(request: Request, response: Response):
    """Revokes a browser session token and clears its cookie."""
    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        path="/",
        secure=settings.SESSION_COOKIE_SECURE,
        httponly=True,
        samesite="strict",
    )
    token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if token:
        try:
            payload = decode_access_token(token)
        except HTTPException:
            payload = None
        if payload:
            jti = payload.get("jti")
            exp = payload.get("exp")
            if jti and exp:
                try:
                    await blacklist_token(jti, max(0, int(exp) - int(time.time())))
                except HTTPException as exc:
                    response.status_code = exc.status_code
                    return {"detail": exc.detail}
    return {"message": "Successfully logged out."}


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout_user(
    request: Request,
    current_user: Annotated[UserResponse, Depends(require_authenticated_user)]
):
    """Revokes the current bearer token by JTI in Redis."""
    auth_header = request.headers.get("Authorization", "")
    token = auth_header[7:].strip() if auth_header.startswith("Bearer ") else None

    if token:
        try:
            payload = decode_access_token(token)
        except HTTPException:
            payload = None
        if payload:
            jti = payload.get("jti")
            exp = payload.get("exp")
            if jti and exp:
                await blacklist_token(jti, max(0, int(exp) - int(time.time())))

    log_audit_event("LOGOUT", user_id=str(current_user.id), email=current_user.email, success=True)
    return {"message": "Successfully logged out."}


@router.get("/me", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def get_me(current_user: Annotated[UserResponse, Depends(require_authenticated_user)]) -> UserResponse:
    """Returns profile and role identity for the currently authenticated user."""
    return current_user
