"""
Comprehensive Database Integration Tests for PulseOps Phase 4
Validates SQLAlchemy 2.0 Async Session, PostgreSQL UserRepository, ORM Domain Models,
Constraints, Foreign Keys, Transaction Rollbacks, and Seed/Migration Integrity.
"""
from datetime import datetime, timezone
from uuid import uuid4, UUID
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.user_repository import PostgresUserRepository
from app.models.user import User
from app.models.service import Service
from app.models.telemetry import TelemetryEvent, Metric, LogEntry
from app.models.alert import AlertRule, Alert
from app.models.incident import Incident, IncidentEvent, AIAnalysis
from app.schemas.user import UserRegister, UserRole
from app.core.security import verify_password, hash_password


@pytest.mark.asyncio
async def test_user_creation_in_database(db_session: AsyncSession):
    """Test 1: Creates a new user record in PostgreSQL via PostgresUserRepository."""
    repo = PostgresUserRepository(db_session)
    user_in = UserRegister(
        email="newuser@pulseops.io",
        full_name="New Test User",
        password="SecurePass123!",
        role=UserRole.USER
    )
    user_db = await repo.create_user(user_in)

    assert user_db.id is not None
    assert user_db.email == "newuser@pulseops.io"
    assert user_db.full_name == "New Test User"
    assert user_db.role == UserRole.USER
    assert user_db.is_active is True
    assert verify_password("SecurePass123!", user_db.hashed_password) is True


@pytest.mark.asyncio
async def test_duplicate_email_rejection(db_session: AsyncSession):
    """Test 2: Verifies duplicate email registration is rejected by repository."""
    repo = PostgresUserRepository(db_session)
    user_in = UserRegister(
        email="duplicate@pulseops.io",
        full_name="Duplicate User",
        password="SecurePass123!",
        role=UserRole.USER
    )
    await repo.create_user(user_in)

    with pytest.raises(ValueError, match="already exists"):
        await repo.create_user(user_in)


@pytest.mark.asyncio
async def test_user_retrieval_by_email_and_id(db_session: AsyncSession):
    """Test 3: Retrieves user by email and UUID string."""
    repo = PostgresUserRepository(db_session)
    user_by_email = await repo.get_by_email("admin@pulseops.io")
    assert user_by_email is not None
    assert user_by_email.email == "admin@pulseops.io"
    assert user_by_email.role == UserRole.ADMIN

    user_by_id = await repo.get_by_id(str(user_by_email.id))
    assert user_by_id is not None
    assert user_by_id.email == "admin@pulseops.io"


@pytest.mark.asyncio
async def test_user_update(db_session: AsyncSession):
    """Test 4: Updates user fields in database."""
    stmt = select(User).where(User.email == "user@pulseops.io")
    res = await db_session.execute(stmt)
    user = res.scalars().first()
    assert user is not None

    user.full_name = "Updated Operator Name"
    user.last_login_at = datetime.now(timezone.utc)
    await db_session.flush()

    repo = PostgresUserRepository(db_session)
    updated_user = await repo.get_by_email("user@pulseops.io")
    assert updated_user.full_name == "Updated Operator Name"


@pytest.mark.asyncio
async def test_user_deactivation(db_session: AsyncSession):
    """Test 5: Deactivates user account without removing record."""
    stmt = select(User).where(User.email == "user@pulseops.io")
    res = await db_session.execute(stmt)
    user = res.scalars().first()
    user.is_active = False
    await db_session.flush()

    stmt_check = select(User).where(User.email == "user@pulseops.io")
    res_check = await db_session.execute(stmt_check)
    check_user = res_check.scalars().first()
    assert check_user.is_active is False


@pytest.mark.asyncio
async def test_password_hash_persistence(db_session: AsyncSession):
    """Test 6: Verifies Argon2id password hash is stored safely without exposing plaintext."""
    stmt = select(User).where(User.email == "admin@pulseops.io")
    res = await db_session.execute(stmt)
    user = res.scalars().first()

    assert user.hashed_password.startswith("$argon2")
    assert "AdminPass123!" not in user.hashed_password
    assert verify_password("AdminPass123!", user.hashed_password) is True


@pytest.mark.asyncio
async def test_role_retrieval(db_session: AsyncSession):
    """Test 9: Verifies role assignment and retrieval integrity."""
    repo = PostgresUserRepository(db_session)
    admin_user = await repo.get_by_email("admin@pulseops.io")
    standard_user = await repo.get_by_email("user@pulseops.io")

    assert admin_user.role == UserRole.ADMIN
    assert standard_user.role == UserRole.USER


