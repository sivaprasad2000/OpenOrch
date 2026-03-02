from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.test_group import TestGroup
from app.repositories.base import BaseRepository


class TestGroupRepository(BaseRepository[TestGroup]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(TestGroup, db)

    async def get_by_organization_id(
        self, organization_id: str, skip: int = 0, limit: int = 100
    ) -> list[TestGroup]:
        result = await self.db.execute(
            select(TestGroup)
            .where(TestGroup.organization_id == organization_id)
            .offset(skip)
            .limit(limit)
            .order_by(TestGroup.created_at.desc())
        )
        return list(result.scalars().all())
