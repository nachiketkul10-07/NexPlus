"""
Authentication Integration Tests (Registration, Login, Logout, /me)
"""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_register_user_success():
    payload = {
        "email": "newuser@pulseops.io",
        "password": "SecurePassword123!",
        "full_name": "New Test User",
        "role": "user"
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == payload["email"]
    assert data["full_name"] == payload["full_name"]
    assert data["role"] == "user"
    assert "id" in data
    # Password and hash MUST NOT be returned in response
    assert "password" not in data
    assert "hashed_password" not in data


def test_register_duplicate_email_fails():
    payload = {
        "email": "user@pulseops.io",  # Seeded email
        "password": "SecurePassword123!",
        "full_name": "Duplicate User",
        "role": "user"
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "BAD_REQUEST"
    assert "already exists" in data["error"]["message"]


def test_register_weak_password_fails():
    payload = {
        "email": "weak@pulseops.io",
        "password": "simple",  # Fails min length & complexity
        "full_name": "Weak User",
        "role": "user"
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"


def test_login_success():
    login_payload = {
        "email": "user@pulseops.io",
        "password": "UserPass123!"
    }
    response = client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0
    assert data["user"]["email"] == "user@pulseops.io"
    assert "password" not in data["user"]


def test_login_invalid_password_safe_error():
    login_payload = {
        "email": "user@pulseops.io",
        "password": "WrongPassword123!"
    }
    response = client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 401
    data = response.json()
    # Ensure message is safe and does not reveal if email exists
    assert data["error"]["message"] == "Invalid email or password"


def test_get_me_success():
    # 1. Login to get token
    login_res = client.post("/api/v1/auth/login", json={
        "email": "admin@pulseops.io",
        "password": "AdminPass123!"
    })
    token = login_res.json()["access_token"]

    # 2. Call /me endpoint with token
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["email"] == "admin@pulseops.io"
    assert me_data["role"] == "admin"


def test_get_me_unauthenticated_rejected():
    me_res = client.get("/api/v1/auth/me")
    assert me_res.status_code == 401
    assert me_res.json()["error"]["code"] == "UNAUTHORIZED"


def test_public_registration_blocks_admin_role_escalation():
    payload = {
        "email": "hacker_attempt@nexpulse.io",
        "password": "SecurePassword123!",
        "full_name": "Attacker Name",
        "role": "admin"
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["role"] == "user"  # Must force standard user role


def test_register_and_login_e2e_flow():
    reg_payload = {
        "email": "e2e_user@nexpulse.io",
        "password": "E2ESecurePass123!",
        "full_name": "E2E User"
    }
    reg_res = client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_res.status_code == 201

    login_res = client.post("/api/v1/auth/login", json={
        "email": reg_payload["email"],
        "password": reg_payload["password"]
    })
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    assert token

    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["email"] == reg_payload["email"]

