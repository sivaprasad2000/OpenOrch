
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rabbitmq import publish_test_run
from app.models.llm import LLM
from app.models.test_group_run import GroupRunStatus
from app.models.test_run import RunStatus, TestRun
from app.repositories.llm_repository import LLMRepository
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.test_case_repository import TestCaseRepository
from app.repositories.test_group_repository import TestGroupRepository
from app.repositories.test_group_run_repository import TestGroupRunRepository
from app.repositories.test_run_repository import TestRunRepository
from app.repositories.user_repository import UserRepository
from app.schemas.test_run import RunConfig, TestRunResultUpdate


class TestRunService:

    def __init__(self, db: AsyncSession):
        self.db = db
        self.test_run_repo = TestRunRepository(db)
        self.test_case_repo = TestCaseRepository(db)
        self.test_group_repo = TestGroupRepository(db)
        self.test_group_run_repo = TestGroupRunRepository(db)
        self.user_repo = UserRepository(db)
        self.org_repo = OrganizationRepository(db)
        self.llm_repo = LLMRepository(db)

    async def run_test_case(
        self,
        user_id: str,
        test_case_id: str,
        config: RunConfig,
        test_group_run_id: str | None = None,
    ) -> TestRun:
        user = await self.user_repo.get_by_id(user_id)
        if not user or not user.active_organization_id:
            raise ValueError("No active organization set")

        test_case = await self.test_case_repo.get_by_id(test_case_id)
        if not test_case:
            raise LookupError("Test case not found")

        test_group = await self.test_group_repo.get_by_id(test_case.test_group_id)
        if not test_group or test_group.organization_id != user.active_organization_id:
            raise LookupError("Test case not found")

        test_run = TestRun(
            test_case_id=test_case_id,
            test_group_run_id=test_group_run_id,
            status=RunStatus.QUEUED,
            browser=config.browser,
            base_url_override=config.base_url_override,
            viewport_width=config.viewport_width,
            viewport_height=config.viewport_height,
        )

        try:
            created = await self.test_run_repo.create(test_run)
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise

        await publish_test_run(run_id=created.id, test_case_id=test_case_id)

        return created

    async def get_test_run(self, user_id: str, run_id: str) -> Optional[TestRun]:
        user = await self.user_repo.get_by_id(user_id)
        if not user or not user.active_organization_id:
            raise ValueError("No active organization set")

        test_run = await self.test_run_repo.get_by_id(run_id)
        if not test_run or not test_run.test_case_id:
            return None

        test_case = await self.test_case_repo.get_by_id(test_run.test_case_id)
        if not test_case:
            return None

        test_group = await self.test_group_repo.get_by_id(test_case.test_group_id)
        if not test_group or test_group.organization_id != user.active_organization_id:
            return None

        return test_run

    async def list_runs_for_test_case(
        self, user_id: str, test_case_id: str, skip: int = 0, limit: int = 100
    ) -> list[TestRun]:
        user = await self.user_repo.get_by_id(user_id)
        if not user or not user.active_organization_id:
            raise ValueError("No active organization set")

        test_case = await self.test_case_repo.get_by_id(test_case_id)
        if not test_case:
            raise LookupError("Test case not found")

        test_group = await self.test_group_repo.get_by_id(test_case.test_group_id)
        if not test_group or test_group.organization_id != user.active_organization_id:
            raise LookupError("Test case not found")

        return await self.test_run_repo.get_by_test_case_id(
            test_case_id, skip=skip, limit=limit
        )

    async def get_run_detail(self, run_id: str) -> Optional[TestRun]:
        return await self.test_run_repo.get_by_id(run_id)

    async def get_run_detail_with_llm(self, run_id: str) -> tuple[Optional[TestRun], Optional[LLM]]:
        """Load the test run and the org's active LLM (if any)."""
        test_run = await self.test_run_repo.get_by_id(run_id)
        if not test_run:
            return None, None

        # Walk the eager-loaded chain: test_run → test_case → test_group → org
        if not test_run.test_case:
            return test_run, None

        test_group = test_run.test_case.test_group
        if not test_group:
            return test_run, None

        org = await self.org_repo.get_by_id(test_group.organization_id)
        if not org or not org.active_llm_id:
            return test_run, None

        llm = await self.llm_repo.get_by_id(org.active_llm_id)
        return test_run, llm

    async def update_run_result(
        self, run_id: str, data: TestRunResultUpdate
    ) -> Optional[TestRun]:
        test_run = await self.test_run_repo.get_by_id(run_id)
        if not test_run:
            return None

        test_run.status = data.status
        test_run.step_results = [step.model_dump() for step in data.step_results]
        test_run.recording_url = data.recording_url
        test_run.trace_url = data.trace_url
        test_run.error = data.error
        test_run.started_at = data.started_at
        test_run.completed_at = data.completed_at

        try:
            updated = await self.test_run_repo.update(test_run)

            if test_run.test_group_run_id:
                await self._sync_group_run_status(test_run.test_group_run_id)

            await self.db.commit()
            return updated
        except Exception:
            await self.db.rollback()
            raise

    async def _sync_group_run_status(self, group_run_id: str) -> None:
        group_run = await self.test_group_run_repo.get_by_id(group_run_id)
        if not group_run:
            return

        runs = await self.test_run_repo.get_by_group_run_id(group_run_id)
        if not runs:
            return

        terminal = {RunStatus.PASSED, RunStatus.FAILED}
        all_done = all(r.status in terminal for r in runs)

        if not all_done:
            group_run.status = GroupRunStatus.RUNNING
        elif all(r.status == RunStatus.PASSED for r in runs):
            group_run.status = GroupRunStatus.PASSED
        elif all(r.status == RunStatus.FAILED for r in runs):
            group_run.status = GroupRunStatus.FAILED
        else:
            group_run.status = GroupRunStatus.PARTIAL

        await self.test_group_run_repo.update(group_run)
