
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_database
from app.schemas.test_case import StepAction, TestCaseCreate, TestCaseResponse, TestCaseUpdate
from app.services.test_case_service import TestCaseService

router = APIRouter()


@router.get("/step-actions", response_model=list[str])
async def list_step_actions(
    current_user: dict = Depends(get_current_user),
) -> list[str]:
    return [action.value for action in StepAction]


def get_test_case_service(
    db: AsyncSession = Depends(get_database),
) -> TestCaseService:
    return TestCaseService(db)


@router.post(
    "/test-groups/{test_group_id}/test-cases",
    response_model=TestCaseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_test_case(
    test_group_id: str,
    data: TestCaseCreate,
    current_user: dict = Depends(get_current_user),
    service: TestCaseService = Depends(get_test_case_service),
) -> Any:
    user_id: str = current_user["sub"]
    try:
        return await service.create_test_case(user_id, test_group_id, data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/test-groups/{test_group_id}/test-cases",
    response_model=list[TestCaseResponse],
)
async def list_test_cases(
    test_group_id: str,
    skip: int = 0,
    limit: int = 100,
    current_user: dict = Depends(get_current_user),
    service: TestCaseService = Depends(get_test_case_service),
) -> Any:
    user_id: str = current_user["sub"]
    try:
        return await service.list_test_cases(user_id, test_group_id, skip=skip, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/test-groups/{test_group_id}/test-cases/{test_case_id}",
    response_model=TestCaseResponse,
)
async def get_test_case(
    test_group_id: str,
    test_case_id: str,
    current_user: dict = Depends(get_current_user),
    service: TestCaseService = Depends(get_test_case_service),
) -> Any:
    user_id: str = current_user["sub"]
    try:
        test_case = await service.get_test_case(user_id, test_group_id, test_case_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    if not test_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Test case not found"
        )

    return test_case


@router.put(
    "/test-groups/{test_group_id}/test-cases/{test_case_id}",
    response_model=TestCaseResponse,
)
async def update_test_case(
    test_group_id: str,
    test_case_id: str,
    data: TestCaseUpdate,
    current_user: dict = Depends(get_current_user),
    service: TestCaseService = Depends(get_test_case_service),
) -> Any:
    user_id: str = current_user["sub"]
    try:
        test_case = await service.update_test_case(user_id, test_group_id, test_case_id, data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    if not test_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Test case not found"
        )

    return test_case


@router.delete(
    "/test-groups/{test_group_id}/test-cases/{test_case_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_test_case(
    test_group_id: str,
    test_case_id: str,
    current_user: dict = Depends(get_current_user),
    service: TestCaseService = Depends(get_test_case_service),
) -> None:
    user_id: str = current_user["sub"]
    try:
        deleted = await service.delete_test_case(user_id, test_group_id, test_case_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Test case not found"
        )
