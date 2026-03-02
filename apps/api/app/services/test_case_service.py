
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.test_case import TestCase
from app.models.test_group import TestGroup
from app.repositories.test_case_repository import TestCaseRepository
from app.repositories.test_group_repository import TestGroupRepository
from app.repositories.user_repository import UserRepository
from app.schemas.test_case import TestCaseCreate, TestCaseUpdate


class TestCaseService:

    def __init__(self, db: AsyncSession):
        self.db = db
        self.test_case_repo = TestCaseRepository(db)
        self.test_group_repo = TestGroupRepository(db)
        self.user_repo = UserRepository(db)

    async def _get_accessible_test_group(self, user_id: str, test_group_id: str) -> TestGroup:
        user = await self.user_repo.get_by_id(user_id)
        if not user or not user.active_organization_id:
            raise ValueError("No active organization set")

        test_group = await self.test_group_repo.get_by_id(test_group_id)
        if not test_group or test_group.organization_id != user.active_organization_id:
            raise LookupError("Test group not found")

        return test_group

    async def create_test_case(
        self, user_id: str, test_group_id: str, data: TestCaseCreate
    ) -> TestCase:
        await self._get_accessible_test_group(user_id, test_group_id)

        test_case = TestCase(
            test_group_id=test_group_id,
            payload=data.payload,
        )

        try:
            created = await self.test_case_repo.create(test_case)
            await self.db.commit()
            return created
        except Exception:
            await self.db.rollback()
            raise

    async def list_test_cases(
        self, user_id: str, test_group_id: str, skip: int = 0, limit: int = 100
    ) -> list[TestCase]:
        await self._get_accessible_test_group(user_id, test_group_id)
        return await self.test_case_repo.get_by_test_group_id(
            test_group_id, skip=skip, limit=limit
        )

    async def get_test_case(
        self, user_id: str, test_group_id: str, test_case_id: str
    ) -> Optional[TestCase]:
        await self._get_accessible_test_group(user_id, test_group_id)

        test_case = await self.test_case_repo.get_by_id(test_case_id)
        if not test_case or test_case.test_group_id != test_group_id:
            return None

        return test_case

    async def update_test_case(
        self, user_id: str, test_group_id: str, test_case_id: str, data: TestCaseUpdate
    ) -> Optional[TestCase]:
        await self._get_accessible_test_group(user_id, test_group_id)

        test_case = await self.test_case_repo.get_by_id(test_case_id)
        if not test_case or test_case.test_group_id != test_group_id:
            return None

        test_case.payload = data.payload

        try:
            updated = await self.test_case_repo.update(test_case)
            await self.db.commit()
            return updated
        except Exception:
            await self.db.rollback()
            raise

    async def delete_test_case(
        self, user_id: str, test_group_id: str, test_case_id: str
    ) -> bool:
        await self._get_accessible_test_group(user_id, test_group_id)

        test_case = await self.test_case_repo.get_by_id(test_case_id)
        if not test_case or test_case.test_group_id != test_group_id:
            return False

        try:
            await self.test_case_repo.delete(test_case)
            await self.db.commit()
            return True
        except Exception:
            await self.db.rollback()
            raise
