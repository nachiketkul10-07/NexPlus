"""
Pytest Fixtures for PulseOps Backend Database Tests
Sets up isolated async in-memory database engine, runs schema migrations/table creation,
seeds test user accounts, and overrides FastAPI get_db dependency.
"""
import asyncio
from datetime import datetime, timezone
from typing import AsyncGenerator
from uuid import UUID, uuid4
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.main import app
from app.core.config import settings
from app.core.security import hash_password, hash_ingest_key
from app.db.base import Base
from app.db.session import get_db
from app.models.user import User
from app.models.service import Service
from app.models.alert import AlertRule
from app.schemas.user import UserRole


# Enable SQLite Foreign Key Enforcement
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# Async test database engine
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False
)

TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)


@pytest.fixture(scope="session")
def event_loop():
    """Provides a session-scoped asyncio event loop for async fixtures."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def prepare_database():
    """
    Creates fresh database schema and seeds initial test users before each test.
    Drops all tables after test execution for strict test isolation.
    """
    from app.core.rate_limit import rate_limiter
    from app.core.brute_force import login_tracker
    await rate_limiter.clear()
    await login_tracker.clear()
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    # Seed initial test users and service
    async with TestingSessionLocal() as session:
        # 1. Admin User
        admin_user = User(
            id=UUID("11111111-1111-1111-1111-111111111111"),
            email="admin@pulseops.io",
            full_name="System Administrator",
            hashed_password=hash_password("AdminPass123!"),
            role=UserRole.ADMIN.value,
            is_active=True
        )
        session.add(admin_user)

        # 2. Standard User
        standard_user = User(
            id=UUID("22222222-2222-2222-2222-222222222222"),
            email="user@pulseops.io",
            full_name="Standard Operator",
            hashed_password=hash_password("UserPass123!"),
            role=UserRole.USER.value,
            is_active=True
        )
        session.add(standard_user)

        # 3. Monitored Demo Service
        demo_service = Service(
            id=UUID("33333333-3333-3333-3333-333333333333"),
            identifier="demo-app",
            name="Demo Application",
            environment="development",
            status="healthy",
            ingest_key_hash=hash_ingest_key("pik_dev_demo_app_secret_key_12345")
        )
        session.add(demo_service)

        await session.commit()

    # Override get_db dependency in FastAPI app
    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with TestingSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yields a database session bound to the active test database."""
    async with TestingSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP Client for testing endpoints against the test database."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client




