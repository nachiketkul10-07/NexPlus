"""Interactively bootstrap the first production administrator after migrations."""
import asyncio
import getpass
from sqlalchemy import select

from app.core.security import hash_password
from app.core.config import settings
from app.db.session import AsyncSessionLocal, engine
from app.models.user import User
from app.schemas.user import UserRole, UserRegister


async def create_admin(email: str, full_name: str, password: str) -> None:
    admin = UserRegister(email=email, full_name=full_name, password=password, role=UserRole.ADMIN)
    async with AsyncSessionLocal() as session:
        existing_admin = await session.scalar(select(User).where(User.role == UserRole.ADMIN.value).limit(1))
        if existing_admin:
            raise RuntimeError("An administrator already exists; refusing to create another bootstrap admin.")
        existing_email = await session.scalar(select(User).where(User.email == str(admin.email).lower()).limit(1))
        if existing_email:
            raise RuntimeError("That email address is already registered.")
        session.add(User(
            email=str(admin.email).lower(),
            full_name=admin.full_name,
            hashed_password=hash_password(admin.password),
            role=UserRole.ADMIN.value,
            is_active=True,
        ))
        await session.commit()


def main() -> None:
    if not settings.is_production:
        raise SystemExit("Initial admin bootstrap is reserved for ENVIRONMENT=production.")
    email = input("Initial admin email: ").strip()
    full_name = input("Initial admin full name: ").strip()
    password = getpass.getpass("Initial admin password (minimum 16 characters): ")
    confirmation = getpass.getpass("Confirm password: ")
    if len(password) < 16:
        raise SystemExit("Use a unique password with at least 16 characters.")
    if password != confirmation:
        raise SystemExit("The passwords did not match.")
    async def run() -> None:
        try:
            await create_admin(email, full_name, password)
        finally:
            await engine.dispose()

    asyncio.run(run())
    print("Initial administrator created. Store the password in your password manager.")


if __name__ == "__main__":
    main()
