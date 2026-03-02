
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.team import Team
from app.repositories.base import BaseRepository


class TeamRepository(BaseRepository[Team]):

    def __init__(self, db: AsyncSession):
        super().__init__(Team, db)

    async def get_by_organization_id(
        self, organization_id: str, skip: int = 0, limit: int = 100
    ) -> list[Team]:
        result = await self.db.execute(
            select(Team)
            .where(Team.organization_id == organization_id)
            .offset(skip)
            .limit(limit)
            .order_by(Team.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_id_and_org(
        self, team_id: str, organization_id: str
    ) -> Optional[Team]:
        result = await self.db.execute(
            select(Team).where(
                Team.id == team_id,
                Team.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()
