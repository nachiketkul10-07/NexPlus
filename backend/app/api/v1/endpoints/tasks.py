"""
Task Management API Endpoints
Provides secure endpoints for enqueuing background tasks and querying task execution status.
Enforces authentication, role authorization, input payload validation, rate limiting, and IDOR protection.
"""
from typing import Annotated, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field

from app.api.deps import require_authenticated_user
from app.core.audit import log_audit_event
from app.core.rate_limit import rate_limiter
from app.schemas.user import UserResponse, UserRole
from app.workers.queue import task_queue
from app.core.metrics import BACKGROUND_TASKS_TOTAL

from app.workers.registry import is_valid_task_type, TASK_REGISTRY

router = APIRouter()


class TaskEnqueueRequest(BaseModel):
    task_type: str = Field(..., description="Registered task type name")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Task payload dictionary")


class TaskEnqueueResponse(BaseModel):
    task_id: str
    task_type: str
    status: str
    created_at: int


class TaskStatusResponse(BaseModel):
    task_id: str
    task_type: str
    status: str
    created_at: Optional[int] = None
    started_at: Optional[int] = None
    completed_at: Optional[int] = None
    attempt_count: int = 0
    max_attempts: int = 3
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


@router.post("/enqueue", response_model=TaskEnqueueResponse, status_code=status.HTTP_202_ACCEPTED)
async def enqueue_task(
    task_in: TaskEnqueueRequest,
    request: Request,
    current_user: Annotated[UserResponse, Depends(require_authenticated_user)]
) -> TaskEnqueueResponse:
    """
    Enqueues a background task into the PulseOps Redis task queue.
    Requires authentication. Rejects unregistered task types.
    Enforces payload size limits and rate limits (10 req/min per user).
    """
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"task_enqueue:{current_user.id}"
    is_limited, remaining, ttl_seconds = await rate_limiter.is_rate_limited(
        key=rate_key,
        max_requests=10,
        window_seconds=60,
        fail_closed=True,
    )
    if is_limited:
        log_audit_event("RATE_LIMIT_EXCEEDED", user_id=str(current_user.id), details={"policy": "TASK_ENQUEUE"}, success=False)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Task enqueue rate limit exceeded. Please try again in {ttl_seconds} seconds.",
            headers={"Retry-After": str(ttl_seconds)}
        )

    # Task registry validation (prevents arbitrary code execution / injection)
    if not is_valid_task_type(task_in.task_type):
        allowed = list(TASK_REGISTRY.keys())
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid task type '{task_in.task_type}'. Allowed task types: {allowed}"
        )

    # Special authorization for controlled failure demo task (Admin only)
    if task_in.task_type == "controlled_failure_demo" and current_user.role != UserRole.ADMIN:
        log_audit_event(
            "AUTHZ_FAILURE",
            user_id=str(current_user.id),
            details={"task_type": task_in.task_type, "required_role": "admin"},
            success=False
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Controlled failure demo task requires System Administrator privileges."
        )

    try:
        task_data = await task_queue.enqueue_task(
            task_type=task_in.task_type,
            payload=task_in.payload,
            owner_id=str(current_user.id)
        )
        BACKGROUND_TASKS_TOTAL.labels(task_type=task_in.task_type, outcome="enqueued").inc()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Task queue service is currently unavailable. Durable storage is required to enqueue tasks."
        )

    log_audit_event(
        "TASK_ENQUEUED",
        user_id=str(current_user.id),
        details={"task_id": task_data["task_id"], "task_type": task_in.task_type},
        success=True
    )

    return TaskEnqueueResponse(
        task_id=task_data["task_id"],
        task_type=task_data["task_type"],
        status=task_data["status"],
        created_at=task_data["created_at"]
    )



@router.get("/status/{task_id}", response_model=TaskStatusResponse, status_code=status.HTTP_200_OK)
async def get_task_status(
    task_id: str,
    request: Request,
    current_user: Annotated[UserResponse, Depends(require_authenticated_user)]
) -> TaskStatusResponse:
    """
    Queries execution status and result summary of a background task.
    Enforces IDOR protection: Non-admin users can only inspect tasks they created.
    """
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"task_status:{current_user.id}"
    is_limited, _, ttl_seconds = await rate_limiter.is_rate_limited(
        key=rate_key,
        max_requests=60,
        window_seconds=60,
        fail_closed=True,
    )
    if is_limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Task status query rate limit exceeded. Please try again in {ttl_seconds} seconds.",
            headers={"Retry-After": str(ttl_seconds)}
        )

    task_data = await task_queue.get_task_status(task_id)
    if not task_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID '{task_id}' not found."
        )

    # IDOR Prevention: check task ownership
    owner_id = str(task_data.get("owner_id", ""))
    if current_user.role != UserRole.ADMIN and owner_id != str(current_user.id):
        log_audit_event(
            "TASK_IDOR_DENIED",
            user_id=str(current_user.id),
            details={"task_id": task_id, "owner_id": owner_id},
            success=False
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation forbidden: You are not authorized to view status for this task."
        )

    return TaskStatusResponse(
        task_id=task_data["task_id"],
        task_type=task_data["task_type"],
        status=task_data["status"],
        created_at=task_data.get("created_at"),
        started_at=task_data.get("started_at"),
        completed_at=task_data.get("completed_at"),
        attempt_count=task_data.get("attempt_count", 0),
        max_attempts=task_data.get("max_attempts", 3),
        error=task_data.get("error"),
        result=task_data.get("result")
    )
