"""
Redis-backed Task Queue & Metadata Store
Manages task enqueuing, processing state transitions, retries, and Dead-Letter Queue (DLQ).
Uses Redis lists and hashes for queue management with reliable processing recovery.
Includes in-memory fallback for local testing without Redis.
"""
import json
import time
import uuid
from typing import Dict, Any, Optional, List
from redis.exceptions import RedisError

from app.core.logging import logger
from app.core.redis import get_redis_client

PRIMARY_QUEUE = "pulseops:task_queue"
PROCESSING_QUEUE = "pulseops:task_processing"
DEAD_LETTER_QUEUE = "pulseops:task_dead_letter"
TASK_HASH_PREFIX = "pulseops:task:"
TASK_TTL_SECONDS = 86400  # 24 hours retention for task metadata


class TaskQueue:
    """Task Queue Manager using Redis operations."""

    def __init__(self) -> None:
        self._in_memory_tasks: Dict[str, Dict[str, Any]] = {}
        self._in_memory_queue: List[str] = []
        self._in_memory_dlq: List[str] = []

    async def enqueue_task(
        self,
        task_type: str,
        payload: Dict[str, Any],
        owner_id: Optional[str] = None,
        max_attempts: int = 3
    ) -> Dict[str, Any]:
        """Creates and enqueues a new background task."""
        task_id = str(uuid.uuid4())
        now = int(time.time())

        task_data = {
            "task_id": task_id,
            "task_type": task_type,
            "status": "queued",
            "created_at": now,
            "started_at": None,
            "completed_at": None,
            "attempt_count": 0,
            "max_attempts": max_attempts,
            "owner_id": owner_id or "system",
            "payload": payload,
            "error": None,
            "result": None
        }

        client = get_redis_client()
        if client is None:
            logger.error("Task enqueue failed: Redis durable queue is unavailable")
            raise RuntimeError("Durable task queue service is unavailable.")

        try:
            task_key = f"{TASK_HASH_PREFIX}{task_id}"
            hash_data = {
                k: json.dumps(v) if isinstance(v, (dict, list)) or v is None else str(v)
                for k, v in task_data.items()
            }
            await client.hset(task_key, mapping=hash_data)
            await client.expire(task_key, TASK_TTL_SECONDS)
            await client.rpush(PRIMARY_QUEUE, task_id)
            logger.info(f"TASK_ENQUEUED (Redis) | TaskID: {task_id} | Type: {task_type}")
            return task_data
        except (RedisError, OSError) as exc:
            logger.error(f"Redis Task Queue Error | Reason: {exc.__class__.__name__}")
            raise RuntimeError("Durable task queue service is unavailable.")

    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves task metadata by task_id."""
        client = get_redis_client()
        if client is not None:
            try:
                task_key = f"{TASK_HASH_PREFIX}{task_id}"
                hash_data = await client.hgetall(task_key)
                if hash_data:
                    parsed = {}
                    for k, v in hash_data.items():
                        if k in ("payload", "result") and v:
                            try:
                                parsed[k] = json.loads(v)
                            except Exception:
                                parsed[k] = v
                        elif k in ("created_at", "started_at", "completed_at", "attempt_count", "max_attempts") and v and v != "None":
                            try:
                                parsed[k] = int(v)
                            except Exception:
                                parsed[k] = None
                        elif v == "None":
                            parsed[k] = None
                        else:
                            parsed[k] = v
                    return parsed
            except (RedisError, OSError) as exc:
                logger.error(f"Redis Task Status Error | Reason: {exc.__class__.__name__}")

        return self._in_memory_tasks.get(task_id)

    async def claim_next_task(self) -> Optional[Dict[str, Any]]:
        """Reliably claims next task from PRIMARY_QUEUE to PROCESSING_QUEUE."""
        client = get_redis_client()
        if client is not None:
            try:
                task_id = await client.rpoplpush(PRIMARY_QUEUE, PROCESSING_QUEUE)
                if not task_id:
                    return None

                task_id = task_id.decode("utf-8") if isinstance(task_id, bytes) else str(task_id)
                task_data = await self.get_task_status(task_id)
                if not task_data:
                    await client.lrem(PROCESSING_QUEUE, 1, task_id)
                    return None

                now = int(time.time())
                attempt_count = task_data.get("attempt_count", 0) + 1

                task_key = f"{TASK_HASH_PREFIX}{task_id}"
                await client.hset(task_key, mapping={
                    "status": "processing",
                    "started_at": str(now),
                    "attempt_count": str(attempt_count)
                })

                task_data["status"] = "processing"
                task_data["started_at"] = now
                task_data["attempt_count"] = attempt_count
                return task_data
            except (RedisError, OSError) as exc:
                logger.error(f"Redis Claim Task Error | Reason: {exc.__class__.__name__}")

        if self._in_memory_queue:
            task_id = self._in_memory_queue.pop(0)
            task_data = self._in_memory_tasks.get(task_id)
            if task_data:
                now = int(time.time())
                task_data["status"] = "processing"
                task_data["started_at"] = now
                task_data["attempt_count"] = task_data.get("attempt_count", 0) + 1
                return task_data
        return None

    async def mark_completed(self, task_id: str, result: Dict[str, Any]) -> None:
        """Marks task as successfully completed and removes from PROCESSING_QUEUE."""
        now = int(time.time())
        client = get_redis_client()
        if client is not None:
            try:
                task_key = f"{TASK_HASH_PREFIX}{task_id}"
                await client.hset(task_key, mapping={
                    "status": "completed",
                    "completed_at": str(now),
                    "result": json.dumps(result)
                })
                await client.lrem(PROCESSING_QUEUE, 1, task_id)
                logger.info(f"TASK_COMPLETED (Redis) | TaskID: {task_id}")
                return
            except (RedisError, OSError) as exc:
                logger.error(f"Redis Mark Completed Error | Reason: {exc.__class__.__name__}")

        if task_id in self._in_memory_tasks:
            self._in_memory_tasks[task_id]["status"] = "completed"
            self._in_memory_tasks[task_id]["completed_at"] = now
            self._in_memory_tasks[task_id]["result"] = result

    async def mark_failed_and_retry(self, task_id: str, error_msg: str) -> None:
        """Marks task for retry and moves it back to PRIMARY_QUEUE."""
        client = get_redis_client()
        if client is not None:
            try:
                task_key = f"{TASK_HASH_PREFIX}{task_id}"
                await client.hset(task_key, mapping={
                    "status": "retrying",
                    "error": error_msg
                })
                await client.lrem(PROCESSING_QUEUE, 1, task_id)
                await client.rpush(PRIMARY_QUEUE, task_id)
                logger.warning(f"TASK_RETRYING (Redis) | TaskID: {task_id} | Error: {error_msg}")
                return
            except (RedisError, OSError) as exc:
                logger.error(f"Redis Retry Error | Reason: {exc.__class__.__name__}")

        if task_id in self._in_memory_tasks:
            self._in_memory_tasks[task_id]["status"] = "retrying"
            self._in_memory_tasks[task_id]["error"] = error_msg
            self._in_memory_queue.append(task_id)

    async def move_to_dead_letter(self, task_id: str, error_msg: str) -> None:
        """Permanently marks task as dead_letter and moves it to DEAD_LETTER_QUEUE."""
        now = int(time.time())
        client = get_redis_client()
        if client is not None:
            try:
                task_key = f"{TASK_HASH_PREFIX}{task_id}"
                await client.hset(task_key, mapping={
                    "status": "dead_letter",
                    "completed_at": str(now),
                    "error": error_msg
                })
                await client.lrem(PROCESSING_QUEUE, 1, task_id)
                await client.rpush(DEAD_LETTER_QUEUE, task_id)
                logger.error(f"TASK_DEAD_LETTER (Redis) | TaskID: {task_id} | Permanent Failure: {error_msg}")
                return
            except (RedisError, OSError) as exc:
                logger.error(f"Redis Move to DLQ Error | Reason: {exc.__class__.__name__}")

        if task_id in self._in_memory_tasks:
            self._in_memory_tasks[task_id]["status"] = "dead_letter"
            self._in_memory_tasks[task_id]["completed_at"] = now
            self._in_memory_tasks[task_id]["error"] = error_msg
            self._in_memory_dlq.append(task_id)

    async def clear(self) -> None:
        """Clears in-memory and Redis queues for testing."""
        self._in_memory_tasks.clear()
        self._in_memory_queue.clear()
        self._in_memory_dlq.clear()
        client = get_redis_client()
        if client is not None:
            try:
                await client.delete(PRIMARY_QUEUE, PROCESSING_QUEUE, DEAD_LETTER_QUEUE)
                keys = await client.keys(f"{TASK_HASH_PREFIX}*")
                if keys:
                    await client.delete(*keys)
            except Exception:
                pass


task_queue = TaskQueue()
