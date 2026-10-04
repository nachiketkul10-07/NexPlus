"""Create the first production administrator without exposing a password in argv."""

import asyncio
import getpass
import re

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import func, select

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal, engine
from app.models.user import User


def _validate_environment() -> None:
    """Refuse to create production admin accounts against a local/dev database."""
    database_url = settings.DATABASE_URL
    if not settings.is_production:
        raise SystemExit("Set ENVIRONMENT=production before bootstrapping the administrator.")
    if not database_url.startswith("postgresql+asyncpg://"):
        raise SystemExit("DATABASE_URL must use the asyncpg driver and point to production PostgreSQL.")
    if re.search(r"@(localhost|127\.0\.0\.1)(:|/)", database_url, re.IGNORECASE):
        raise SystemExit("Refusing to use a localhost database for production administrator setup.")


async def _create_first_admin(email: str, full_name: str, password: str) -> None:
    async with AsyncSessionLocal() as session:
        admin_count = await session.scalar(
            select(func.count()).select_from(User).where(User.role == "admin")
        )
        if admin_count:
            raise SystemExit("An administrator already exists; refusing to add or promote another account.")

        existing_user = await session.scalar(select(User.id).where(User.email == email))
        if existing_user:
            raise SystemExit("That email already belongs to an account; no changes were made.")

        session.add(
            User(
                email=email,
                full_name=full_name,
                hashed_password=hash_password(password),
                role="admin",
                is_active=True,
            )
        )
        await session.commit()


async def _close_engine() -> None:
    await engine.dispose()


def main() -> None:
    _validate_environment()
    try:
        email = str(TypeAdapter(EmailStr).validate_python(input("Administrator email: "))).lower().strip()
    except ValidationError as error:
        raise SystemExit("Enter a valid email address.") from error

    full_name = input("Administrator full name: ").strip()
    if not 2 <= len(full_name) <= 100:
        raise SystemExit("Full name must be between 2 and 100 characters.")

    password = getpass.getpass("Administrator password (14+ characters): ")
    if len(password) < 14 or len(password) > 128:
        raise SystemExit("Password must be between 14 and 128 characters.")
    if password != getpass.getpass("Confirm password: "):
        raise SystemExit("Passwords did not match.")

    try:
        asyncio.run(_create_first_admin(email, full_name, password))
    finally:
        asyncio.run(_close_engine())
    print("Production administrator created. Sign in through the deployed application.")


if __name__ == "__main__":
    main()
