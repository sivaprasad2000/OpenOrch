
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm import LLM
from app.repositories.base import BaseRepository


class LLMRepository(BaseRepository[LLM]):

    def __init__(self, db: AsyncSession):
        super().__init__(LLM, db)

    async def get_by_organization_id(self, organization_id: str) -> list[LLM]:
        result = await self.db.execute(
            select(LLM)
            .where(LLM.organization_id == organization_id)
            .order_by(LLM.created_at.desc())
        )
        return list(result.scalars().all())
