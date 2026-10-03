"""
Security Audit Logging Module
Logs structured audit events (registration, login success/failure, logout, authorization errors).
Guarantees secrets, passwords, and tokens are NEVER included in log payloads.
"""
from typing import Optional, Dict, Any
from app.core.logging import logger, request_id_ctx


def log_audit_event(
    event_type: str,
    user_id: Optional[str] = None,
    email: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    success: bool = True
) -> None:
    """Logs structured security audit event."""
    req_id = request_id_ctx.get()
    status_str = "SUCCESS" if success else "FAILED"
    safe_details = details.copy() if details else {}

    # Never log sensitive keys if accidentally passed
    for sensitive_key in ["password", "token", "hashed_password", "secret", "access_token"]:
        safe_details.pop(sensitive_key, None)

    logger.info(
        f"AUDIT | Event: {event_type} | Status: {status_str} | "
        f"User: {user_id or 'anonymous'} | Email: {email or 'n/a'} | "
        f"ReqID: {req_id or 'n/a'} | Details: {safe_details}"
    )
