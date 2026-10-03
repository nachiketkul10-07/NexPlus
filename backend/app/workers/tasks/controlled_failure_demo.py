"""
Controlled Failure Demo Task Module
Fails deterministically to demonstrate worker retry logic and Dead-Letter Queue (DLQ) transition.
"""
from typing import Dict, Any
from app.core.logging import logger


class ControlledTaskFailureException(Exception):
    """Exception raised intentionally by the controlled failure task."""
    pass


async def run_controlled_failure_demo(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Controlled failure demonstration task.
    Always raises ControlledTaskFailureException to force execution retries up to max_attempts.
    """
    attempt = payload.get("attempt_number", 1)
    logger.warning(f"CONTROLLED_FAILURE_DEMO | Attempting task execution (Expected Failure) | Attempt: {attempt}")
    raise ControlledTaskFailureException(
        "Deterministic task failure for retry and dead-letter queue testing"
    )
