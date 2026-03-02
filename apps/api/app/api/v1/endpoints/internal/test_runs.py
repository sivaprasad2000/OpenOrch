from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_database, verify_internal_secret
from app.schemas.test_run import (
    LLMConfig,
    TestRunDetailResponse,
    TestRunResponse,
    TestRunResultUpdate,
)
from app.services.test_run_service import TestRunService

router = APIRouter()


def get_test_run_service(db: AsyncSession = Depends(get_database)) -> TestRunService:
    return TestRunService(db)


@router.get(
    "/test-runs/{run_id}",
    response_model=TestRunDetailResponse,
    dependencies=[Depends(verify_internal_secret)],
)
async def get_test_run_detail(
    run_id: str,
    service: TestRunService = Depends(get_test_run_service),
) -> TestRunDetailResponse:
    test_run, llm = await service.get_run_detail_with_llm(run_id)

    if not test_run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test run not found")

    llm_config: LLMConfig | None = None
    if llm:
        llm_config = LLMConfig(
            provider=llm.provider.value,
            api_key=llm.api_key,
            model_name=llm.model_name,
        )

    return TestRunDetailResponse(
        id=test_run.id,
        test_case_id=test_run.test_case_id,
        test_group_run_id=test_run.test_group_run_id,
        status=test_run.status,
        browser=test_run.browser,
        base_url_override=test_run.base_url_override,
        viewport_width=test_run.viewport_width,
        viewport_height=test_run.viewport_height,
        test_case_payload=test_run.test_case.payload if test_run.test_case else None,
        llm_config=llm_config,
        created_at=test_run.created_at,
        updated_at=test_run.updated_at,
    )


@router.patch(
    "/test-runs/{run_id}/result",
    response_model=TestRunResponse,
    dependencies=[Depends(verify_internal_secret)],
)
async def update_test_run_result(
    run_id: str,
    data: TestRunResultUpdate,
    service: TestRunService = Depends(get_test_run_service),
) -> Any:
    test_run = await service.update_run_result(run_id, data)

    if not test_run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test run not found")

    return test_run
