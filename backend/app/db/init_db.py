"""Development database initialization; production schema is managed with Alembic."""
from app.core.config import settings
from app.core.logging import logger
from app.db.session import engine
from app.models.base import Base
from sqlalchemy import inspect

# Import model modules so SQLAlchemy metadata is populated for development setup.
from app.models import *  # noqa: F401,F403


async def init_db() -> None:
    """Create development tables; verify the production database without changing schema."""
    if settings.is_production:
        async with engine.connect() as connection:
            await connection.exec_driver_sql("SELECT 1")
        logger.info("Production database connection verified; schema migrations are managed by Alembic")
        return

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        existing_columns = await connection.run_sync(
            lambda sync_connection: {column["name"] for column in inspect(sync_connection).get_columns("services")}
        )
        if "repository_url" not in existing_columns:
            # create_all does not alter an existing SQLite development database.
            await connection.exec_driver_sql("ALTER TABLE services ADD COLUMN repository_url TEXT")
    logger.info("Development database tables initialized; demo accounts are created only by the explicit seed command")
