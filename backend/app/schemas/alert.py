"""
Alert Rule and Triggered Alert Pydantic Schemas
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict, field_validator


class AlertRuleBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=120, description="Rule display name")
    metric_name: str = Field(..., min_length=1, max_length=80, description="Metric being evaluated")
    operator: str = Field(..., description="Comparison operator: >, >=, <, <=, =")
    threshold: float = Field(..., description="Configured numeric threshold")
    window_seconds: int = Field(default=60, ge=1, le=86400, description="Evaluation window in seconds")
    severity: str = Field(default="warning", description="Severity level: critical, warning, info")
    create_incident: bool = Field(default=True, description="Flag whether rule can initiate an incident")
    cooldown_seconds: int = Field(default=300, ge=0, le=86400, description="Deduplication cooldown window in seconds")
    enabled: bool = Field(default=True, description="Whether rule evaluation is active")
    service_id: Optional[UUID] = Field(default=None, description="Target service UUID or null for global evaluation")

    @field_validator("operator")
    @classmethod
    def validate_operator(cls, v: str) -> str:
        valid_ops = {">", ">=", "<", "<=", "="}
        if v not in valid_ops:
            raise ValueError(f"Invalid operator '{v}'. Must be one of {valid_ops}")
        return v

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str) -> str:
        valid_sevs = {"critical", "warning", "info"}
        if v.lower() not in valid_sevs:
            raise ValueError(f"Invalid severity '{v}'. Must be one of {valid_sevs}")
        return v.lower()


class AlertRuleCreate(AlertRuleBase):
    pass


class AlertRuleUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    metric_name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    operator: Optional[str] = None
    threshold: Optional[float] = None
    window_seconds: Optional[int] = Field(default=None, ge=1, le=86400)
    severity: Optional[str] = None
    create_incident: Optional[bool] = None
    cooldown_seconds: Optional[int] = Field(default=None, ge=0, le=86400)
    enabled: Optional[bool] = None
    service_id: Optional[UUID] = None

    @field_validator("operator")
    @classmethod
    def validate_operator(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            valid_ops = {">", ">=", "<", "<=", "="}
            if v not in valid_ops:
                raise ValueError(f"Invalid operator '{v}'. Must be one of {valid_ops}")
        return v

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            valid_sevs = {"critical", "warning", "info"}
            if v.lower() not in valid_sevs:
                raise ValueError(f"Invalid severity '{v}'. Must be one of {valid_sevs}")
            return v.lower()
        return v


class AlertRuleResponse(AlertRuleBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AlertResponse(BaseModel):
    id: UUID
    rule_id: UUID
    service_id: UUID
    status: str = Field(..., description="Alert status: active, resolved, suppressed")
    severity: str = Field(..., description="Severity level: critical, warning, info")
    current_value: Optional[float] = None
    threshold_value: Optional[float] = None
    triggered_at: datetime
    last_seen_at: datetime
    resolved_at: Optional[datetime] = None
    evidence: Optional[Dict[str, Any]] = None
    rule_name: Optional[str] = None
    service_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AlertEvaluationSummary(BaseModel):
    rules_evaluated: int
    alerts_triggered: int
    alerts_updated: int
    alerts_resolved: int
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)
