"""
User Repository Interfaces and PostgreSQL Async Implementation
Replaces Phase 3 in-memory repository with real PostgreSQL + AsyncPG persistence.
"""
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, Optional
from uuid import UUID, uuid4
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.user import UserRegister, UserInDB, UserRole
from app.core.security import hash_password
from app.models.user import User


class UserRepositoryInterface(ABC):
    @abstractmethod
    async def create_user(self, user_in: UserRegister, hashed_pwd: Optional[str] = None) -> UserInDB:
        """Creates a new user record."""
        pass

    @abstractmethod
    async def get_by_email(self, email: str) -> Optional[UserInDB]:
        """Fetches user by email address."""
        pass

    @abstractmethod
    async def get_by_id(self, user_id: str) -> Optional[UserInDB]:
        """Fetches user by UUID string."""
        pass


class PostgresUserRepository(UserRepositoryInterface):
    """
    Production PostgreSQL User Repository using SQLAlchemy Async Session.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_user(self, user_in: UserRegister, hashed_pwd: Optional[str] = None) -> UserInDB:
        email_key = user_in.email.lower().strip()
        existing = await self.get_by_email(email_key)
        if existing:
            raise ValueError("User with this email already exists.")

        pwd_hash = hashed_pwd or hash_password(user_in.password)
        db_user = User(
            id=uuid4(),
            email=email_key,
            full_name=user_in.full_name,
            hashed_password=pwd_hash,
            role=user_in.role.value if hasattr(user_in.role, "value") else str(user_in.role),
            is_active=True
        )
        self.session.add(db_user)
        await self.session.flush()
        await self.session.refresh(db_user)
        return UserInDB.model_validate(db_user)

    async def get_by_email(self, email: str) -> Optional[UserInDB]:
        email_key = email.lower().strip()
        stmt = select(User).where(func.lower(User.email) == email_key)
        result = await self.session.execute(stmt)
        user = result.scalars().first()
        if not user:
            return None
        return UserInDB.model_validate(user)

    async def get_by_id(self, user_id: str) -> Optional[UserInDB]:
        try:
            val_id = UUID(str(user_id))
        except (ValueError, AttributeError):
            return None

        stmt = select(User).where(User.id == val_id)
        result = await self.session.execute(stmt)
        user = result.scalars().first()
        if not user:
            return None
        return UserInDB.model_validate(user)


class InMemoryUserRepository(UserRepositoryInterface):
    """
    Temporary In-Memory User Repository for fallback/testing.
    """

    def __init__(self):
        self._users_by_id: Dict[str, UserInDB] = {}
        self._users_by_email: Dict[str, str] = {}

    async def create_user(self, user_in: UserRegister, hashed_pwd: Optional[str] = None) -> UserInDB:
        email_key = user_in.email.lower().strip()
        if email_key in self._users_by_email:
            raise ValueError("User with this email already exists.")

        user_id = uuid4()
        now = datetime.now(timezone.utc)
        pwd_hash = hashed_pwd or hash_password(user_in.password)

        db_user = UserInDB(
            id=user_id,
            email=user_in.email,
            full_name=user_in.full_name,
            role=user_in.role,
            is_active=True,
            created_at=now,
            updated_at=now,
            hashed_password=pwd_hash
        )

        self._users_by_id[str(user_id)] = db_user
        self._users_by_email[email_key] = str(user_id)
        return db_user

    async def get_by_email(self, email: str) -> Optional[UserInDB]:
        user_id = self._users_by_email.get(email.lower().strip())
        if not user_id:
            return None
        return self._users_by_id.get(user_id)

    async def get_by_id(self, user_id: str) -> Optional[UserInDB]:
        return self._users_by_id.get(str(user_id))

