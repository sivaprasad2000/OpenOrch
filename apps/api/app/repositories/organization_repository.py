
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.repositories.base import BaseRepository


class OrganizationRepository(BaseRepository[Organization]):

    def __init__(self, db: AsyncSession):
        super().__init__(Organization, db)

    async def get_by_name(self, name: str) -> Optional[Organization]:
        result = await self.db.execute(
            select(Organization).where(Organization.name == name)
        )
        return result.scalar_one_or_none()

    async def name_exists(self, name: str) -> bool:
        organization = await self.get_by_name(name)
        return organization is not None

    async def search_by_name(
        self, name: str, skip: int = 0, limit: int = 100
    ) -> list[Organization]:
        result = await self.db.execute(
            select(Organization)
            .where(Organization.name.ilike(f"%{name}%"))
            .offset(skip)
            .limit(limit)
            .order_by(Organization.created_at.desc())
        )
        return list(result.scalars().all())
