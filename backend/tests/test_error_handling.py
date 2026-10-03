"""
Unit and integration tests for Global Error Handling and Shielding.
"""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_404_not_found_error_response():
    response = client.get("/non-existent-route")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "NOT_FOUND"
    assert "request_id" in data["error"]
    assert data["error"]["request_id"] is not None


def test_validation_error_response():
    # Invalid payload: name is too short (min 2 chars), count is < 1
    invalid_payload = {"name": "a", "count": 0}
    response = client.post("/test-validation", json=invalid_payload)
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert "request_id" in data["error"]
    assert isinstance(data["error"]["details"], list)
    assert len(data["error"]["details"]) >= 1


def test_unhandled_error_shielding():
    # Verify 500 error shields tracebacks and returns clean structured error response
    response = client.get("/test-unhandled-error")
    assert response.status_code == 500
    data = response.json()
    assert data["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert data["error"]["message"] == "An unexpected server error occurred. Please contact support."
    assert "request_id" in data["error"]

    # Verify no tracebacks, paths, or code leaks in response text
    raw_text = response.text
    assert "Traceback" not in raw_text
    assert "RuntimeError" not in raw_text
    assert "app/main.py" not in raw_text
