"""
PulseOps Prometheus HTTP Request Metrics Middleware
Captures HTTP request rates, active request gauges, latency distributions, and error counters
using bounded route templates and status class labels.
"""
import time
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings
from app.core.metrics import (
    HTTP_REQUESTS_TOTAL,
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_ACTIVE_REQUESTS,
    HTTP_ERRORS_TOTAL,
    normalize_route_template,
    get_status_class
)


class PrometheusMetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware that records HTTP operational metrics for Prometheus.
    Uses route templates to protect metric label cardinality.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not settings.PROMETHEUS_ENABLED:
            return await call_next(request)

        # Exclude internal Prometheus scrape route from self-metering if desired
        raw_path = request.url.path
        if raw_path in ("/metrics", "/health", "/docs", "/openapi.json"):
            return await call_next(request)

        method = request.method
        route = normalize_route_template(raw_path)

        HTTP_ACTIVE_REQUESTS.labels(method=method, route=route).inc()
        start_time = time.perf_counter()
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception:
            status_code = 500
            raise
        finally:
            duration = time.perf_counter() - start_time
            status_class = get_status_class(status_code)

            HTTP_REQUESTS_TOTAL.labels(
                method=method,
                route=route,
                status_class=status_class
            ).inc()

            HTTP_REQUEST_DURATION_SECONDS.labels(
                method=method,
                route=route
            ).observe(duration)

            if status_code >= 400:
                HTTP_ERRORS_TOTAL.labels(
                    method=method,
                    route=route,
                    status_class=status_class
                ).inc()

            HTTP_ACTIVE_REQUESTS.labels(method=method, route=route).dec()
