"""
Database Engine and Async Session Factory Management
Configures SQLAlchemy 2.0 Async Engine and SessionMaker using settings.DATABASE_URL.
Supports automatic local SQLite fallback if PostgreSQL connection is unavailable.
"""
import os
import socket
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.logging import logger

db_url = settings.DATABASE_URL

# Auto-fallback: if postgresql URL fails to connect or in local dev without postgres running
if db_url.startswith("postgresql") and not settings.is_production:
    try:
        host_port = db_url.split("@")[-1].split("/")[0]
        host = host_port.split(":")[0]
        port = int(host_port.split(":")[1]) if ":" in host_port else 5432
        with socket.create_connection((host, port), timeout=1.0):
            pass
    except (OSError, ValueError, IndexError):
        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        db_path = os.path.join(backend_dir, "pulseops_dev.db").replace("\\", "/")
        logger.warning(f"PostgreSQL target at '{db_url}' is unreachable. Auto-switching to local SQLite engine at '{db_path}' for zero-dependency execution.")
        db_url = f"sqlite+aiosqlite:///{db_path}"

# Engine configuration arguments
engine_args = {}
if db_url.startswith("sqlite"):
    engine_args["connect_args"] = {"check_same_thread": False}

# Async SQLAlchemy Engine
engine = create_async_engine(
    db_url,
    echo=False,
    future=True,
    **engine_args
)

# Async Session Factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency yielding an async database session per request lifecycle.
    Automatically handles commit, rollback on failure, and session cleanup.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
