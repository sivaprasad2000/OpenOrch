from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_organization import UserOrganization
from app.repositories.base import BaseRepository


class UserOrganizationRepository(BaseRepository[UserOrganization]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(UserOrganization, db)

    async def get_by_user_and_org(
        self, user_id: str, organization_id: str
    ) -> UserOrganization | None:
        result = await self.db.execute(
            select(UserOrganization).where(
                and_(
                    UserOrganization.user_id == user_id,
                    UserOrganization.organization_id == organization_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_by_user_id(self, user_id: str) -> list[UserOrganization]:
        result = await self.db.execute(
            select(UserOrganization).where(UserOrganization.user_id == user_id)
        )
        return list(result.scalars().all())

    async def get_by_organization_id(self, organization_id: str) -> list[UserOrganization]:
        result = await self.db.execute(
            select(UserOrganization).where(UserOrganization.organization_id == organization_id)
        )
        return list(result.scalars().all())

    async def membership_exists(self, user_id: str, organization_id: str) -> bool:
        membership = await self.get_by_user_and_org(user_id, organization_id)
        return membership is not None
