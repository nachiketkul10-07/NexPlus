"""
Payload Size Limit Middleware
Enforces maximum incoming request body size to protect against memory exhaustion attacks.
"""
from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
from app.core.config import settings
from app.core.errors import create_error_response


class PayloadSizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                length_bytes = int(content_length)
                if length_bytes > settings.MAX_PAYLOAD_SIZE_BYTES:
                    req_id = getattr(request.state, "request_id", None)
                    return create_error_response(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        code="PAYLOAD_TOO_LARGE",
                        message=f"Request payload exceeds maximum allowed size of {settings.MAX_PAYLOAD_SIZE_BYTES} bytes.",
                        request_id=req_id
                    )
            except ValueError:
                pass

        return await call_next(request)

