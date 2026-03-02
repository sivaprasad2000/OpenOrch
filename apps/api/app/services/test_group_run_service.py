from sqlalchemy.ext.asyncio import AsyncSession

from app.models.test_group_run import GroupRunStatus, TestGroupRun
from app.repositories.test_case_repository import TestCaseRepository
from app.repositories.test_group_repository import TestGroupRepository
from app.repositories.test_group_run_repository import TestGroupRunRepository
from app.repositories.user_repository import UserRepository
from app.schemas.test_run import RunConfig
from app.services.test_run_service import TestRunService


class TestGroupRunService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.group_run_repo = TestGroupRunRepository(db)
        self.test_group_repo = TestGroupRepository(db)
        self.test_case_repo = TestCaseRepository(db)
        self.user_repo = UserRepository(db)
        self.test_run_service = TestRunService(db)

    async def run_test_group(
        self, user_id: str, test_group_id: str, config: RunConfig
    ) -> TestGroupRun:
        user = await self.user_repo.get_by_id(user_id)
        if not user or not user.active_organization_id:
            raise ValueError("No active organization set")

        test_group = await self.test_group_repo.get_by_id(test_group_id)
        if not test_group or test_group.organization_id != user.active_organization_id:
            raise LookupError("Test group not found")

        test_cases = await self.test_case_repo.get_by_test_group_id(test_group_id)
        if not test_cases:
            raise ValueError("Test group has no test cases to run")

        group_run = TestGroupRun(
            test_group_id=test_group_id,
            status=GroupRunStatus.QUEUED,
            browser=config.browser,
            base_url_override=config.base_url_override,
            viewport_width=config.viewport_width,
            viewport_height=config.viewport_height,
        )

        try:
            created_group_run = await self.group_run_repo.create(group_run)
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise

        for test_case in test_cases:
            await self.test_run_service.run_test_case(
                user_id=user_id,
                test_case_id=test_case.id,
                config=config,
                test_group_run_id=created_group_run.id,
            )

        await self.db.refresh(created_group_run)
        return created_group_run

    async def get_test_group_run(self, user_id: str, group_run_id: str) -> TestGroupRun | None:
        user = await self.user_repo.get_by_id(user_id)
        if not user or not user.active_organization_id:
            raise ValueError("No active organization set")

        group_run = await self.group_run_repo.get_by_id(group_run_id)
        if not group_run or not group_run.test_group_id:
            return None

        test_group = await self.test_group_repo.get_by_id(group_run.test_group_id)
        if not test_group or test_group.organization_id != user.active_organization_id:
            return None

        return group_run

    async def list_runs_for_test_group(
        self, user_id: str, test_group_id: str, skip: int = 0, limit: int = 100
    ) -> list[TestGroupRun]:
        user = await self.user_repo.get_by_id(user_id)
        if not user or not user.active_organization_id:
            raise ValueError("No active organization set")

        test_group = await self.test_group_repo.get_by_id(test_group_id)
        if not test_group or test_group.organization_id != user.active_organization_id:
            raise LookupError("Test group not found")

        return await self.group_run_repo.get_by_test_group_id(test_group_id, skip=skip, limit=limit)
