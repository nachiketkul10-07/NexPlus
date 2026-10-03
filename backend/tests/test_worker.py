"""
Unit and Integration Tests for Task Worker Processing Engine
Tests task execution, retries, MAX_ATTEMPTS enforcement, Dead-Letter Queue (DLQ) movement, and telemetry/notification task execution.
"""
import pytest
from app.workers.queue import task_queue
from app.workers.worker import TaskWorker
from app.workers.tasks.telemetry_enrichment import run_telemetry_enrichment
from app.workers.tasks.alert_notification import run_alert_notification
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
async def mock_redis_for_worker(monkeypatch):
    if redis_manager.get_client() is None:
        mock = MockTaskRedis()
        monkeypatch.setattr(redis_manager, "get_client", lambda: mock)



@pytest.mark.asyncio
async def test_telemetry_enrichment_task_execution():
    """Verify telemetry enrichment task handler logic calculates metrics and traffic classification."""
    payload = {
        "service_id": "srv-prod-api",
        "metrics": [
            {"name": "latency", "value": 150.0},
            {"name": "latency", "value": 250.0}
        ],
        "logs": [
            {"level": "INFO", "message": "Health normal"},
            {"level": "ERROR", "message": "Connection timeout"}
        ]
    }

    result = await run_telemetry_enrichment(payload)

    assert result["service_id"] == "srv-prod-api"
    assert result["metrics_processed"] == 2
    assert result["logs_processed"] == 2
    assert result["error_logs_count"] == 1
    assert result["avg_latency_ms"] == 200.0
    assert result["traffic_classification"] == "HEALTHY"
    assert result["enriched"] is True


@pytest.mark.asyncio
async def test_alert_notification_task_execution():
    """Verify alert notification task handler logs notification and returns dispatched result."""
    payload = {
        "alert_id": "alt-999",
        "rule_name": "High CPU Rule",
        "severity": "CRITICAL",
        "message": "CPU usage > 90%",
        "channel": "internal_sink"
    }

    result = await run_alert_notification(payload)

    assert result["alert_id"] == "alt-999"
    assert result["severity"] == "CRITICAL"
    assert result["dispatched"] is True


@pytest.mark.asyncio
async def test_worker_controlled_failure_demo_transitions_to_dlq():
    """
    Verify worker executes controlled failure demo task up to max 3 attempts
    and moves task to dead_letter queue state after 3 failures.
    """
    await task_queue.clear()
    worker = TaskWorker(concurrency=1)

    # 1. Enqueue controlled failure task with max_attempts=3
    task_data = await task_queue.enqueue_task(
        task_type="controlled_failure_demo",
        payload={"demo": True},
        max_attempts=3
    )
    task_id = task_data["task_id"]

    # 2. First execution claim & process -> fails attempt 1, transitions to retrying
    claimed_1 = await task_queue.claim_next_task()
    assert claimed_1["task_id"] == task_id
    assert claimed_1["attempt_count"] == 1
    await worker.process_task(claimed_1)

    status_1 = await task_queue.get_task_status(task_id)
    assert status_1["status"] == "retrying"

    # 3. Second execution claim & process -> fails attempt 2, transitions to retrying
    claimed_2 = await task_queue.claim_next_task()
    assert claimed_2["task_id"] == task_id
    assert claimed_2["attempt_count"] == 2
    await worker.process_task(claimed_2)

    status_2 = await task_queue.get_task_status(task_id)
    assert status_2["status"] == "retrying"

    # 4. Third execution claim & process -> fails attempt 3 (max_attempts reached), transitions to dead_letter
    claimed_3 = await task_queue.claim_next_task()
    assert claimed_3["task_id"] == task_id
    assert claimed_3["attempt_count"] == 3
    await worker.process_task(claimed_3)

    status_3 = await task_queue.get_task_status(task_id)
    assert status_3["status"] == "dead_letter"
    assert "ControlledTaskFailureException" in status_3["error"]
