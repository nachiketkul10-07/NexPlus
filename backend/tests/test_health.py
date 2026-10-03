from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_top_level_health():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "NexPulse Backend"
    assert "version" in data


def test_v1_health():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "NexPulse Backend"
    assert "timestamp" in data

