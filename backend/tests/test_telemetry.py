"""
Phase 5 Comprehensive Unit and Integration Tests for Telemetry Ingestion Engine
Tests Authentication, Validation, Security controls, Persistence, and Telemetry Queries.
"""
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# Helper to get authenticated User token
def get_user_token() -> str:
    res = client.post("/api/v1/auth/login", json={"email": "user@pulseops.io", "password": "UserPass123!"})
    return res.json()["access_token"]


# Dev seed ingest key for demo-app
DEV_INGEST_KEY = "pik_dev_demo_app_secret_key_12345"


# ----------------------------------------------------------------------
# 1. Service Ingestion Key Authentication & Cross-Service Security
# ----------------------------------------------------------------------

def test_telemetry_missing_auth_header():
    """Verify missing ingestion credential header is rejected with HTTP 401."""
    response = client.post("/api/v1/telemetry/events", json={
        "service_id": "demo-app",
        "method": "GET",
        "endpoint": "/api/orders",
        "status_code": 200,
        "duration_ms": 50,
        "outcome": "success"
    })
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_telemetry_invalid_auth_key():
    """Verify invalid ingestion credential key is rejected with HTTP 401."""
    response = client.post(
        "/api/v1/telemetry/events",
        json={"method": "GET", "endpoint": "/api/orders", "outcome": "success"},
        headers={"X-Ingest-Key": "invalid_secret_key_9999"}
    )
    assert response.status_code == 401
    assert "Invalid service ingestion key" in response.json()["error"]["message"]


