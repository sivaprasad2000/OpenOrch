
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.test_group import TestGroup, TestGroupStatus
from app.repositories.test_group_repository import TestGroupRepository
from app.repositories.user_repository import UserRepository
from app.schemas.test_group import TestGroupCreate, TestGroupUpdate


class TestGroupService:

    def __init__(self, db: AsyncSession):
        self.db = db
        self.test_group_repo = TestGroupRepository(db)
        self.user_repo = UserRepository(db)

    async def create_test_group(self, user_id: str, data: TestGroupCreate) -> TestGroup:
        user = await self.user_repo.get_by_id(user_id)
        if not user or not user.active_organization_id:
            raise ValueError("No active organization set")

        test_group = TestGroup(
            name=data.name,
            description=data.description,
            base_url=data.base_url,
            status=TestGroupStatus.ACTIVE,
            tags=data.tags,
            organization_id=user.active_organization_id,
            created_by=user_id,
        )

        try:
            created = await self.test_group_repo.create(test_group)
            await self.db.commit()
            return created
        except Exception:
            await self.db.rollback()
            raise

    async def list_test_groups(
        self, user_id: str, skip: int = 0, limit: int = 100
    ) -> list[TestGroup]:
        user = await self.user_repo.get_by_id(user_id)
        if not user or not user.active_organization_id:
            raise ValueError("No active organization set")

        return await self.test_group_repo.get_by_organization_id(
            user.active_organization_id, skip=skip, limit=limit
        )

    async def get_test_group(
        self, user_id: str, test_group_id: str
    ) -> Optional[TestGroup]:
        user = await self.user_repo.get_by_id(user_id)
        if not user or not user.active_organization_id:
            raise ValueError("No active organization set")

        test_group = await self.test_group_repo.get_by_id(test_group_id)
        if not test_group or test_group.organization_id != user.active_organization_id:
            return None

        return test_group

    async def update_test_group(
        self, user_id: str, test_group_id: str, data: TestGroupUpdate
    ) -> Optional[TestGroup]:
        user = await self.user_repo.get_by_id(user_id)
        if not user or not user.active_organization_id:
            raise ValueError("No active organization set")

        test_group = await self.test_group_repo.get_by_id(test_group_id)
        if not test_group or test_group.organization_id != user.active_organization_id:
            return None

        if data.name is not None:
            test_group.name = data.name
        if data.description is not None:
            test_group.description = data.description
        if data.base_url is not None:
            test_group.base_url = data.base_url
        if data.status is not None:
            test_group.status = data.status
        if data.tags is not None:
            test_group.tags = data.tags

        try:
            updated = await self.test_group_repo.update(test_group)
            await self.db.commit()
            return updated
        except Exception:
            await self.db.rollback()
            raise

    async def delete_test_group(self, user_id: str, test_group_id: str) -> bool:
        user = await self.user_repo.get_by_id(user_id)
        if not user or not user.active_organization_id:
            raise ValueError("No active organization set")

        test_group = await self.test_group_repo.get_by_id(test_group_id)
        if not test_group or test_group.organization_id != user.active_organization_id:
            return False

        try:
            await self.test_group_repo.delete(test_group)
            await self.db.commit()
            return True
        except Exception:
            await self.db.rollback()
            raise
