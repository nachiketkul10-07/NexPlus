"""
Async Worker Process Engine
Consumes tasks from TaskQueue, executes registered task handlers, manages retries up to 3 max attempts,
moves unrecoverable failures to Dead-Letter Queue (DLQ), maintains worker heartbeat, and exits cleanly on shutdown.
"""
import asyncio
import signal
import uuid
import time
from typing import Optional

from app.core.logging import logger
from app.core.redis import init_redis, close_redis, get_redis_client
from app.workers.queue import task_queue
from app.workers.registry import get_task_handler, is_valid_task_type
from app.workers.retry import should_retry, MAX_TASK_RETRIES
from app.core.metrics import (
    BACKGROUND_TASKS_TOTAL,
    BACKGROUND_TASKS_FAILED_TOTAL,
    BACKGROUND_TASKS_DEAD_LETTERED_TOTAL,
    WORKER_TASK_DURATION_SECONDS,
    WORKER_ACTIVE_CONCURRENCY
)


WORKER_CONCURRENCY: int = 2
HEARTBEAT_INTERVAL: int = 5
WORKER_ID: str = f"worker_{uuid.uuid4().hex[:8]}"


class TaskWorker:
    """Asynchronous Worker Execution Engine."""

    def __init__(self, concurrency: int = WORKER_CONCURRENCY) -> None:
        self.concurrency = concurrency
        self.worker_id = WORKER_ID
        self.running = False
        self._shutdown_event = asyncio.Event()

    async def send_heartbeat(self) -> None:
        """Periodically writes heartbeat to Redis key with 15s TTL."""
        client = get_redis_client()
        if client is None:
            return
        heartbeat_key = f"pulseops:worker:heartbeat:{self.worker_id}"
        try:
            await client.setex(heartbeat_key, 15, str(int(time.time())))
        except Exception as exc:
            logger.error(f"Worker Heartbeat Failed | Reason: {exc}")

    async def process_task(self, task_data: dict) -> None:
        """Executes a single claimed task with retry and DLQ handling."""
        task_id = task_data["task_id"]
        task_type = task_data["task_type"]
        payload = task_data.get("payload", {})
        attempt_count = task_data.get("attempt_count", 1)
        max_attempts = task_data.get("max_attempts", MAX_TASK_RETRIES)

        logger.info(
            f"WORKER_EXECUTING_TASK | WorkerID: {self.worker_id} | TaskID: {task_id} | "
            f"Type: {task_type} | Attempt: {attempt_count}/{max_attempts}"
        )

        WORKER_ACTIVE_CONCURRENCY.inc()
        start_time = time.perf_counter()

        try:
            if not is_valid_task_type(task_type):
                raise ValueError(f"Invalid task type '{task_type}'")

            handler = get_task_handler(task_type)
            payload_copy = payload.copy() if isinstance(payload, dict) else {}
            payload_copy["attempt_number"] = attempt_count

            result = await handler(payload_copy)
            await task_queue.mark_completed(task_id, result)

            duration = time.perf_counter() - start_time
            BACKGROUND_TASKS_TOTAL.labels(task_type=task_type, outcome="completed").inc()
            WORKER_TASK_DURATION_SECONDS.labels(task_type=task_type).observe(duration)
        except Exception as exc:
            duration = time.perf_counter() - start_time
            BACKGROUND_TASKS_FAILED_TOTAL.labels(task_type=task_type).inc()
            error_msg = f"{exc.__class__.__name__}: {str(exc)}"
            logger.error(
                f"WORKER_TASK_FAILED | TaskID: {task_id} | Attempt: {attempt_count}/{max_attempts} | "
                f"Error: {error_msg}"
            )

            if should_retry(attempt_count, max_attempts):
                await task_queue.mark_failed_and_retry(task_id, error_msg)
            else:
                await task_queue.move_to_dead_letter(task_id, error_msg)
                BACKGROUND_TASKS_DEAD_LETTERED_TOTAL.labels(task_type=task_type).inc()
        finally:
            WORKER_ACTIVE_CONCURRENCY.dec()

    async def worker_loop(self) -> None:
        """Main asynchronous loop pulling and processing tasks."""
        logger.info(f"Task Worker Loop Started | WorkerID: {self.worker_id} | Concurrency: {self.concurrency}")
        while self.running:
            try:
                await self.send_heartbeat()
                task_data = await task_queue.claim_next_task()
                if task_data:
                    await self.process_task(task_data)
                else:
                    await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"Worker Loop Unexpected Error | Error: {exc}")
                await asyncio.sleep(1.0)

    async def start(self) -> None:
        """Starts worker heartbeat and consumer loop."""
        self.running = True
        logger.info(f"Starting Task Worker | WorkerID: {self.worker_id}")
        workers = [asyncio.create_task(self.worker_loop()) for _ in range(self.concurrency)]
        await self._shutdown_event.wait()

        self.running = False
        for w in workers:
            w.cancel()
        await asyncio.gather(*workers, return_exceptions=True)
        logger.info(f"Task Worker Stopped Cleanly | WorkerID: {self.worker_id}")

    def stop(self) -> None:
        """Signals worker to shutdown gracefully."""
        logger.info(f"Shutdown Signal Received | Stopping Worker: {self.worker_id}")
        self.running = False
        self._shutdown_event.set()


async def main() -> None:
    """Worker Command Line Entry Point."""
    await init_redis()
    worker = TaskWorker(concurrency=WORKER_CONCURRENCY)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, worker.stop)
        except NotImplementedError:
            pass

    try:
        await worker.start()
    finally:
        await close_redis()


if __name__ == "__main__":
    asyncio.run(main())
