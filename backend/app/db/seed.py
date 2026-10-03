"""
Development Seed Data Script for PulseOps
Idempotently seeds initial administrative users, default operator user,
monitored demo service, and standard alert rules.

NOTE: Seed credentials are for local development ONLY.
Never deploy development seed credentials to production environments.
"""
import os
import asyncio
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, hash_ingest_key
from app.core.config import settings
from app.db.session import AsyncSessionLocal, engine
from app.db.init_db import init_db
from app.models.user import User
from app.models.service import Service
from app.models.alert import AlertRule
from app.models.incident import Incident
from app.schemas.user import UserRole


async def seed_development_data(session: AsyncSession) -> None:
    """Seeds default initial users, service, and alert rules if they do not already exist."""

    # 1. Admin User
    admin_email = os.getenv("SEED_ADMIN_EMAIL", "admin@pulseops.io").lower().strip()
    admin_pwd = os.getenv("SEED_ADMIN_PASSWORD", "AdminPass123!")

    stmt = select(User).where(User.email == admin_email)
    res = await session.execute(stmt)
    existing_admin = res.scalars().first()

    if not existing_admin:
        admin_user = User(
            id=UUID("11111111-1111-1111-1111-111111111111"),
            email=admin_email,
            full_name="System Administrator",
            hashed_password=hash_password(admin_pwd),
            role=UserRole.ADMIN.value,
            is_active=True
        )
        session.add(admin_user)
        print(f"[SEED] Created Admin user: {admin_email}")

    # 2. Standard Operator User
    user_email = os.getenv("SEED_USER_EMAIL", "user@pulseops.io").lower().strip()
    user_pwd = os.getenv("SEED_USER_PASSWORD", "UserPass123!")

    stmt = select(User).where(User.email == user_email)
    res = await session.execute(stmt)
    existing_user = res.scalars().first()

    if not existing_user:
        standard_user = User(
            id=UUID("22222222-2222-2222-2222-222222222222"),
            email=user_email,
            full_name="Standard Operator",
            hashed_password=hash_password(user_pwd),
            role=UserRole.USER.value,
            is_active=True
        )
        session.add(standard_user)
        print(f"[SEED] Created Standard Operator user: {user_email}")

    # 3. Default Demo Service
    service_identifier = "demo-app"
    dev_ingest_key = os.getenv("SEED_DEMO_INGEST_KEY", "pik_dev_demo_app_secret_key_12345")
    dev_ingest_hash = hash_ingest_key(dev_ingest_key)

    stmt = select(Service).where(Service.identifier == service_identifier)
    res = await session.execute(stmt)
    existing_service = res.scalars().first()

    if not existing_service:
        demo_service = Service(
            id=UUID("33333333-3333-3333-3333-333333333333"),
            identifier=service_identifier,
            name="Demo Application",
            environment="development",
            base_url="http://demo-app:8000",
            health_path="/api/health",
            status="healthy",
            ingest_key_hash=dev_ingest_hash,
            last_seen_at=datetime.now(timezone.utc)
        )
        session.add(demo_service)
        print(f"[SEED] Created Monitored Service: {service_identifier}")
        demo_service_id = demo_service.id
    else:
        existing_service.ingest_key_hash = dev_ingest_hash
        demo_service_id = existing_service.id

    # 4. Default Alert Rules
    rules_to_seed = [
        {
            "id": UUID("44444444-4444-4444-4444-444444444441"),
            "name": "High error rate",
            "metric_name": "error_rate",
            "operator": ">",
            "threshold": 0.10,
            "window_seconds": 60,
            "severity": "critical",
            "create_incident": True,
            "cooldown_seconds": 300,
            "enabled": True,
        },
        {
            "id": UUID("44444444-4444-4444-4444-444444444442"),
            "name": "High latency",
            "metric_name": "avg_latency_ms",
            "operator": ">",
            "threshold": 1000.0,
            "window_seconds": 60,
            "severity": "warning",
            "create_incident": True,
            "cooldown_seconds": 300,
            "enabled": True,
        },
        {
            "id": UUID("44444444-4444-4444-4444-444444444443"),
            "name": "Service unhealthy",
            "metric_name": "service_health",
            "operator": "=",
            "threshold": 0.0,
            "window_seconds": 60,
            "severity": "critical",
            "create_incident": True,
            "cooldown_seconds": 300,
            "enabled": True,
        },
    ]

    for rule_data in rules_to_seed:
        stmt = select(AlertRule).where(AlertRule.id == rule_data["id"])
        res = await session.execute(stmt)
        if not res.scalars().first():
            rule = AlertRule(
                id=rule_data["id"],
                service_id=demo_service_id,
                name=rule_data["name"],
                metric_name=rule_data["metric_name"],
                operator=rule_data["operator"],
                threshold=rule_data["threshold"],
                window_seconds=rule_data["window_seconds"],
                severity=rule_data["severity"],
                create_incident=rule_data["create_incident"],
                cooldown_seconds=rule_data["cooldown_seconds"],
                enabled=rule_data["enabled"],
            )
            session.add(rule)
            print(f"[SEED] Created Alert Rule: {rule_data['name']}")

    # 5. Default Sample Incidents for AI Assistant Evaluation
    sample_inc_id = UUID("55555555-5555-5555-5555-555555555555")
    stmt = select(Incident).where(Incident.id == sample_inc_id)
    res = await session.execute(stmt)
    if not res.scalars().first():
        sample_incident = Incident(
            id=sample_inc_id,
            service_id=demo_service_id,
            title="Database Connection Pool Exhaustion on /api/v1/checkout",
            description="High error rate detected (>15%) on /api/v1/checkout endpoint with elevated latency (1420ms). Connection pool starvation detected.",
            status="investigating",
            severity="critical",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        session.add(sample_incident)
        print(f"[SEED] Created Sample Incident: {sample_incident.title}")

    sample_inc_id_2 = UUID("55555555-5555-5555-5555-555555555556")
    stmt = select(Incident).where(Incident.id == sample_inc_id_2)
    res = await session.execute(stmt)
    if not res.scalars().first():
        sample_incident_2 = Incident(
            id=sample_inc_id_2,
            service_id=demo_service_id,
            title="High Latency Spike on Search Indexing Endpoint",
            description="Average response latency exceeded threshold (>1000ms) over sliding 60s window.",
            status="open",
            severity="warning",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        session.add(sample_incident_2)
        print(f"[SEED] Created Sample Incident: {sample_incident_2.title}")

    await session.commit()
    print("[SEED] Development seed completed successfully.")


async def main():
    if settings.is_production:
        raise RuntimeError("Development seed data is disabled in production.")
    await init_db()
    async with AsyncSessionLocal() as session:
        await seed_development_data(session)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
