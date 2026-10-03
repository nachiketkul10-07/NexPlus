"""Reject cross-origin state changes authenticated by the browser session cookie."""
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from app.core.config import settings


class CookieCSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        unsafe_method = request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}
        has_session_cookie = settings.SESSION_COOKIE_NAME in request.cookies
        if unsafe_method and has_session_cookie:
            origin = request.headers.get("origin")
            if not origin or origin not in settings.cors_origins_list:
                return JSONResponse(
                    status_code=403,
                    content={"error": {"code": "CSRF_ORIGIN_REJECTED", "message": "Request origin is not allowed."}},
                )
        return await call_next(request)
