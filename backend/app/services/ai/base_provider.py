"""
Abstract Base Provider for NexPulse AI Incident Assistant
"""
from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseAIProvider(ABC):
    """Abstract interface for AI inference providers (Groq, OpenAI, Mock, etc.)."""

    @abstractmethod
    async def generate_analysis(
        self,
        incident_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generates structured advisory analysis from incident context.
        Must return a dict conforming to AIAnalysisBase structure:
        {
            "summary": str,
            "evidence": List[Dict],
            "possible_causes": List[Dict],
            "next_checks": List[str],
            "limitations_note": str,
            "status": "generated" | "fallback" | "unavailable"
        }
        """
        pass
