"""
Task Registry Module
Maintains strict whitelist mapping of allowed task types to Python async callables.
Prevents task injection, arbitrary code execution, dynamic imports, and shell commands.
"""
from typing import Dict, Callable, Any
from app.workers.tasks import (
    run_telemetry_enrichment,
    run_alert_notification,
    run_controlled_failure_demo
)

TASK_REGISTRY: Dict[str, Callable[[Dict[str, Any]], Any]] = {
    "telemetry_enrichment": run_telemetry_enrichment,
    "alert_notification": run_alert_notification,
    "controlled_failure_demo": run_controlled_failure_demo
}


def get_task_handler(task_type: str) -> Callable[[Dict[str, Any]], Any]:
    """
    Retrieves the handler callable for a validated task type.
    Raises KeyError if the task type is not registered.
    """
    if task_type not in TASK_REGISTRY:
        raise KeyError(f"Task type '{task_type}' is not registered in TASK_REGISTRY")
    return TASK_REGISTRY[task_type]


def is_valid_task_type(task_type: str) -> bool:
    """Returns True if task_type is present in TASK_REGISTRY."""
    return task_type in TASK_REGISTRY
