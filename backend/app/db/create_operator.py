"""Interactively add an operator to a production single-team installation."""
import asyncio
import getpass
from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal, engine
from app.models.user import User
from app.schemas.user import UserRegister, UserRole


async def add_operator(email: str, full_name: str, password: str) -> None:
    operator = UserRegister(email=email, full_name=full_name, password=password, role=UserRole.USER)
    async with AsyncSessionLocal() as session:
        admin = await session.scalar(select(User).where(User.role == UserRole.ADMIN.value).limit(1))
        if not admin:
            raise RuntimeError("Create the initial administrator before adding operators.")
        existing = await session.scalar(select(User).where(User.email == str(operator.email).lower()).limit(1))
        if existing:
            raise RuntimeError("That email address is already registered.")
        session.add(User(
            email=str(operator.email).lower(),
            full_name=operator.full_name,
            hashed_password=hash_password(operator.password),
            role=UserRole.USER.value,
            is_active=True,
        ))
        await session.commit()


def main() -> None:
    if not settings.is_production:
        raise SystemExit("Operator provisioning is reserved for ENVIRONMENT=production.")
    email = input("Operator email: ").strip()
    full_name = input("Operator full name: ").strip()
    password = getpass.getpass("Unique password (minimum 16 characters): ")
    if len(password) < 16:
        raise SystemExit("Use a unique password with at least 16 characters.")
    if password != getpass.getpass("Confirm password: "):
        raise SystemExit("The passwords did not match.")

    async def run() -> None:
        try:
            await add_operator(email, full_name, password)
        finally:
            await engine.dispose()

    asyncio.run(run())
    print("Operator account created.")


if __name__ == "__main__":
    main()
