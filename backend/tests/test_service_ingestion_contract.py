from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def _token(email, password):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def _create_service(token, identifier):
    response = client.post(
        "/api/v1/services",
        headers={"Authorization": f"Bearer {token}"},
        json={"identifier": identifier, "name": identifier, "environment": "test", "framework": "pytest", "language": "Python"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_services_keep_separate_keys_and_ingest_each_telemetry_type():
    user_token = _token("user@pulseops.io", "UserPass123!")
    service_a = _create_service(user_token, "planner-test-a")
    service_b = _create_service(user_token, "planner-test-b")
    key_a = service_a["ingest_key"]
    key_b = service_b["ingest_key"]

    event = client.post("/api/v1/telemetry/events", headers={"X-Ingest-Key": key_a}, json={
        "service_id": service_a["identifier"], "method": "GET", "endpoint": "/health", "status_code": 200,
        "duration_ms": 18, "outcome": "success",
    })
    metric = client.post("/api/v1/telemetry/metrics", headers={"X-Ingest-Key": key_a}, json={
        "service_id": service_a["identifier"], "metric_name": "queue_depth", "value": 3,
    })
    log = client.post("/api/v1/telemetry/logs", headers={"X-Ingest-Key": key_a}, json={
        "service_id": service_a["identifier"], "level": "INFO", "message": "planner started",
    })
    assert [event.status_code, metric.status_code, log.status_code] == [202, 202, 202]

    for endpoint in ("events", "metrics", "logs"):
        response = client.get(
            f"/api/v1/telemetry/{endpoint}?service_id={service_a['id']}",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert response.status_code == 200
        assert response.json()

    wrong_service = client.post("/api/v1/telemetry/events", headers={"X-Ingest-Key": key_a}, json={
        "service_id": service_b["identifier"], "method": "GET", "endpoint": "/health", "status_code": 200,
    })
    assert wrong_service.status_code == 403

    services = client.get("/api/v1/services", headers={"Authorization": f"Bearer {user_token}"}).json()
    current_a = next(item for item in services if item["id"] == service_a["id"])
    assert current_a["last_seen_at"]
    assert current_a["is_active"] is True

    admin_token = _token("admin@pulseops.io", "AdminPass123!")
    rotated = client.post(
        f"/api/v1/services/{service_a['id']}/rotate-ingest-key",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert rotated.status_code == 200
    key_new = rotated.json()["ingest_key"]
    old_key_result = client.post("/api/v1/telemetry/logs", headers={"X-Ingest-Key": key_a}, json={"message": "old key"})
    new_key_result = client.post("/api/v1/telemetry/logs", headers={"X-Ingest-Key": key_new}, json={"message": "new key"})
    assert old_key_result.status_code == 401
    assert new_key_result.status_code == 202

    deactivated = client.patch(
        f"/api/v1/services/{service_b['id']}/status?is_active=false",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert deactivated.status_code == 200
    rejected = client.post("/api/v1/telemetry/events", headers={"X-Ingest-Key": key_b}, json={"method": "GET"})
    assert rejected.status_code == 403


def test_service_identifier_normalization_and_duplicate_rejection():
    token = _token("user@pulseops.io", "UserPass123!")
    created = _create_service(token, "Case-Sensitive-Service")
    assert created["identifier"] == "case-sensitive-service"
    duplicate = client.post(
        "/api/v1/services", headers={"Authorization": f"Bearer {token}"},
        json={"identifier": "CASE-SENSITIVE-SERVICE", "name": "duplicate"},
    )
    assert duplicate.status_code == 400


def test_ingestion_rejects_oversized_batches_and_commit_failure_is_not_accepted(monkeypatch):
    token = _token("user@pulseops.io", "UserPass123!")
    service = _create_service(token, "persist-test")
    too_many = client.post(
        "/api/v1/telemetry/events", headers={"X-Ingest-Key": service["ingest_key"]},
        json=[{"method": "GET", "endpoint": "/health"} for _ in range(101)],
    )
    assert too_many.status_code == 422

    from app.db.repositories.telemetry_repository import PostgresTelemetryRepository

    async def fail_before_persist(*args, **kwargs):
        raise RuntimeError("test database failure")

    monkeypatch.setattr(PostgresTelemetryRepository, "create_events_batch", fail_before_persist)
    failed = client.post(
        "/api/v1/telemetry/events", headers={"X-Ingest-Key": service["ingest_key"]},
        json={"service_id": service["identifier"], "method": "GET", "endpoint": "/health"},
    )
    assert failed.status_code == 500
    assert failed.json()["error"]["code"] == "INTERNAL_SERVER_ERROR"
