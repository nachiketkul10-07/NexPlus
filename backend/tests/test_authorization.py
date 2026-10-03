"""
Authorization tests for role checking (require_admin) and resource ownership verification.
"""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def get_tokens():
    # Admin Token
    admin_res = client.post("/api/v1/auth/login", json={"email": "admin@pulseops.io", "password": "AdminPass123!"})
    admin_token = admin_res.json()["access_token"]
    admin_user_id = admin_res.json()["user"]["id"]

    # User Token
    user_res = client.post("/api/v1/auth/login", json={"email": "user@pulseops.io", "password": "UserPass123!"})
    user_token = user_res.json()["access_token"]
    user_id = user_res.json()["user"]["id"]

    return (admin_token, admin_user_id), (user_token, user_id)


def test_protected_user_route_requires_auth():
    # Unauthenticated request rejected with 401
    res = client.get("/test-protected-user")
    assert res.status_code == 401

    (admin_token, _), (user_token, _) = get_tokens()

    # Authenticated user request permitted
    res_user = client.get("/test-protected-user", headers={"Authorization": f"Bearer {user_token}"})
    assert res_user.status_code == 200
    assert res_user.json()["status"] == "authenticated"


def test_admin_only_route_authorization():
    (admin_token, _), (user_token, _) = get_tokens()

    # Standard user request to admin route rejected with 403 Forbidden
    res_user = client.get("/test-protected-admin", headers={"Authorization": f"Bearer {user_token}"})
    assert res_user.status_code == 403
    assert res_user.json()["error"]["code"] == "FORBIDDEN"
    assert "Administrator privileges required" in res_user.json()["error"]["message"]

    # Admin user request to admin route permitted with 200 OK
    res_admin = client.get("/test-protected-admin", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_admin.status_code == 200
    assert res_admin.json()["status"] == "admin_granted"


def test_resource_ownership_authorization():
    (admin_token, admin_id), (user_token, user_id) = get_tokens()
    other_owner_id = "33333333-3333-3333-3333-333333333333"

    # 1. User accessing their own resource -> Permitted (200 OK)
    res_own = client.get(f"/test-resource-ownership/{user_id}", headers={"Authorization": f"Bearer {user_token}"})
    assert res_own.status_code == 200
    assert res_own.json()["status"] == "access_granted"

    # 2. User attempting to access another user's resource -> Rejected (403 Forbidden)
    res_other = client.get(f"/test-resource-ownership/{other_owner_id}", headers={"Authorization": f"Bearer {user_token}"})
    assert res_other.status_code == 403
    assert res_other.json()["error"]["code"] == "FORBIDDEN"

    # 3. Admin accessing any user's resource -> Permitted (200 OK)
    res_admin_access = client.get(f"/test-resource-ownership/{other_owner_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_admin_access.status_code == 200
    assert res_admin_access.json()["status"] == "access_granted"
