from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.test_run import TestRun
from app.repositories.base import BaseRepository


class TestRunRepository(BaseRepository[TestRun]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(TestRun, db)

    async def get_by_test_case_id(
        self, test_case_id: str, skip: int = 0, limit: int = 100
    ) -> list[TestRun]:
        result = await self.db.execute(
            select(TestRun)
            .where(TestRun.test_case_id == test_case_id)
            .offset(skip)
            .limit(limit)
            .order_by(TestRun.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_group_run_id(self, group_run_id: str) -> list[TestRun]:
        result = await self.db.execute(
            select(TestRun).where(TestRun.test_group_run_id == group_run_id)
        )
        return list(result.scalars().all())
