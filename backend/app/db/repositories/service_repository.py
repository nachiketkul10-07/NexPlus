"""
Service Repository Implementation for PostgreSQL
Manages Service entities and ingest credential validation.
"""
from datetime import datetime, timezone
from typing import Optional, List, Tuple
from uuid import UUID
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_ingest_key, hash_ingest_key
from app.models.service import Service
from app.models.alert import Alert, AlertRule
from app.models.incident import Incident
from app.schemas.service import ServiceCreate


class PostgresServiceRepository:
    """Async repository for Service ORM model CRUD and authentication operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, service_id: UUID) -> Optional[Service]:
        """Fetch service by UUID primary key."""
        stmt = select(Service).where(Service.id == service_id)
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def get_by_identifier(self, identifier: str) -> Optional[Service]:
        """Fetch service by unique text identifier (e.g. demo-app)."""
        stmt = select(Service).where(Service.identifier == identifier.strip())
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def get_by_ingest_key(self, raw_ingest_key: str) -> Optional[Service]:
        """Look up active service matching raw ingestion key hash."""
        if not raw_ingest_key:
            return None
        key_hash = hash_ingest_key(raw_ingest_key)
        stmt = select(Service).where(Service.ingest_key_hash == key_hash)
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def create_service(self, service_in: ServiceCreate) -> Tuple[Service, str]:
        """Creates a new service and generates a raw ingestion key returned once."""
        raw_key = generate_ingest_key()
        key_hash = hash_ingest_key(raw_key)

        service = Service(
            identifier=service_in.identifier,
            name=service_in.name,
            environment=service_in.environment,
            base_url=service_in.base_url,
            repository_url=service_in.repository_url,
            health_path=service_in.health_path,
            status="unknown",
            ingest_key_hash=key_hash,
            last_seen_at=None
        )
        self.session.add(service)
        await self.session.flush()
        await self.session.refresh(service)
        return service, raw_key

    async def rotate_ingest_key(self, service_id: UUID) -> Optional[str]:
        """Replace a service credential and return its raw value once."""
        service = await self.get_by_id(service_id)
        if service is None:
            return None
        raw_key = generate_ingest_key()
        service.ingest_key_hash = hash_ingest_key(raw_key)
        await self.session.flush()
        return raw_key

    async def delete_service(self, service_id: UUID) -> bool:
        """Delete a service and its service-scoped operational history."""
        service = await self.get_by_id(service_id)
        if service is None:
            return False

        # Remove dependents explicitly because these foreign keys use RESTRICT.
        for model in (Incident, Alert, AlertRule):
            result = await self.session.execute(select(model).where(model.service_id == service_id))
            for record in result.scalars().all():
                await self.session.delete(record)
        await self.session.delete(service)
        await self.session.flush()
        return True

    async def update_last_seen(self, service_id: UUID, ts: Optional[datetime] = None) -> None:
        """Updates service last_seen_at timestamp to signify activity."""
        seen_at = ts or datetime.now(timezone.utc)
        stmt = (
            update(Service)
            .where(Service.id == service_id)
            .values(last_seen_at=seen_at, status="healthy")
        )
        await self.session.execute(stmt)

    async def list_services(self) -> List[Service]:
        """Fetch all registered services ordered by creation date."""
        stmt = select(Service).order_by(Service.created_at.desc())
        res = await self.session.execute(stmt)
        return list(res.scalars().all())
