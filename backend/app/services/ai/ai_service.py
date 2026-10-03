"""
AI Analysis Orchestration Service for NexPulse
Manages incident context extraction, provider delegation, fallback execution, persistent storage, and operational metrics.
"""
import time
import logging
from typing import Dict, Any, Optional
from uuid import UUID, uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.core.config import settings
from app.core.metrics import (
    AI_ANALYSIS_REQUESTS_TOTAL,
    AI_ANALYSIS_DURATION_SECONDS,
    AI_ANALYSIS_FALLBACK_TOTAL,
)
from app.models.incident import Incident, AIAnalysis
from app.services.ai.context_builder import IncidentContextBuilder
from app.services.ai.groq_provider import GroqProvider
from app.services.ai.fallback_engine import FallbackEngine

logger = logging.getLogger("pulseops.ai")


class AIService:
    """Orchestrates AI analysis workflow for NexPulse incidents."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.context_builder = IncidentContextBuilder(session)
        self.groq_provider = GroqProvider()

    async def get_latest_analysis(self, incident_id: UUID) -> Optional[AIAnalysis]:
        """Retrieves latest cached AIAnalysis for an incident from database."""
        stmt = (
            select(AIAnalysis)
            .where(AIAnalysis.incident_id == incident_id)
            .order_by(desc(AIAnalysis.created_at))
            .limit(1)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def analyze_incident(
        self,
        incident: Incident,
        force_refresh: bool = False
    ) -> AIAnalysis:
        """
        Executes advisory AI analysis for an incident.
        Uses cached result if available and force_refresh is False.
        Otherwise constructs sanitized context and delegates to Groq or Fallback engine.
        """
        # 1. Check cached analysis if force_refresh is False
        if not force_refresh:
            cached = await self.get_latest_analysis(incident.id)
            if cached:
                return cached

        start_time = time.time()
        provider_name = settings.AI_PROVIDER.lower()

        # 2. Build sanitized & bounded incident context
        context = await self.context_builder.build_context(incident)

        # 3. Determine execution path (AI Enabled vs Disabled)
        if not settings.AI_ENABLED:
            logger.info(f"AI_ENABLED is False. Executing fallback analysis for incident {incident.id}")
            analysis_dict = FallbackEngine.generate_fallback(context, reason="AI Assistant disabled by configuration")
            AI_ANALYSIS_FALLBACK_TOTAL.labels(reason="disabled").inc()
        elif provider_name == "groq":
            analysis_dict = await self.groq_provider.generate_analysis(context)
            if analysis_dict.get("status") == "fallback":
                AI_ANALYSIS_FALLBACK_TOTAL.labels(reason="provider_fallback").inc()
        else:
            # Unsupported provider fallback
            analysis_dict = FallbackEngine.generate_fallback(context, reason=f"Unsupported provider '{provider_name}'")
            AI_ANALYSIS_FALLBACK_TOTAL.labels(reason="unsupported_provider").inc()

        duration = time.time() - start_time
        analysis_status = analysis_dict.get("status", "generated")

        # 4. Record Prometheus operational metrics
        AI_ANALYSIS_REQUESTS_TOTAL.labels(provider=provider_name, status=analysis_status).inc()
        AI_ANALYSIS_DURATION_SECONDS.labels(provider=provider_name).observe(duration)

        # 5. Persist analysis snapshot to database
        evidence_snapshot = {
            "evidence": analysis_dict.get("evidence", []),
            "next_checks": analysis_dict.get("next_checks", []),
            "status": analysis_status,
        }

        # Convert possible causes to serializable format
        causes = [
            c if isinstance(c, str) else f"{c.get('statement', '')} [Confidence: {c.get('confidence', 'medium')}]"
            for c in analysis_dict.get("possible_causes", [])
        ]

        ai_analysis_record = AIAnalysis(
            id=uuid4(),
            incident_id=incident.id,
            model_name=settings.AI_MODEL if analysis_status == "generated" else "deterministic-fallback",
            prompt_version="v1",
            evidence_snapshot=evidence_snapshot,
            summary=analysis_dict.get("summary", "Analysis unavailable."),
            possible_factors=causes,
            limitations_note=analysis_dict.get("limitations_note", "Advisory analysis only."),
        )

        self.session.add(ai_analysis_record)
        await self.session.commit()
        await self.session.refresh(ai_analysis_record)

        return ai_analysis_record
