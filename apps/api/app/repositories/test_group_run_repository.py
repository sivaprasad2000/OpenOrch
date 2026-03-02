
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.test_group_run import TestGroupRun
from app.repositories.base import BaseRepository


class TestGroupRunRepository(BaseRepository[TestGroupRun]):

    def __init__(self, db: AsyncSession):
        super().__init__(TestGroupRun, db)

    async def get_by_test_group_id(
        self, test_group_id: str, skip: int = 0, limit: int = 100
    ) -> list[TestGroupRun]:
        result = await self.db.execute(
            select(TestGroupRun)
            .where(TestGroupRun.test_group_id == test_group_id)
            .offset(skip)
            .limit(limit)
            .order_by(TestGroupRun.created_at.desc())
        )
        return list(result.scalars().all())
