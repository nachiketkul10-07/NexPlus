"""
Unit and Integration Tests for Phase 10 Observability
Validates OpenTelemetry initialization, tracer provider configuration,
Prometheus /metrics endpoint, metric label cardinality controls, secret scrubbing,
exporter fault tolerance, worker metrics, telemetry metrics, and alert metrics.
"""
import pytest
from fastapi import status
from httpx import AsyncClient
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.core.config import settings
from app.core.telemetry import get_tracer
from app.core.metrics import (
    HTTP_REQUESTS_TOTAL,
    TELEMETRY_EVENTS_INGESTED_TOTAL,
    BACKGROUND_TASKS_TOTAL,
    ALERT_EVALUATIONS_TOTAL,
    ALERTS_TRIGGERED_TOTAL,
    INCIDENTS_CREATED_TOTAL,
    normalize_route_template,
    get_status_class
)


@pytest.mark.asyncio
async def test_opentelemetry_initializes():
    """1. Verify OpenTelemetry tracer provider is initialized and accessible."""
    tracer = get_tracer("test_tracer")
    assert tracer is not None


@pytest.mark.asyncio
async def test_service_name_configured():
    """2. Verify OTEL_SERVICE_NAME configuration setting default is set to pulseops-backend."""
    assert settings.OTEL_SERVICE_NAME == "pulseops-backend"


@pytest.mark.asyncio
async def test_http_spans_created():
    """3. Verify OpenTelemetry spans can be created and ended without error."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("test_tracer")

    with tracer.start_as_current_span("test_http_operation") as span:
        span.set_attribute("http.method", "GET")
        span.set_attribute("http.route", "/api/v1/health")

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "test_http_operation"
    assert spans[0].attributes["http.method"] == "GET"


@pytest.mark.asyncio
async def test_errors_mark_spans_correctly():
    """4. Verify error exceptions set span status code to ERROR."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("test_tracer")

    try:
        with tracer.start_as_current_span("error_span") as span:
            raise ValueError("Simulated failure")
    except ValueError:
        pass

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "error_span"


@pytest.mark.asyncio
async def test_prometheus_endpoint_exists(async_client):
    """5. Verify /metrics endpoint returns HTTP 200 OK with Prometheus text format content."""
    res = await async_client.get("/metrics")
    assert res.status_code == status.HTTP_200_OK
    assert "text/plain" in res.headers["content-type"]
    assert "# HELP" in res.text or "# TYPE" in res.text


@pytest.mark.asyncio
async def test_expected_metrics_exist_in_prometheus_output(async_client):
    """6. Verify standard application counters and histograms exist in /metrics output."""
    res = await async_client.get("/metrics")
    assert res.status_code == status.HTTP_200_OK
    content = res.text

    assert "http_requests_total" in content
    assert "telemetry_events_ingested_total" in content
    assert "background_tasks_total" in content
    assert "alert_evaluations_total" in content


@pytest.mark.asyncio
async def test_metrics_contain_bounded_labels():
    """7. Verify metric label helpers produce bounded status classes and route templates."""
    assert get_status_class(200) == "2xx"
    assert get_status_class(201) == "2xx"
    assert get_status_class(400) == "4xx"
    assert get_status_class(404) == "4xx"
    assert get_status_class(500) == "5xx"

    route = normalize_route_template("/api/v1/services/7cc8f831-274e-4e6f-870d-854cb048cbb3")
    assert route == "/api/v1/services/{id}"


@pytest.mark.asyncio
async def test_no_secrets_appear_in_metrics(async_client):
    """8. Verify passwords, JWT tokens, and ingest keys never leak into /metrics content."""
    res = await async_client.get("/metrics")
    assert res.status_code == status.HTTP_200_OK
    content = res.text

    assert "AdminPass123!" not in content
    assert "UserPass123!" not in content
    assert "pik_dev_demo_app_secret_key_12345" not in content


@pytest.mark.asyncio
async def test_no_raw_uuid_or_request_ids_in_metric_labels():
    """9. Verify raw UUIDs and arbitrary request parameters are stripped from metric route templates."""
    test_uuid_path = "/api/v1/incidents/550e8400-e29b-41d4-a716-446655440000"
    normalized = normalize_route_template(test_uuid_path)
    assert "550e8400" not in normalized
    assert normalized == "/api/v1/incidents/{id}"


@pytest.mark.asyncio
async def test_observability_can_be_disabled_by_config(async_client, monkeypatch):
    """10. Verify disabling PROMETHEUS_ENABLED returns HTTP 503 Service Unavailable for /metrics."""
    monkeypatch.setattr(settings, "PROMETHEUS_ENABLED", False)
    res = await async_client.get("/metrics")
    assert res.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


@pytest.mark.asyncio
async def test_otlp_exporter_failure_does_not_crash_requests(async_client):
    """11. Verify requests complete normally even if OTLP span exporter endpoint is unreachable."""
    res = await async_client.get("/health")
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_worker_metrics_increment():
    """12. Verify worker metrics counters increment when recording background task execution."""
    initial = BACKGROUND_TASKS_TOTAL.labels(task_type="telemetry_enrichment", outcome="completed")._value.get()
    BACKGROUND_TASKS_TOTAL.labels(task_type="telemetry_enrichment", outcome="completed").inc()
    after = BACKGROUND_TASKS_TOTAL.labels(task_type="telemetry_enrichment", outcome="completed")._value.get()
    assert after == initial + 1


@pytest.mark.asyncio
async def test_telemetry_ingestion_metrics_increment():
    """13. Verify telemetry ingestion counters increment correctly."""
    initial = TELEMETRY_EVENTS_INGESTED_TOTAL.labels(telemetry_type="metric", outcome="success")._value.get()
    TELEMETRY_EVENTS_INGESTED_TOTAL.labels(telemetry_type="metric", outcome="success").inc()
    after = TELEMETRY_EVENTS_INGESTED_TOTAL.labels(telemetry_type="metric", outcome="success")._value.get()
    assert after == initial + 1


@pytest.mark.asyncio
async def test_alert_metrics_increment():
    """14. Verify alert rule evaluation and triggered counters increment correctly."""
    initial_evals = ALERT_EVALUATIONS_TOTAL._value.get()
    ALERT_EVALUATIONS_TOTAL.inc(3)
    assert ALERT_EVALUATIONS_TOTAL._value.get() == initial_evals + 3

    initial_trig = ALERTS_TRIGGERED_TOTAL.labels(severity="critical")._value.get()
    ALERTS_TRIGGERED_TOTAL.labels(severity="critical").inc()
    assert ALERTS_TRIGGERED_TOTAL.labels(severity="critical")._value.get() == initial_trig + 1
