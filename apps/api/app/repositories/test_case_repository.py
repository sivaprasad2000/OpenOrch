from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.test_case import TestCase
from app.repositories.base import BaseRepository


class TestCaseRepository(BaseRepository[TestCase]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(TestCase, db)

    async def get_by_test_group_id(
        self, test_group_id: str, skip: int = 0, limit: int = 100
    ) -> list[TestCase]:
        result = await self.db.execute(
            select(TestCase)
            .where(TestCase.test_group_id == test_group_id)
            .offset(skip)
            .limit(limit)
            .order_by(TestCase.created_at.desc())
        )
        return list(result.scalars().all())
