"""
PulseOps Operational Prometheus Metrics Registry
Defines bounded-cardinality Prometheus counters, gauges, and histograms
observing HTTP requests, telemetry ingestion, worker tasks, and alert evaluations.
"""
from typing import Optional
from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    CollectorRegistry,
    generate_latest,
    CONTENT_TYPE_LATEST,
    REGISTRY
)

# Custom Registry to avoid collision in test suites
registry = REGISTRY

# 1. HTTP Metrics
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total cumulative HTTP requests handled by service",
    ["method", "route", "status_class"],
    registry=registry
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request execution latency distribution in seconds",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=registry
)

HTTP_ACTIVE_REQUESTS = Gauge(
    "http_requests_active",
    "Current active concurrent HTTP requests being processed",
    ["method", "route"],
    registry=registry
)

HTTP_ERRORS_TOTAL = Counter(
    "http_errors_total",
    "Total cumulative HTTP 4xx and 5xx error responses",
    ["method", "route", "status_class"],
    registry=registry
)

# 2. Telemetry Ingestion Metrics
TELEMETRY_EVENTS_INGESTED_TOTAL = Counter(
    "telemetry_events_ingested_total",
    "Total cumulative telemetry events ingested",
    ["telemetry_type", "outcome"],
    registry=registry
)

TELEMETRY_METRICS_INGESTED_TOTAL = Counter(
    "telemetry_metrics_ingested_total",
    "Total cumulative telemetry metric data points ingested",
    ["outcome"],
    registry=registry
)

TELEMETRY_LOGS_INGESTED_TOTAL = Counter(
    "telemetry_logs_ingested_total",
    "Total cumulative telemetry log entries ingested",
    ["outcome"],
    registry=registry
)

TELEMETRY_INGESTION_ERRORS_TOTAL = Counter(
    "telemetry_ingestion_errors_total",
    "Total cumulative telemetry ingestion failures",
    ["telemetry_type"],
    registry=registry
)

# 3. Alert & Incident Operational Metrics
ALERT_EVALUATIONS_TOTAL = Counter(
    "alert_evaluations_total",
    "Total cumulative alert rule evaluations executed",
    registry=registry
)

ALERTS_TRIGGERED_TOTAL = Counter(
    "alerts_triggered_total",
    "Total cumulative alert instances triggered",
    ["severity"],
    registry=registry
)

INCIDENTS_CREATED_TOTAL = Counter(
    "incidents_created_total",
    "Total cumulative incidents automatically created",
    ["severity"],
    registry=registry
)

# 4. Worker & Background Task Metrics
BACKGROUND_TASKS_TOTAL = Counter(
    "background_tasks_total",
    "Total cumulative background tasks enqueued or processed",
    ["task_type", "outcome"],
    registry=registry
)

BACKGROUND_TASKS_FAILED_TOTAL = Counter(
    "background_tasks_failed_total",
    "Total cumulative background task execution failures",
    ["task_type"],
    registry=registry
)

BACKGROUND_TASKS_DEAD_LETTERED_TOTAL = Counter(
    "background_tasks_dead_lettered_total",
    "Total cumulative background tasks moved to Dead Letter Queue",
    ["task_type"],
    registry=registry
)

WORKER_TASK_DURATION_SECONDS = Histogram(
    "worker_task_duration_seconds",
    "Worker background task execution latency in seconds",
    ["task_type"],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 30.0),
    registry=registry
)

WORKER_ACTIVE_CONCURRENCY = Gauge(
    "worker_active_concurrency",
    "Current active worker execution concurrency",
    registry=registry
)

# 5. AI Assistant Metrics
AI_ANALYSIS_REQUESTS_TOTAL = Counter(
    "pulseops_ai_analysis_requests_total",
    "Total cumulative AI analysis requests handled",
    ["provider", "status"],
    registry=registry
)

AI_ANALYSIS_DURATION_SECONDS = Histogram(
    "pulseops_ai_analysis_duration_seconds",
    "AI analysis execution latency in seconds",
    ["provider"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 20.0, 30.0),
    registry=registry
)

AI_ANALYSIS_FALLBACK_TOTAL = Counter(
    "pulseops_ai_analysis_fallback_total",
    "Total cumulative fallback AI analysis executions",
    ["reason"],
    registry=registry
)

def normalize_route_template(route_str: str) -> str:
    """
    Normalizes raw request URLs to bounded route templates to eliminate metric cardinality explosion.
    Replaces UUIDs, numeric IDs, and variable parameters with generic placeholders.
    """
    if not route_str:
        return "unknown"

    import re
    # Strip query parameters
    route = route_str.split("?")[0]

    # Replace UUIDs
    route = re.sub(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
        "{id}",
        route
    )
    # Replace numeric resource IDs
    route = re.sub(r"/\d+(?=/|$)", "/{id}", route)

    return route


def get_status_class(status_code: int) -> str:
    """Returns bounded status class label string: 2xx, 3xx, 4xx, 5xx."""
    if 200 <= status_code < 300:
        return "2xx"
    elif 300 <= status_code < 400:
        return "3xx"
    elif 400 <= status_code < 500:
        return "4xx"
    elif status_code >= 500:
        return "5xx"
    return "other"
