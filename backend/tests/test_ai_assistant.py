"""
Integration and Security Tests for NexPulse AI Incident Assistant
"""
import pytest
from unittest.mock import patch, AsyncMock
from uuid import UUID, uuid4
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.incident import Incident, AIAnalysis
from app.services.ai.context_builder import redact_secrets_from_text, sanitize_dict_secrets


async def get_auth_headers(async_client: AsyncClient, email: str = "user@pulseops.io", password: str = "UserPass123!") -> dict:
    """Helper to authenticate user and return Bearer token headers."""
    res = await async_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_secret_redaction_utilities():
    """Verify secret scrubbing regex filters passwords, JWTs, bearer tokens, and ingest keys."""
    raw_text = "Failed login with pass: SuperSecret123! and Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.signature and key pik_live_0123456789abcdef0123456789abcdef"
    redacted = redact_secrets_from_text(raw_text)

    assert "SuperSecret123!" not in redacted
    assert "pik_live_" not in redacted

    dictionary_data = {
        "user_email": "operator@nexpulse.io",
        "api_key": "secret_key_12345678",
        "nested": {
            "ingest_key": "pik_live_0123456789abcdef0123456789abcdef"
        }
    }
    sanitized = sanitize_dict_secrets(dictionary_data)
    assert sanitized["user_email"] == "operator@nexpulse.io"
    assert sanitized["api_key"] == "[REDACTED_SECRET]"


@pytest.mark.asyncio
async def test_ai_analysis_endpoint_disabled_triggers_fallback(async_client: AsyncClient, db_session: AsyncSession):
    """Verify fallback analysis is returned when AI_ENABLED is False."""
    user_headers = await get_auth_headers(async_client)
    demo_service_id = UUID("33333333-3333-3333-3333-333333333333")

    inc = Incident(
        id=uuid4(),
        service_id=demo_service_id,
        title="High Error Rate on Demo Service",
        description="Observed HTTP 500 error spikes with pass: Secret123!",
        severity="critical",
        status="open",
    )
    db_session.add(inc)
    await db_session.commit()

    with patch.object(settings, "AI_ENABLED", False):
        res = await async_client.post(f"/api/v1/incidents/{inc.id}/ai-analysis", json={"force_refresh": True}, headers=user_headers)
        assert res.status_code == 200
        data = res.json()

        assert data["incident_id"] == str(inc.id)
        assert data["status"] == "fallback"
        assert "summary" in data
        assert len(data["evidence"]) >= 1


@pytest.mark.asyncio
async def test_ai_analysis_endpoint_mocked_groq_success(async_client: AsyncClient, db_session: AsyncSession):
    """Verify successful Groq API mock response converts into structured AIAnalysisResponse."""
    user_headers = await get_auth_headers(async_client)
    demo_service_id = UUID("33333333-3333-3333-3333-333333333333")

    inc = Incident(
        id=uuid4(),
        service_id=demo_service_id,
        title="Latency Spike on Demo Service",
        description="Response duration exceeded 500ms threshold",
        severity="warning",
        status="open",
    )
    db_session.add(inc)
    await db_session.commit()

    mock_groq_output = {
        "summary": "Mocked Groq SRE summary: High HTTP 500 error rate detected on Demo Application.",
        "evidence": [
            {
                "source_type": "alert",
                "source_reference": "Rule: High HTTP 500 Rate",
                "observation": "Error rate crossed 0.10 threshold reaching 0.25."
            }
        ],
        "possible_causes": [
            {
                "statement": "Database connection pool exhaustion causing backend 500 errors.",
                "supporting_evidence": ["Rule: High HTTP 500 Rate"],
                "confidence": "high"
            }
        ],
        "next_checks": [
            "Check PostgreSQL connection pool active metrics.",
            "Verify Redis queue processing latency."
        ],
        "limitations_note": "Advisory mock output."
    }

    with patch.object(settings, "AI_ENABLED", True), \
         patch.object(settings, "AI_API_KEY", "gsk_mock_test_key_12345678"), \
         patch("app.services.ai.groq_provider.GroqProvider.generate_analysis", new_callable=AsyncMock) as mock_gen:
        
        mock_groq_output["status"] = "generated"
        mock_gen.return_value = mock_groq_output

        res = await async_client.post(f"/api/v1/incidents/{inc.id}/ai-analysis", json={"force_refresh": True}, headers=user_headers)
        assert res.status_code == 200
        data = res.json()

        assert data["status"] == "generated"
        assert "Mocked Groq SRE summary" in data["summary"]
        assert len(data["next_checks"]) == 2


@pytest.mark.asyncio
async def test_ai_analysis_security_and_authorization(async_client: AsyncClient):
    """Verify unauthenticated requests fail (401) and non-existent IDs return 404."""
    res = await async_client.post(f"/api/v1/incidents/{uuid4()}/ai-analysis")
    assert res.status_code == 401

    user_headers = await get_auth_headers(async_client)
    res = await async_client.post(f"/api/v1/incidents/{uuid4()}/ai-analysis", headers=user_headers)
    assert res.status_code == 404
