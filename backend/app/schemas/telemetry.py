"""
Pydantic Schemas for Telemetry, Metrics, and Log Ingestion
Defines strict request/response payloads, field validations, timestamp checks, and metadata sanitization.
"""
import json
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Union
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict, field_validator

SENSITIVE_KEYS = {
    "authorization", "auth", "token", "access_token", "refresh_token",
    "password", "secret", "api_key", "cookie", "set-cookie", "x-api-key",
    "ingest_key", "x-ingest-key"
}


def sanitize_metadata(meta: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Sanitizes metadata dictionary by scrubbing sensitive keys, limiting entry count,
    and enforcing payload size caps.
    """
    if not meta:
        return {}

    sanitized = {}
    for key, value in meta.items():
        if len(sanitized) >= 25:
            break  # Cap maximum label/key count

        key_str = str(key)
        if key_str.lower() in SENSITIVE_KEYS:
            sanitized[key_str] = "[REDACTED]"
        else:
            if isinstance(value, dict):
                sanitized[key_str] = sanitize_metadata(value)
            elif isinstance(value, str) and len(value) > 1024:
                sanitized[key_str] = value[:1024] + "...[TRUNCATED]"
            else:
                sanitized[key_str] = value

    serialized = json.dumps(sanitized, default=str)
    if len(serialized) > 10240:
        return {"error": "metadata_exceeded_size_limit"}

    return sanitized


def validate_timestamp_range(dt: Optional[datetime]) -> datetime:
    """
    Ensures datetime is timezone-aware and falls within an acceptable historical/future range.
    Range limit: Not older than 30 days, not further than 1 hour in the future.
    """
    if dt is None:
        return datetime.now(timezone.utc)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    max_past = now - timedelta(days=30)
    max_future = now + timedelta(hours=1)

    if dt < max_past or dt > max_future:
        raise ValueError("Timestamp out of acceptable range (must be within last 30 days and max 1h in future)")

    return dt


class TelemetryEventCreate(BaseModel):
    service_id: Optional[Union[UUID, str]] = Field(default=None)
    timestamp: Optional[datetime] = Field(default=None)
    request_id: Optional[str] = Field(default=None, max_length=64)
    method: Optional[str] = Field(default=None, max_length=10)
    endpoint: Optional[str] = Field(default=None, max_length=300)
    status_code: Optional[int] = Field(default=None, ge=100, le=599)
    response_time_ms: Optional[int] = Field(default=None, ge=0, le=3600000)
    duration_ms: Optional[int] = Field(default=None, ge=0, le=3600000)
    outcome: str = Field(default="success", max_length=24)
    error_type: Optional[str] = Field(default=None, max_length=160)
    error_message: Optional[str] = Field(default=None, max_length=2000)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

    @field_validator("timestamp")
    @classmethod
    def check_ts(cls, v: Optional[datetime]) -> datetime:
        return validate_timestamp_range(v)

    @field_validator("method")
    @classmethod
    def check_method(cls, v: Optional[str]) -> Optional[str]:
        if v:
            v_upper = v.upper().strip()
            if v_upper not in {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}:
                raise ValueError(f"Invalid HTTP method: {v}")
            return v_upper
        return v

    @field_validator("metadata")
    @classmethod
    def check_meta(cls, v: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        return sanitize_metadata(v)


class TelemetryEventResponse(BaseModel):
    id: int
    service_id: UUID
    request_id: Optional[str] = None
    occurred_at: datetime
    method: Optional[str] = None
    endpoint: Optional[str] = None
    status_code: Optional[int] = None
    duration_ms: Optional[int] = None
    outcome: str
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default=None, validation_alias="metadata_json")

    model_config = ConfigDict(from_attributes=True)



# ----------------------------------------------------------------------
# Metric Schemas
# ----------------------------------------------------------------------
class MetricCreate(BaseModel):
    service_id: Optional[Union[UUID, str]] = Field(default=None)
    metric_name: str = Field(..., min_length=2, max_length=80)
    value: float = Field(...)
    window_seconds: int = Field(default=60, ge=1, le=86400)
    timestamp: Optional[datetime] = Field(default=None)
    recorded_at: Optional[datetime] = Field(default=None)
    labels: Optional[Dict[str, str]] = Field(default_factory=dict)

    @field_validator("timestamp", "recorded_at")
    @classmethod
    def check_ts(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is None:
            return None
        return validate_timestamp_range(v)

    @field_validator("value")
    @classmethod
    def check_value(cls, v: float) -> float:
        import math
        if math.isnan(v) or math.isinf(v):
            raise ValueError("Metric value must be a finite float")
        return v

    @field_validator("labels")
    @classmethod
    def check_labels(cls, v: Optional[Dict[str, str]]) -> Dict[str, str]:
        if not v:
            return {}
        if len(v) > 10:
            raise ValueError("Maximum 10 label key-value pairs allowed")
        sanitized = {}
        for key, value in v.items():
            k_str = str(key)[:64]
            v_str = str(value)[:256]
            sanitized[k_str] = v_str
        return sanitized


class MetricResponse(BaseModel):
    id: int
    service_id: UUID
    metric_name: str
    value: float
    window_seconds: int
    recorded_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ----------------------------------------------------------------------
# Log Entry Schemas
# ----------------------------------------------------------------------
class LogCreate(BaseModel):
    service_id: Optional[Union[UUID, str]] = Field(default=None)
    timestamp: Optional[datetime] = Field(default=None)
    occurred_at: Optional[datetime] = Field(default=None)
    level: str = Field(default="INFO", max_length=16)
    message: str = Field(..., min_length=1, max_length=10000)
    request_id: Optional[str] = Field(default=None, max_length=64)
    trace_id: Optional[str] = Field(default=None, max_length=64)
    stack_trace: Optional[str] = Field(default=None, max_length=20000)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

    @field_validator("timestamp", "occurred_at")
    @classmethod
    def check_ts(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is None:
            return None
        return validate_timestamp_range(v)

    @field_validator("level")
    @classmethod
    def check_level(cls, v: str) -> str:
        v_upper = v.upper().strip()
        if v_upper not in {"DEBUG", "INFO", "WARN", "WARNING", "ERROR", "CRITICAL", "FATAL"}:
            raise ValueError(f"Invalid log level: {v}")
        return v_upper

    @field_validator("metadata")
    @classmethod
    def check_meta(cls, v: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        return sanitize_metadata(v)


class LogResponse(BaseModel):
    id: int
    service_id: UUID
    occurred_at: datetime
    level: str
    message: str
    request_id: Optional[str] = None
    trace_id: Optional[str] = None
    stack_trace: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default=None, validation_alias="metadata_json")

    model_config = ConfigDict(from_attributes=True)


# ----------------------------------------------------------------------
# Unified Batch Payload & Responses
# ----------------------------------------------------------------------
class UnifiedTelemetryBatchPayload(BaseModel):
    service_id: Optional[Union[UUID, str]] = Field(default=None)
    events: List[TelemetryEventCreate] = Field(default_factory=list)
    metrics: List[MetricCreate] = Field(default_factory=list)
    logs: List[LogCreate] = Field(default_factory=list)


class IngestionResponse(BaseModel):
    status: str = "accepted"
    accepted_count: int
    rejected_count: int = 0
    request_id: str
