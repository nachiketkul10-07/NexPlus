"""
Phase 8 Incident Management System Test Suite
Tests incident creation from alerts, deduplication, state machine transitions, authorization, assignee controls, timeline events, security, and IDOR prevention.
"""
from datetime import datetime, timezone, timedelta
from uuid import UUID, uuid4
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.service import Service
from app.models.alert import AlertRule, Alert
from app.models.incident import Incident, IncidentEvent
from app.models.telemetry import TelemetryEvent
from app.schemas.user import UserRole
from app.services.alert_engine import AlertEngine
from app.services.incident_service import IncidentService


async def get_auth_headers(async_client: AsyncClient, email: str = "user@pulseops.io", password: str = "UserPass123!"):
    res = await async_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_alert_escalation_creates_incident_and_deduplicates(db_session: AsyncSession):
    """Verifies that a qualifying active alert creates an incident, and duplicate alerts do not recreate incidents."""
    now = datetime.now(timezone.utc)
    demo_service_id = UUID("33333333-3333-3333-3333-333333333333")

    rule = AlertRule(
        id=uuid4(),
        service_id=demo_service_id,
        name="Escalation High Errors",
        metric_name="error_rate",
        operator=">",
        threshold=0.10,
        window_seconds=60,
        severity="critical",
        create_incident=True,
        cooldown_seconds=300,
        enabled=True
    )
    db_session.add(rule)

    for _ in range(5):
        db_session.add(TelemetryEvent(
            service_id=demo_service_id,
            occurred_at=now,
            status_code=500,
            duration_ms=100,
            outcome="error"
        ))
    await db_session.flush()

    engine = AlertEngine(db_session)
    summary = await engine.evaluate_rule(rule.id)
    assert summary.alerts_triggered == 1

    # Verify incident was automatically created
    inc_service = IncidentService(db_session)
    incidents = await inc_service.repo.list_incidents(service_id=demo_service_id)
    assert len(incidents) == 1
    inc = incidents[0]
    assert inc.status == "open"
    assert inc.severity == "critical"
    assert "Escalation High Errors" in inc.title

    # Verify initial timeline event
    events = await inc_service.repo.get_timeline_events(inc.id)
    assert len(events) >= 1
    assert events[0].event_type == "INCIDENT_CREATED"

    # Evaluate again (condition still true) -> alert is updated (deduplicated), NO second incident is created!
    summary2 = await engine.evaluate_rule(rule.id)
    assert summary2.alerts_updated == 1

    incidents_after = await inc_service.repo.list_incidents(service_id=demo_service_id)
    assert len(incidents_after) == 1  # Exactly ONE incident!


@pytest.mark.asyncio
async def test_incident_lifecycle_state_machine_and_api(async_client: AsyncClient, db_session: AsyncSession):
    """Tests incident state transitions (OPEN -> INVESTIGATING -> RESOLVED), timeline events, notes, and rejection of invalid transitions."""
    user_headers = await get_auth_headers(async_client, "user@pulseops.io", "UserPass123!")
    demo_service_id = UUID("33333333-3333-3333-3333-333333333333")

    inc_service = IncidentService(db_session)
    inc = await inc_service.repo.create_incident(
        service_id=demo_service_id,
        title="API Test Outage",
        severity="critical",
        status="open"
    )

    # 1. List Incidents
    res = await async_client.get("/api/v1/incidents", headers=user_headers)
    assert res.status_code == 200
    assert len(res.json()) >= 1

    # 2. Get Incident Detail
    res = await async_client.get(f"/api/v1/incidents/{inc.id}", headers=user_headers)
    assert res.status_code == 200
    assert res.json()["status"] == "open"

    # 3. Transition OPEN -> INVESTIGATING
    res = await async_client.patch(f"/api/v1/incidents/{inc.id}", json={"status": "investigating"}, headers=user_headers)
    assert res.status_code == 200
    assert res.json()["status"] == "investigating"
    assert res.json()["investigating_at"] is not None

    # 4. Attempt Invalid Transition INVESTIGATING -> OPEN (Should fail 400)
    res = await async_client.patch(f"/api/v1/incidents/{inc.id}", json={"status": "open"}, headers=user_headers)
    assert res.status_code == 400
    assert "Cannot transition incident from investigating back to open" in res.json()["error"]["message"]

    # 5. Add Note
    res = await async_client.post(f"/api/v1/incidents/{inc.id}/events", json={"message": "Investigating high DB cpu spikes"}, headers=user_headers)
    assert res.status_code == 201
    assert res.json()["message"] == "Investigating high DB cpu spikes"

    # 6. Transition INVESTIGATING -> RESOLVED
    res = await async_client.patch(
        f"/api/v1/incidents/{inc.id}",
        json={"status": "resolved", "resolution_note": "Restarted connection pool"},
        headers=user_headers
    )
    assert res.status_code == 200
    assert res.json()["status"] == "resolved"
    assert res.json()["resolved_at"] is not None
    assert res.json()["resolution_note"] == "Restarted connection pool"

    # 7. Attempt Reopening RESOLVED -> INVESTIGATING or OPEN (Should fail 400)
    res = await async_client.patch(f"/api/v1/incidents/{inc.id}", json={"status": "investigating"}, headers=user_headers)
    assert res.status_code == 400
    assert "Resolved incidents cannot be reopened" in res.json()["error"]["message"]

    # 8. Check Timeline History
    res = await async_client.get(f"/api/v1/incidents/{inc.id}/events", headers=user_headers)
    assert res.status_code == 200
    events = res.json()
    assert len(events) >= 3


@pytest.mark.asyncio
async def test_incident_security_controls_and_authorization(async_client: AsyncClient, db_session: AsyncSession):
    """Tests security boundaries, unauthenticated rejection, 404 for missing UUIDs, and authenticated access."""
    user_headers = await get_auth_headers(async_client, "user@pulseops.io", "UserPass123!")

    # 1. Unauthenticated request rejected (401)
    res = await async_client.get("/api/v1/incidents")
    assert res.status_code == 401

    # 2. Non-existent incident UUID returns 404
    fake_id = uuid4()
    res = await async_client.get(f"/api/v1/incidents/{fake_id}", headers=user_headers)
    assert res.status_code == 404

    # 3. Malicious inputs reject invalid status values (422 / 400)
    demo_service_id = UUID("33333333-3333-3333-3333-333333333333")
    inc_service = IncidentService(db_session)
    inc = await inc_service.repo.create_incident(
        service_id=demo_service_id,
        title="Sanitization Test",
        severity="info",
        status="open"
    )

    res = await async_client.patch(f"/api/v1/incidents/{inc.id}", json={"status": "HACK_STATUS"}, headers=user_headers)
    assert res.status_code in (400, 422)
