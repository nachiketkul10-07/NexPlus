from types import SimpleNamespace

from app.services.ai.ai_service import analysis_matches_current_incident


def test_cached_analysis_must_match_current_incident_state_and_ai_mode():
    incident = SimpleNamespace(status="resolved")
    cached = SimpleNamespace(evidence_snapshot={"incident_status": "open", "analysis_mode": "provider:groq:model-a"})

    assert not analysis_matches_current_incident(cached, incident, True, "groq", "model-a")
    cached.evidence_snapshot = {"incident_status": "resolved", "analysis_mode": "provider:groq:model-a"}
    assert analysis_matches_current_incident(cached, incident, True, "groq", "model-a")
    assert not analysis_matches_current_incident(cached, incident, True, "groq", "model-b")
    assert not analysis_matches_current_incident(cached, incident, False, "groq", "model-a")
    cached.evidence_snapshot = {"incident_status": "resolved", "analysis_mode": "deterministic-fallback"}
    assert analysis_matches_current_incident(cached, incident, False, "groq", "model-a")
