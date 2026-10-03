"""
Request ID / Correlation ID Middleware
Assigns or extracts a unique correlation ID for every incoming request.
Catches unhandled exceptions to guarantee error shielding and request ID attachment.
"""
import uuid
import re
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
from app.core.logging import request_id_ctx
from app.core.errors import unhandled_exception_handler

REQUEST_ID_HEADER = "X-Request-ID"
SAFE_UUID_PATTERN = re.compile(r"^[a-zA-Z0-9\-_]{8,64}$")


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        header_val = request.headers.get(REQUEST_ID_HEADER)

        # Validate incoming request ID if provided; otherwise generate new UUIDv4
        if header_val and SAFE_UUID_PATTERN.match(header_val):
            req_id = header_val
        else:
            req_id = str(uuid.uuid4())

        # Bind to request state and context variable for logging
        request.state.request_id = req_id
        token = request_id_ctx.set(req_id)

        try:
            response = await call_next(request)
        except Exception as exc:
            response = await unhandled_exception_handler(request, exc)

        response.headers[REQUEST_ID_HEADER] = req_id
        request_id_ctx.reset(token)
        return response

