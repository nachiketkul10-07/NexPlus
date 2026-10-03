"""
Alert & Incident Notification Task Module
Asynchronously dispatches alert/incident notifications to an internal logging and task result sink.
Prevents external credentials (SMTP, Twilio) from being required.
Excludes all sensitive fields (passwords, JWTs, secrets).
"""
from typing import Dict, Any
from app.core.logging import logger


async def run_alert_notification(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Dispatches alert or incident notifications.
    """
    alert_id = payload.get("alert_id", "unknown")
    rule_name = payload.get("rule_name", "Alert Notification")
    severity = payload.get("severity", "MEDIUM")
    message = payload.get("message", "Alert triggered")
    channel = payload.get("channel", "internal_sink")

    logger.info(
        f"NOTIFICATION_DISPATCHED | AlertID: {alert_id} | Rule: {rule_name} | "
        f"Severity: {severity} | Channel: {channel} | Message: {message}"
    )

    return {
        "alert_id": alert_id,
        "rule_name": rule_name,
        "severity": severity,
        "channel": channel,
        "dispatched": True,
        "sink": "internal_log_and_result_store"
    }
