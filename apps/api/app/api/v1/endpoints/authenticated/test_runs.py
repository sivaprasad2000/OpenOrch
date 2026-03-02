from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_database
from app.schemas.test_group_run import TestGroupRunResponse
from app.schemas.test_run import PlayerResponse, RunConfig, StepMarker, TestRunResponse
from app.services.test_group_run_service import TestGroupRunService
from app.services.test_run_service import TestRunService

router = APIRouter()


def get_test_run_service(db: AsyncSession = Depends(get_database)) -> TestRunService:
    return TestRunService(db)


def get_test_group_run_service(
    db: AsyncSession = Depends(get_database),
) -> TestGroupRunService:
    return TestGroupRunService(db)


@router.post(
    "/test-cases/{test_case_id}/run",
    response_model=TestRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_test_case(
    test_case_id: str,
    config: RunConfig = RunConfig(),
    current_user: dict = Depends(get_current_user),
    service: TestRunService = Depends(get_test_run_service),
) -> Any:
    user_id: str = current_user["sub"]
    try:
        return await service.run_test_case(user_id, test_case_id, config)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)) from e


@router.post(
    "/test-groups/{test_group_id}/run",
    response_model=TestGroupRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_test_group(
    test_group_id: str,
    config: RunConfig = RunConfig(),
    current_user: dict = Depends(get_current_user),
    service: TestGroupRunService = Depends(get_test_group_run_service),
) -> Any:
    user_id: str = current_user["sub"]
    try:
        return await service.run_test_group(user_id, test_group_id, config)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)) from e


@router.get("/test-runs/{run_id}", response_model=TestRunResponse)
async def get_test_run(
    run_id: str,
    current_user: dict = Depends(get_current_user),
    service: TestRunService = Depends(get_test_run_service),
) -> Any:
    user_id: str = current_user["sub"]
    try:
        test_run = await service.get_test_run(user_id, run_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    if not test_run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test run not found")

    return test_run


@router.get("/test-runs/{run_id}/player", response_model=PlayerResponse)
async def get_player_data(
    run_id: str,
    current_user: dict = Depends(get_current_user),
    service: TestRunService = Depends(get_test_run_service),
) -> Any:
    """Return the recording URL and per-step seek bar markers for the player.

    Strips the heavy tool-call logs from step_results so the response stays
    small even for long test runs.
    """
    user_id: str = current_user["sub"]
    try:
        test_run = await service.get_test_run(user_id, run_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    if not test_run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test run not found")

    markers: list[StepMarker] = []
    for step in test_run.step_results or []:
        markers.append(
            StepMarker(
                index=step["index"],
                action=step["action"],
                group=step.get("group"),
                description=step["description"],
                status=step["status"],
                started_at_seconds=step.get("started_at_seconds", 0.0),
                duration_ms=step["duration_ms"],
                error=step.get("error"),
            )
        )

    return PlayerResponse(recording_url=test_run.recording_url, markers=markers)


@router.get("/test-cases/{test_case_id}/runs", response_model=list[TestRunResponse])
async def list_runs_for_test_case(
    test_case_id: str,
    skip: int = 0,
    limit: int = 100,
    current_user: dict = Depends(get_current_user),
    service: TestRunService = Depends(get_test_run_service),
) -> Any:
    user_id: str = current_user["sub"]
    try:
        return await service.list_runs_for_test_case(user_id, test_case_id, skip=skip, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.get("/test-group-runs/{group_run_id}", response_model=TestGroupRunResponse)
async def get_test_group_run(
    group_run_id: str,
    current_user: dict = Depends(get_current_user),
    service: TestGroupRunService = Depends(get_test_group_run_service),
) -> Any:
    user_id: str = current_user["sub"]
    try:
        group_run = await service.get_test_group_run(user_id, group_run_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    if not group_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Test group run not found"
        )

    return group_run


@router.get("/test-groups/{test_group_id}/runs", response_model=list[TestGroupRunResponse])
async def list_runs_for_test_group(
    test_group_id: str,
    skip: int = 0,
    limit: int = 100,
    current_user: dict = Depends(get_current_user),
    service: TestGroupRunService = Depends(get_test_group_run_service),
) -> Any:
    user_id: str = current_user["sub"]
    try:
        return await service.list_runs_for_test_group(
            user_id, test_group_id, skip=skip, limit=limit
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
