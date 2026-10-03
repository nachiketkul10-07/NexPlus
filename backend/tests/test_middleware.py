"""
Unit and integration tests for Middleware components (Request ID, Security Headers, CORS, Payload Size Limit).
"""
import uuid
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_request_id_generated_when_missing():
    response = client.get("/health")
    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    req_id = response.headers["X-Request-ID"]
    # Check valid UUID
    uuid.UUID(req_id)


def test_request_id_preserved_when_provided():
    custom_id = "test-correlation-id-12345"
    response = client.get("/health", headers={"X-Request-ID": custom_id})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == custom_id


def test_security_headers_present():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "default-src 'none'" in response.headers.get("Content-Security-Policy", "")
    assert response.headers.get("Cache-Control") == "no-store"
    assert response.headers.get("X-XSS-Protection") is None


def test_cors_allowed_origin():
    response = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_cors_disallowed_origin():
    response = client.get("/health", headers={"Origin": "http://malicious-attacker.com"})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_payload_size_limit_rejected():
    # Simulate Content-Length exceeding 10MB limit
    oversized_length = str(15 * 1024 * 1024)
    response = client.post(
        "/test-validation",
        headers={"Content-Length": oversized_length, "Content-Type": "application/json"},
        content='{"name": "test", "count": 1}'
    )
    assert response.status_code == 413
    data = response.json()
    assert data["error"]["code"] == "PAYLOAD_TOO_LARGE"
