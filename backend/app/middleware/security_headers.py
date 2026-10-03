"""
Security Headers Middleware
Injects standard HTTP security headers into all outgoing backend responses.
"""
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking in frames
        response.headers["X-Frame-Options"] = "DENY"

        # Referrer privacy control
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # REST API Content Security Policy
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none';"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

        return response