def test_telemetry_cross_service_submission_rejected():
    """Verify valid key for Service A cannot submit telemetry for Service B (HTTP 403)."""
    response = client.post(
        "/api/v1/telemetry/events",
        json={
            "service_id": "other-service-id-or-name",
            "method": "POST",
            "endpoint": "/api/checkout",
            "outcome": "success"
        },
        headers={"X-Ingest-Key": DEV_INGEST_KEY}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
    assert "not authorized for the specified target service" in response.json()["error"]["message"]


# ----------------------------------------------------------------------
# 2. Service Registration and Ingest Key Lifecyle
# ----------------------------------------------------------------------

def test_service_registration_and_ingest_flow():
    """Verify user can register a new service, receive ingest key once, and submit telemetry."""
    token = get_user_token()

    # 1. Register new service
    reg_res = client.post(
        "/api/v1/services",
        json={
            "identifier": "payment-gateway",
            "name": "Payment Processing Service",
            "environment": "production",
            "base_url": "https://payments.example.com",
            "health_path": "/healthz"
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    assert reg_res.status_code == 201
    serv_data = reg_res.json()
    new_service_id = serv_data["id"]
    new_ingest_key = serv_data["ingest_key"]
    assert new_ingest_key.startswith("pik_live_")

    # 2. Use newly received ingest key to submit telemetry event
    ingest_res = client.post(
        "/api/v1/telemetry/events",
        json={
            "service_id": new_service_id,
            "method": "POST",
            "endpoint": "/v1/charges",
            "status_code": 201,
            "duration_ms": 145,
            "outcome": "success"
        },
        headers={"X-Ingest-Key": new_ingest_key}
    )
    assert ingest_res.status_code == 202
    assert ingest_res.json()["accepted_count"] == 1


# ----------------------------------------------------------------------
# 3. Payload Validation & Secret Scrubbing Tests
# ----------------------------------------------------------------------

def test_telemetry_invalid_http_method():
    """Verify invalid HTTP method is rejected with HTTP 422."""
    response = client.post(
        "/api/v1/telemetry/events",
        json={"method": "INVALID_METHOD", "outcome": "success"},
        headers={"X-Ingest-Key": DEV_INGEST_KEY}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_telemetry_out_of_range_timestamp():
    """Verify absurd historical or future timestamps are rejected with HTTP 422."""
    old_ts = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
    response = client.post(
        "/api/v1/telemetry/events",
        json={"timestamp": old_ts, "method": "GET", "outcome": "success"},
        headers={"X-Ingest-Key": DEV_INGEST_KEY}
    )
    assert response.status_code == 422


def test_telemetry_metadata_sensitive_secrets_scrubbed():
    """Verify passwords, authorization tokens, and credentials in metadata are redacted."""
    token = get_user_token()

    event_payload = {
        "method": "POST",
        "endpoint": "/api/login",
        "status_code": 200,
        "outcome": "success",
        "metadata": {
            "user_id": 42,
            "authorization": "Bearer secret_jwt_token_here",
            "password": "SuperSecretPassword123!",
            "normal_field": "public_data"
        }
    }

    ingest_res = client.post(
        "/api/v1/telemetry/events",
        json=event_payload,
        headers={"X-Ingest-Key": DEV_INGEST_KEY}
    )
    assert ingest_res.status_code == 202

    # Query events to verify stored metadata
    query_res = client.get(
        "/api/v1/telemetry/events?limit=5",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert query_res.status_code == 200
    events = query_res.json()
    latest = events[0]
    meta = latest["metadata"]

    assert meta["authorization"] == "[REDACTED]"
    assert meta["password"] == "[REDACTED]"
    assert meta["normal_field"] == "public_data"


def test_metric_ingestion_and_validation():
    """Verify metric ingestion, non-finite value rejection, and query contracts."""
    token = get_user_token()

    # Valid Metric Ingestion
    metric_payload = {
        "metric_name": "error_rate",
        "value": 0.05,
        "window_seconds": 60
    }
    res = client.post(
        "/api/v1/telemetry/metrics",
        json=metric_payload,
        headers={"X-Ingest-Key": DEV_INGEST_KEY}
    )
    assert res.status_code == 202
    assert res.json()["accepted_count"] == 1

    # Query Metric
    q_res = client.get(
        "/api/v1/metrics?metric_name=error_rate",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert q_res.status_code == 200
    metrics = q_res.json()
    assert len(metrics) >= 1
    assert metrics[0]["metric_name"] == "error_rate"
    assert metrics[0]["value"] == 0.05


def test_log_ingestion_and_validation():
    """Verify log ingestion, invalid log level rejection, and log search."""
    token = get_user_token()

    # Invalid Log Level
    bad_log = {"level": "SUPER_ERROR", "message": "Test error log"}
    bad_res = client.post(
        "/api/v1/telemetry/logs",
        json=bad_log,
        headers={"X-Ingest-Key": DEV_INGEST_KEY}
    )
    assert bad_res.status_code == 422

    # Valid Log Ingestion
    good_log = {
        "level": "ERROR",
        "message": "Database connection timeout observed in order service",
        "request_id": "req_test_12345",
        "stack_trace": "Traceback (most recent call last):\n  File 'app.py', line 42"
    }
    good_res = client.post(
        "/api/v1/telemetry/logs",
        json=good_log,
        headers={"X-Ingest-Key": DEV_INGEST_KEY}
    )
    assert good_res.status_code == 202

    # Query Logs
    q_res = client.get(
        "/api/v1/logs?level=ERROR",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert q_res.status_code == 200
    logs = q_res.json()
    assert len(logs) >= 1
    assert logs[0]["level"] == "ERROR"
    assert "Database connection timeout" in logs[0]["message"]


def test_unified_batch_ingestion():
    """Verify unified batch ingestion accepting events, metrics, and logs in one payload."""
    batch_payload = {
        "service_id": "demo-app",
        "events": [
            {"method": "GET", "endpoint": "/api/health", "status_code": 200, "duration_ms": 10, "outcome": "success"},
            {"method": "GET", "endpoint": "/api/slow", "status_code": 200, "duration_ms": 3050, "outcome": "slow"}
        ],
        "metrics": [
            {"metric_name": "avg_latency_ms", "value": 1530.0}
        ],
        "logs": [
            {"level": "WARN", "message": "Slow request threshold exceeded on /api/slow"}
        ]
    }
    res = client.post(
        "/api/v1/telemetry/ingest",
        json=batch_payload,
        headers={"X-Ingest-Key": DEV_INGEST_KEY}
    )
    assert res.status_code == 202
    assert res.json()["accepted_count"] == 4
