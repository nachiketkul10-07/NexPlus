"""
Task Retry & Failure Handling Helper
Defines retry limits and failure classification logic.
"""
from typing import Dict, Any

MAX_TASK_RETRIES: int = 3


def should_retry(attempt_count: int, max_attempts: int = MAX_TASK_RETRIES) -> bool:
    """Determines whether a failed task should be retried."""
    return attempt_count < max_attempts
