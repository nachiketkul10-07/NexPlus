"""
Phase 7 Alert Engine & Evaluation Pipeline Test Suite
Tests alert rule CRUD, threshold condition evaluation, deduplication, cooldowns, state transitions, security controls, and authorization.
"""
from datetime import datetime, timezone, timedelta
from uuid import UUID, uuid4
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.service import Service
from app.models.alert import AlertRule, Alert
from app.models.telemetry import TelemetryEvent, Metric
from app.schemas.user import UserRole
from app.services.alert_engine import AlertEngine


async def get_auth_headers(async_client: AsyncClient, email: str = "user@pulseops.io", password: str = "UserPass123!"):
    res = await async_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_alert_rule_crud_api(async_client: AsyncClient, db_session: AsyncSession):
    """Tests creating, fetching, updating, and deleting alert rules via API."""
    user_headers = await get_auth_headers(async_client, "user@pulseops.io", "UserPass123!")
    admin_headers = await get_auth_headers(async_client, "admin@pulseops.io", "AdminPass123!")

    demo_service_id = UUID("33333333-3333-3333-3333-333333333333")

    # 1. Create rule for demo service as user
    rule_data = {
        "name": "High HTTP 500 Rate",
        "metric_name": "error_rate",
        "operator": ">",
        "threshold": 0.05,
        "window_seconds": 120,
        "severity": "critical",
        "create_incident": True,
        "cooldown_seconds": 180,
        "enabled": True,
        "service_id": str(demo_service_id)
    }

    res = await async_client.post("/api/v1/alerts/rules", json=rule_data, headers=user_headers)
    assert res.status_code == 201, res.text
    created = res.json()
    rule_id = created["id"]
    assert created["name"] == "High HTTP 500 Rate"
    assert created["threshold"] == 0.05

    # 2. Get rule by ID
    res = await async_client.get(f"/api/v1/alerts/rules/{rule_id}", headers=user_headers)
    assert res.status_code == 200
    assert res.json()["id"] == rule_id

    # 3. List rules
    res = await async_client.get(f"/api/v1/alerts/rules?service_id={demo_service_id}", headers=user_headers)
    assert res.status_code == 200
    assert len(res.json()) >= 1

    # 4. Update rule
    res = await async_client.put(f"/api/v1/alerts/rules/{rule_id}", json={"threshold": 0.15, "enabled": False}, headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["threshold"] == 0.15
    assert res.json()["enabled"] is False

    # 5. Delete rule
    res = await async_client.delete(f"/api/v1/alerts/rules/{rule_id}", headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["rule_id"] == rule_id


@pytest.mark.asyncio
async def test_alert_rule_security_controls(async_client: AsyncClient):
    """Tests that standard users cannot create global rules or use invalid parameters."""
    user_headers = await get_auth_headers(async_client, "user@pulseops.io", "UserPass123!")

    # Standard user attempting to create a global rule (service_id=None) must be rejected with 403
    global_rule = {
        "name": "Global Error Alert",
        "metric_name": "error_rate",
        "operator": ">",
        "threshold": 0.1,
        "service_id": None
    }
    res = await async_client.post("/api/v1/alerts/rules", json=global_rule, headers=user_headers)
    assert res.status_code == 403

    # Invalid operator validation
    invalid_op_rule = {
        "name": "Bad Operator Rule",
        "metric_name": "latency",
        "operator": "INVALID",
        "threshold": 100.0,
    }
    res = await async_client.post("/api/v1/alerts/rules", json=invalid_op_rule, headers=user_headers)
    assert res.status_code == 422
@pytest.mark.asyncio
async def test_alert_engine_evaluation_and_deduplication(db_session: AsyncSession):
    """
    Tests alert evaluation against raw telemetry data:
    - Condition false -> no alert created
    - Condition true -> 1 alert created
    - Subsequent evaluation with condition still true -> alert updated (deduplicated!), count remains 1
    - Condition cleared -> active alert resolved
    - Cooldown window -> prevents immediate re-firing
    """
    now = datetime.now(timezone.utc)
    demo_service_id = UUID("33333333-3333-3333-3333-333333333333")

    # 1. Create alert rule: error_rate > 0.20
    rule = AlertRule(
        id=uuid4(),
        service_id=demo_service_id,
        name="High API Error Rate",
        metric_name="error_rate",
        operator=">",
        threshold=0.20,
        window_seconds=300,
        severity="critical",
        create_incident=True,
        cooldown_seconds=600,
        enabled=True
    )
    db_session.add(rule)
    await db_session.flush()

    engine = AlertEngine(db_session)

    # 2. Evaluate when no telemetry exists -> error_rate = 0.0 -> False
    summary1 = await engine.evaluate_rule(rule.id)
    assert summary1.alerts_triggered == 0
    assert summary1.alerts_updated == 0

    # 3. Add telemetry: 10 requests, 4 errors (error_rate = 0.40 > 0.20 threshold)
    for i in range(6):
        db_session.add(TelemetryEvent(
            service_id=demo_service_id,
            occurred_at=now - timedelta(seconds=10),
            status_code=200,
            duration_ms=120,
            outcome="success"
        ))
    for i in range(4):
        db_session.add(TelemetryEvent(
            service_id=demo_service_id,
            occurred_at=now - timedelta(seconds=5),
            status_code=500,
            duration_ms=450,
            outcome="error"
        ))
    await db_session.flush()

    # 4. Evaluate -> Condition true -> Alert created!
    summary2 = await engine.evaluate_rule(rule.id)
    assert summary2.alerts_triggered == 1
    assert summary2.alerts_updated == 0

    # Verify Alert record in DB
    alert_res = await engine.alert_repo.list_alerts(service_id=demo_service_id, status="active")
    assert len(alert_res) == 1
    created_alert = alert_res[0]
    assert created_alert.rule_id == rule.id
    assert created_alert.severity == "critical"
    assert created_alert.current_value == 0.4

    # 5. Evaluate again with condition still true -> DEDUPLICATION! Update existing alert, do not create second record
    summary3 = await engine.evaluate_rule(rule.id)
    assert summary3.alerts_triggered == 0
    assert summary3.alerts_updated == 1

    alert_res_after = await engine.alert_repo.list_alerts(service_id=demo_service_id, status="active")
    assert len(alert_res_after) == 1  # Still only 1 active alert!

    # 6. Condition clears: add 50 successful requests so error rate drops to < 0.20
    for i in range(50):
        db_session.add(TelemetryEvent(
            service_id=demo_service_id,
            occurred_at=now,
            status_code=200,
            duration_ms=50,
            outcome="success"
        ))
    await db_session.flush()

    summary4 = await engine.evaluate_rule(rule.id)
    assert summary4.alerts_resolved == 1

    active_alerts = await engine.alert_repo.list_alerts(service_id=demo_service_id, status="active")
    assert len(active_alerts) == 0

    resolved_alerts = await engine.alert_repo.list_alerts(service_id=demo_service_id, status="resolved")
    assert len(resolved_alerts) == 1


@pytest.mark.asyncio
async def test_alert_engine_latency_rule(db_session: AsyncSession):
    """Tests latency threshold rule evaluation."""
    now = datetime.now(timezone.utc)
    demo_service_id = UUID("33333333-3333-3333-3333-333333333333")

    rule = AlertRule(
        id=uuid4(),
        service_id=demo_service_id,
        name="High Response Latency",
        metric_name="avg_latency_ms",
        operator=">",
        threshold=500.0,
        window_seconds=180,
        severity="warning",
        enabled=True
    )
    db_session.add(rule)

    # Insert 3 events with high duration
    for d in [600, 700, 800]:
        db_session.add(TelemetryEvent(
            service_id=demo_service_id,
            occurred_at=now,
            status_code=200,
            duration_ms=d,
            outcome="success"
        ))
    await db_session.flush()

    engine = AlertEngine(db_session)
    summary = await engine.evaluate_rule(rule.id)
    assert summary.alerts_triggered == 1

    alerts = await engine.alert_repo.list_alerts(service_id=demo_service_id)
    assert len(alerts) == 1
    assert alerts[0].current_value == 700.0


@pytest.mark.asyncio
async def test_alert_cooldown_measured_from_resolved_at(db_session: AsyncSession):
    """Verifies that cooldown after alert resolution is measured strictly from resolved_at."""
    now = datetime.now(timezone.utc)
    demo_service_id = UUID("33333333-3333-3333-3333-333333333333")

    rule = AlertRule(
        id=uuid4(),
        service_id=demo_service_id,
        name="Cooldown Test Rule",
        metric_name="error_rate",
        operator=">",
        threshold=0.10,
        window_seconds=60,
        severity="critical",
        cooldown_seconds=300,
        enabled=True
    )
    db_session.add(rule)
    await db_session.flush()

    engine = AlertEngine(db_session)

    # 1. Insert telemetry causing condition to trigger
    for _ in range(5):
        db_session.add(TelemetryEvent(
            service_id=demo_service_id,
            occurred_at=now,
            status_code=500,
            duration_ms=100,
            outcome="error"
        ))
    await db_session.flush()

    # Trigger alert
    summary1 = await engine.evaluate_rule(rule.id)
    assert summary1.alerts_triggered == 1

    active_alerts = await engine.alert_repo.list_alerts(service_id=demo_service_id, status="active")
    assert len(active_alerts) == 1
    first_alert = active_alerts[0]

    # 2. Add success events to clear condition and resolve alert
    for _ in range(50):
        db_session.add(TelemetryEvent(
            service_id=demo_service_id,
            occurred_at=now,
            status_code=200,
            duration_ms=50,
            outcome="success"
        ))
    await db_session.flush()

    summary2 = await engine.evaluate_rule(rule.id)
    assert summary2.alerts_resolved == 1

    # Reload alert to verify resolved_at is set
    resolved_alert = await engine.alert_repo.get_alert_by_id(first_alert.id)
    assert resolved_alert.status == "resolved"
    assert resolved_alert.resolved_at is not None

    # 3. Add failing telemetry again immediately (condition is true, but inside cooldown period measured from resolved_at)
    for _ in range(20):
        db_session.add(TelemetryEvent(
            service_id=demo_service_id,
            occurred_at=now,
            status_code=500,
            duration_ms=200,
            outcome="error"
        ))
    await db_session.flush()

    summary3 = await engine.evaluate_rule(rule.id)
    # Should NOT trigger a new alert because cooldown (300s) from resolved_at has not elapsed!
    assert summary3.alerts_triggered == 0

    # 4. Simulate passage of time past cooldown period by adjusting resolved_at to 301 seconds ago
    resolved_alert.resolved_at = now - timedelta(seconds=301)
    await db_session.flush()

    summary4 = await engine.evaluate_rule(rule.id)
    # Now cooldown from resolved_at has expired -> NEW alert is triggered!
    assert summary4.alerts_triggered == 1

    all_alerts = await engine.alert_repo.list_alerts(service_id=demo_service_id)
    assert len(all_alerts) == 2