@pytest.mark.asyncio
async def test_transaction_rollback_on_failure(db_session: AsyncSession):
    """Test 10: Ensures failed transactions roll back cleanly without polluting state."""
    db_session.add(User(
        id=uuid4(),
        email="rollback_test@pulseops.io",
        full_name="Rollback Test",
        hashed_password=hash_password("Pass123!"),
        role="user"
    ))
    await db_session.flush()

    # Intentionally duplicate email to trigger constraint failure
    db_session.add(User(
        id=uuid4(),
        email="rollback_test@pulseops.io",
        full_name="Duplicate Rollback",
        hashed_password=hash_password("Pass123!"),
        role="user"
    ))

    with pytest.raises(IntegrityError):
        await db_session.flush()

    await db_session.rollback()

    stmt = select(User).where(User.email == "rollback_test@pulseops.io")
    res = await db_session.execute(stmt)
    assert res.scalars().first() is None


@pytest.mark.asyncio
async def test_foreign_key_constraints(db_session: AsyncSession):
    """Test 11: Verifies foreign key constraints reject orphan child records."""
    non_existent_service_id = uuid4()
    orphan_event = TelemetryEvent(
        service_id=non_existent_service_id,
        occurred_at=datetime.now(timezone.utc),
        outcome="success"
    )
    db_session.add(orphan_event)

    with pytest.raises(IntegrityError):
        await db_session.flush()

    await db_session.rollback()


@pytest.mark.asyncio
async def test_all_domain_models_creation(db_session: AsyncSession):
    """Test 12: Verifies all 10 domain models can be instantiated and persisted in the schema."""
    # 1. Service
    service = Service(
        id=uuid4(),
        identifier="order-service",
        name="Order Processing Service",
        environment="production",
        status="healthy"
    )
    db_session.add(service)
    await db_session.flush()

    # 2. Telemetry Event
    telemetry = TelemetryEvent(
        service_id=service.id,
        occurred_at=datetime.now(timezone.utc),
        method="POST",
        endpoint="/api/v1/orders",
        status_code=200,
        duration_ms=45,
        outcome="success"
    )
    db_session.add(telemetry)

    # 3. Metric
    metric = Metric(
        service_id=service.id,
        metric_name="avg_latency_ms",
        value=45.0,
        window_seconds=60
    )
    db_session.add(metric)

    # 4. Log Entry
    log_entry = LogEntry(
        service_id=service.id,
        occurred_at=datetime.now(timezone.utc),
        level="INFO",
        message="Order processed successfully"
    )
    db_session.add(log_entry)

    # 5. Alert Rule
    rule = AlertRule(
        id=uuid4(),
        service_id=service.id,
        name="Order latency high",
        metric_name="avg_latency_ms",
        operator=">",
        threshold=500.0,
        window_seconds=60,
        severity="warning"
    )
    db_session.add(rule)
    await db_session.flush()

    # 6. Alert
    alert = Alert(
        id=uuid4(),
        rule_id=rule.id,
        service_id=service.id,
        status="active",
        severity="warning",
        current_value=550.0,
        threshold_value=500.0
    )
    db_session.add(alert)
    await db_session.flush()

    # 7. Incident
    incident = Incident(
        id=uuid4(),
        service_id=service.id,
        alert_id=alert.id,
        title="High order latency detected",
        severity="warning",
        status="open"
    )
    db_session.add(incident)
    await db_session.flush()

    # 8. Incident Event
    inc_event = IncidentEvent(
        incident_id=incident.id,
        event_type="state_change",
        message="Incident opened automatically"
    )
    db_session.add(inc_event)

    # 9. AI Analysis
    ai_analysis = AIAnalysis(
        id=uuid4(),
        incident_id=incident.id,
        model_name="gpt-4o-mini",
        prompt_version="v1",
        evidence_snapshot={"alert_id": str(alert.id)},
        summary="High latency observed due to database query spike",
        limitations_note="Advisory analysis only"
    )
    db_session.add(ai_analysis)

    await db_session.commit()

    # Query back incident to verify full ORM relationships
    stmt = select(Incident).where(Incident.id == incident.id)
    res = await db_session.execute(stmt)
    retrieved_inc = res.scalars().first()

    assert retrieved_inc is not None
    assert retrieved_inc.title == "High order latency detected"
    assert retrieved_inc.service.identifier == "order-service"

