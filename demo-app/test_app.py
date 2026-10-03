"""
Phase 1 Test Suite for Controllable Demo Application
"""
import sys
from pathlib import Path
import pytest

# Ensure demo-app directory is prioritized in sys.path
demo_app_dir = str(Path(__file__).parent.resolve())
if demo_app_dir not in sys.path:
    sys.path.insert(0, demo_app_dir)

from fastapi.testclient import TestClient
from app import app

client = TestClient(app)



def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "demo-app"
    assert data["status"] == "running"
    assert "version" in data


def test_read_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "demo-app"
    assert "timestamp" in data


def test_read_users():
    response = client.get("/api/users")
    assert response.status_code == 200
    users = response.json()
    assert isinstance(users, list)
    assert len(users) == 3
    assert users[0]["username"] == "alice"


def test_read_orders():
    response = client.get("/api/orders")
    assert response.status_code == 200
    orders = response.json()
    assert isinstance(orders, list)
    assert len(orders) == 3
    assert orders[0]["id"] == "ord-101"


def test_read_slow_default():
    response = client.get("/api/slow?delay=0.1")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["requested_delay_seconds"] == 0.1


def test_read_slow_zero():
    response = client.get("/api/slow?delay=0")
    assert response.status_code == 200
    data = response.json()
    assert data["requested_delay_seconds"] == 0.0


def test_read_slow_negative_validation_error():
    response = client.get("/api/slow?delay=-2.0")
    # FastAPI returns 422 Unprocessable Entity for query validation errors
    assert response.status_code == 422


def test_read_slow_excessive_validation_error():
    response = client.get("/api/slow?delay=999.0")
    assert response.status_code == 422


def test_read_error_returns_500():
    response = client.get("/api/error")
    assert response.status_code == 500
    data = response.json()
    assert data["detail"] == "Simulated server failure endpoint triggered"
