"""
Unit and Integration Tests for Task Queue API Endpoints
Tests task enqueueing, task status retrieval, task registry validation, IDOR protection, and rate limiting.
"""
import pytest
from fastapi import status
from app.workers.queue import task_queue
import pytest_asyncio
from app.core.redis import redis_manager


class MockTaskRedis:
    def __init__(self):
        self.hashes = {}
        self.lists = {}

    async def hset(self, name, key=None, value=None, mapping=None):
        if name not in self.hashes:
            self.hashes[name] = {}
        if mapping:
            for k, v in mapping.items():
                self.hashes[name][str(k)] = str(v)
        elif key is not None:
            self.hashes[name][str(key)] = str(value)
        return 1

    async def expire(self, name, time):
        return True

    async def rpush(self, name, *values):
        if name not in self.lists:
            self.lists[name] = []
        for v in values:
            self.lists[name].append(str(v))
        return len(self.lists[name])

    async def hgetall(self, name):
        return self.hashes.get(name, {})

    async def rpoplpush(self, src, dst):
        if src not in self.lists or not self.lists[src]:
            return None
        val = self.lists[src].pop(0)
        if dst not in self.lists:
            self.lists[dst] = []
        self.lists[dst].append(val)
        return val

    async def lrem(self, name, count, value):
        if name in self.lists:
            self.lists[name] = [v for v in self.lists[name] if v != str(value)]
        return 1

    async def eval(self, *args, **kwargs):
        return [0, 60, 60]

    async def exists(self, *args, **kwargs):
        return False

    async def set(self, *args, **kwargs):
        return True

    async def get(self, *args, **kwargs):
        return None

    async def ttl(self, *args, **kwargs):
        return -1

    async def delete(self, *args, **kwargs):
        return 1


@pytest_asyncio.fixture(autouse=True)
async def mock_redis_for_tasks(monkeypatch):
    if redis_manager.get_client() is None:
        mock = MockTaskRedis()
        monkeypatch.setattr(redis_manager, "get_client", lambda: mock)



async def get_auth_headers(client, email: str = "user@pulseops.io", password: str = "UserPass123!"):
    res = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == status.HTTP_200_OK
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_enqueue_valid_telemetry_enrichment_task(async_client):
    """Verify enqueuing a valid telemetry enrichment task returns 202 Accepted and server-generated task_id."""
    await task_queue.clear()
    user_headers = await get_auth_headers(async_client, "user@pulseops.io", "UserPass123!")

    payload = {
        "task_type": "telemetry_enrichment",
        "payload": {
            "service_id": "srv-100",
            "metrics": [{"name": "latency", "value": 120.5}],
            "logs": [{"level": "INFO", "message": "Normal operation"}]
        }
    }

    res = await async_client.post("/api/v1/tasks/enqueue", json=payload, headers=user_headers)
    assert res.status_code == status.HTTP_202_ACCEPTED
    data = res.json()
    assert "task_id" in data
    assert data["task_type"] == "telemetry_enrichment"
    assert data["status"] == "queued"


@pytest.mark.asyncio
async def test_enqueue_unregistered_task_type_rejected(async_client):
    """Verify enqueuing an arbitrary/unregistered task type is rejected with HTTP 400."""
    user_headers = await get_auth_headers(async_client, "user@pulseops.io", "UserPass123!")
    payload = {
        "task_type": "malicious_eval_task",
        "payload": {"code": "import os; os.system('whoami')"}
    }

    res = await async_client.post("/api/v1/tasks/enqueue", json=payload, headers=user_headers)
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "Allowed task types" in res.json()["error"]["message"]


@pytest.mark.asyncio
async def test_controlled_failure_demo_task_requires_admin(async_client):
    """Verify controlled_failure_demo task fails for normal user (403) and succeeds for admin (202)."""
    user_headers = await get_auth_headers(async_client, "user@pulseops.io", "UserPass123!")
    admin_headers = await get_auth_headers(async_client, "admin@pulseops.io", "AdminPass123!")

    payload = {
        "task_type": "controlled_failure_demo",
        "payload": {}
    }

    # Normal user attempt -> 403 Forbidden
    res_user = await async_client.post("/api/v1/tasks/enqueue", json=payload, headers=user_headers)
    assert res_user.status_code == status.HTTP_403_FORBIDDEN

    # Admin user attempt -> 202 Accepted
    res_admin = await async_client.post("/api/v1/tasks/enqueue", json=payload, headers=admin_headers)
    assert res_admin.status_code == status.HTTP_202_ACCEPTED


@pytest.mark.asyncio
async def test_task_status_idor_protection(async_client):
    """Verify non-admin users cannot query tasks owned by other users (IDOR protection)."""
    await task_queue.clear()
    user_headers = await get_auth_headers(async_client, "user@pulseops.io", "UserPass123!")
    admin_headers = await get_auth_headers(async_client, "admin@pulseops.io", "AdminPass123!")

    # Enqueue task as Admin
    payload = {
        "task_type": "alert_notification",
        "payload": {"alert_id": "alt-555", "message": "System check"}
    }
    res_enqueue = await async_client.post("/api/v1/tasks/enqueue", json=payload, headers=admin_headers)
    assert res_enqueue.status_code == status.HTTP_202_ACCEPTED
    task_id = res_enqueue.json()["task_id"]

    # Normal user attempts to query Admin's task status -> 403 Forbidden
    res_user_query = await async_client.get(f"/api/v1/tasks/status/{task_id}", headers=user_headers)
    assert res_user_query.status_code == status.HTTP_403_FORBIDDEN

    # Admin queries task status -> 200 OK
    res_admin_query = await async_client.get(f"/api/v1/tasks/status/{task_id}", headers=admin_headers)
    assert res_admin_query.status_code == status.HTTP_200_OK
    assert res_admin_query.json()["task_id"] == task_id


@pytest.mark.asyncio
async def test_task_status_not_found(async_client):
    """Verify querying status for non-existent task_id returns 404 Not Found."""
    user_headers = await get_auth_headers(async_client, "user@pulseops.io", "UserPass123!")
    res = await async_client.get("/api/v1/tasks/status/non-existent-task-9999", headers=user_headers)
    assert res.status_code == status.HTTP_404_NOT_FOUND



@pytest.mark.asyncio
async def test_task_enqueue_redis_unavailable_returns_503(async_client, monkeypatch):
    """Verify that when Redis is unavailable, task enqueue returns 503 Service Unavailable instead of fake in-memory fallback."""
    from app.core.redis import redis_manager
    monkeypatch.setattr(redis_manager, "get_client", lambda: None)

    user_headers = await get_auth_headers(async_client, "user@pulseops.io", "UserPass123!")
    payload = {
        "task_type": "telemetry_enrichment",
        "payload": {"service_id": "srv-test"}
    }

    res = await async_client.post("/api/v1/tasks/enqueue", json=payload, headers=user_headers)
    assert res.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "currently unavailable" in res.json()["error"]["message"]
