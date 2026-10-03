"""
Pydantic Schemas for NexPulse AI Incident Assistant
Defines DTOs for evidence items, hypotheses, structured analysis outputs, and API responses.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


class EvidenceItem(BaseModel):
    """Structured representation of an observed fact or telemetry data point."""
    source_type: str = Field(..., description="Evidence origin: alert, log, metric, telemetry, event, service")
    source_reference: Optional[str] = Field(None, description="Reference identifier, endpoint, or timestamp")
    observation: str = Field(..., description="Factual statement of observed metric or event condition")


class PossibleCause(BaseModel):
    """Advisory hypothesis explaining potential incident root causes."""
    statement: str = Field(..., description="Hypothesis describing potential cause")
    supporting_evidence: List[str] = Field(default_factory=list, description="Linked observations supporting hypothesis")
    confidence: str = Field("medium", pattern="^(high|medium|low)$", description="Confidence rating: high, medium, low")


class AIAnalysisBase(BaseModel):
    """Core advisory analysis structure."""
    summary: str = Field(..., description="Concise technical overview of incident context")
    evidence: List[EvidenceItem] = Field(default_factory=list, description="Factual observations extracted from telemetry")
    possible_causes: List[PossibleCause] = Field(default_factory=list, description="Advisory root cause hypotheses")
    next_checks: List[str] = Field(default_factory=list, description="Recommended diagnostic investigation steps")
    limitations_note: str = Field("AI analysis is advisory only. Verify with observed telemetry.", description="Operational disclaimer")
    status: str = Field("generated", pattern="^(generated|fallback|unavailable)$", description="Analysis status: generated, fallback, unavailable")


class AIAnalysisRequest(BaseModel):
    """Optional parameters for triggering AI analysis."""
    force_refresh: bool = Field(False, description="Whether to re-evaluate analysis if cached result exists")


class AIAnalysisResponse(AIAnalysisBase):
    """Complete DTO returned by the NexPulse AI Assistant API."""
    id: UUID
    incident_id: UUID
    provider: str = Field("groq", description="AI service provider")
    model_name: str = Field(..., description="Model name utilized for inference")
    prompt_version: str = Field("v1", description="System prompt version")
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
