"""
Global Error Handling Module
Provides consistent JSON error response schemas and FastAPI exception handlers.
"""
from typing import Any, Dict, Optional, List
from fastapi import Request, status, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.core.logging import logger, request_id_ctx


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: Optional[str] = None
    details: Optional[List[Dict[str, Any]]] = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


def create_error_response(
    status_code: int,
    code: str,
    message: str,
    request_id: Optional[str] = None,
    details: Optional[List[Dict[str, Any]]] = None,
    headers: Optional[Dict[str, str]] = None
) -> JSONResponse:
    """Constructs uniform JSON error response."""
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": request_id,
                "details": details
            }
        },
        headers=headers
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handles explicit HTTPExceptions raised by API endpoints."""
    req_id = getattr(request.state, "request_id", request_id_ctx.get())
    code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        413: "PAYLOAD_TOO_LARGE",
        422: "UNPROCESSABLE_ENTITY",
        429: "TOO_MANY_REQUESTS",
        500: "INTERNAL_SERVER_ERROR",
        503: "SERVICE_UNAVAILABLE"
    }
    error_code = code_map.get(exc.status_code, "HTTP_ERROR")
    msg = exc.detail if isinstance(exc.detail, str) else "HTTP Exception occurred"

    return create_error_response(
        status_code=exc.status_code,
        code=error_code,
        message=msg,
        request_id=req_id,
        headers=exc.headers
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handles Pydantic request validation errors."""
    req_id = getattr(request.state, "request_id", request_id_ctx.get())
    formatted_errors = []
    for err in exc.errors():
        formatted_errors.append({
            "field": " -> ".join([str(loc) for loc in err.get("loc", [])]),
            "message": err.get("msg", "Invalid field value"),
            "type": err.get("type", "validation_error")
        })

    return create_error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        code="VALIDATION_ERROR",
        message="Request payload or parameter validation failed",
        request_id=req_id,
        details=formatted_errors
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all exception handler for uncaught server errors.
    Logs exception internally with request_id while shielding internal tracebacks from API consumers.
    """
    req_id = getattr(request.state, "request_id", request_id_ctx.get())
    logger.error(f"Unhandled server exception on path {request.url.path}: {exc}", exc_info=True)

    return create_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="INTERNAL_SERVER_ERROR",
        message="An unexpected server error occurred. Please contact support.",
        request_id=req_id
    )
