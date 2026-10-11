from datetime import datetime, timezone
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert, AlertRule
from app.models.incident import Incident


async def _auth(async_client: AsyncClient, email: str, password: str) -> dict[str, str]:
    response = await async_client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.asyncio
async def test_service_and_telemetry_reads_are_limited_to_the_owner(async_client: AsyncClient):
    owner_headers = await _auth(async_client, "user@pulseops.io", "UserPass123!")
    other_headers = await _auth(async_client, "second@pulseops.io", "SecondPass123!")

    created = await async_client.post(
        "/api/v1/services",
        headers=owner_headers,
        json={"identifier": "tenant-isolation-app", "name": "Tenant Isolation App"},
    )
    assert created.status_code == 201
    service = created.json()
    ingest_headers = {"X-Ingest-Key": service["ingest_key"]}

    for endpoint, payload in (
        ("events", {"method": "GET", "endpoint": "/health", "status_code": 200}),
        ("metrics", {"metric_name": "queue_depth", "value": 3}),
        ("logs", {"level": "INFO", "message": "owner-only sample"}),
    ):
        accepted = await async_client.post(
            f"/api/v1/telemetry/{endpoint}", headers=ingest_headers, json=payload
        )
        assert accepted.status_code == 202

    owner_services = await async_client.get("/api/v1/services", headers=owner_headers)
    other_services = await async_client.get("/api/v1/services", headers=other_headers)
    assert service["id"] in {item["id"] for item in owner_services.json()}
    assert service["id"] not in {item["id"] for item in other_services.json()}

    hidden_detail = await async_client.get(
        f"/api/v1/services/{service['id']}", headers=other_headers
    )
    assert hidden_detail.status_code == 404

    for endpoint in ("events", "metrics", "logs"):
        owner_query = await async_client.get(
            f"/api/v1/telemetry/{endpoint}?service_id={service['id']}",
            headers=owner_headers,
        )
        hidden_query = await async_client.get(
            f"/api/v1/telemetry/{endpoint}", headers=other_headers
        )
        explicit_hidden_query = await async_client.get(
            f"/api/v1/telemetry/{endpoint}?service_id={service['id']}",
            headers=other_headers,
        )
        assert owner_query.status_code == 200 and owner_query.json()
        assert hidden_query.status_code == 200 and hidden_query.json() == []
        assert explicit_hidden_query.status_code == 404


@pytest.mark.asyncio
async def test_incidents_alerts_and_rules_are_limited_to_the_service_owner(
    async_client: AsyncClient, db_session: AsyncSession
):
    owner_headers = await _auth(async_client, "user@pulseops.io", "UserPass123!")
    other_headers = await _auth(async_client, "second@pulseops.io", "SecondPass123!")
    created = await async_client.post(
        "/api/v1/services",
        headers=owner_headers,
        json={"identifier": "tenant-ops-app", "name": "Tenant Ops App"},
    )
    assert created.status_code == 201
    service_id = UUID(created.json()["id"])

    rule = AlertRule(
        service_id=service_id,
        name="Owner only rule",
        metric_name="error_rate",
        operator=">",
        threshold=0.1,
        severity="warning",
    )
    db_session.add(rule)
    await db_session.flush()
    alert = Alert(
        rule_id=rule.id,
        service_id=service_id,
        status="active",
        severity="warning",
        current_value=0.2,
        threshold_value=0.1,
        triggered_at=datetime.now(timezone.utc),
        last_seen_at=datetime.now(timezone.utc),
    )
    db_session.add(alert)
    await db_session.flush()
    incident = Incident(
        service_id=service_id,
        alert_id=alert.id,
        title="Owner only incident",
        severity="warning",
        status="open",
    )
    db_session.add(incident)
    await db_session.flush()

    assert (await async_client.get(f"/api/v1/alerts/rules/{rule.id}", headers=owner_headers)).status_code == 200
    assert (await async_client.get(f"/api/v1/alerts/rules/{rule.id}", headers=other_headers)).status_code == 404
    assert (await async_client.get(f"/api/v1/alerts/{alert.id}", headers=owner_headers)).status_code == 200
    assert (await async_client.get(f"/api/v1/alerts/{alert.id}", headers=other_headers)).status_code == 404
    assert (await async_client.get(f"/api/v1/incidents/{incident.id}", headers=owner_headers)).status_code == 200
    assert (await async_client.get(f"/api/v1/incidents/{incident.id}", headers=other_headers)).status_code == 404

    assigned_to_other = await async_client.patch(
        f"/api/v1/incidents/{incident.id}",
        headers=owner_headers,
        json={"assignee_user_id": "44444444-4444-4444-4444-444444444444"},
    )
    assert assigned_to_other.status_code == 403

    other_rules = await async_client.get("/api/v1/alerts/rules", headers=other_headers)
    other_alerts = await async_client.get("/api/v1/alerts", headers=other_headers)
    other_incidents = await async_client.get("/api/v1/incidents", headers=other_headers)
    assert rule.id.hex not in str(other_rules.json())
    assert alert.id.hex not in str(other_alerts.json())
    assert incident.id.hex not in str(other_incidents.json())
