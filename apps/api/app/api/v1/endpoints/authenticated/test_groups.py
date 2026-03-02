
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_database
from app.schemas.test_group import TestGroupCreate, TestGroupResponse, TestGroupUpdate
from app.services.test_group_service import TestGroupService

router = APIRouter()


def get_test_group_service(
    db: AsyncSession = Depends(get_database),
) -> TestGroupService:
    return TestGroupService(db)


@router.post(
    "/test-groups",
    response_model=TestGroupResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_test_group(
    data: TestGroupCreate,
    current_user: dict = Depends(get_current_user),
    service: TestGroupService = Depends(get_test_group_service),
) -> Any:
    user_id: str = current_user["sub"]
    try:
        return await service.create_test_group(user_id, data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/test-groups", response_model=list[TestGroupResponse])
async def list_test_groups(
    skip: int = 0,
    limit: int = 100,
    current_user: dict = Depends(get_current_user),
    service: TestGroupService = Depends(get_test_group_service),
) -> Any:
    user_id: str = current_user["sub"]
    try:
        return await service.list_test_groups(user_id, skip=skip, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/test-groups/{test_group_id}", response_model=TestGroupResponse)
async def get_test_group(
    test_group_id: str,
    current_user: dict = Depends(get_current_user),
    service: TestGroupService = Depends(get_test_group_service),
) -> Any:
    user_id: str = current_user["sub"]
    try:
        test_group = await service.get_test_group(user_id, test_group_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    if not test_group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Test group not found"
        )

    return test_group


@router.put("/test-groups/{test_group_id}", response_model=TestGroupResponse)
async def update_test_group(
    test_group_id: str,
    data: TestGroupUpdate,
    current_user: dict = Depends(get_current_user),
    service: TestGroupService = Depends(get_test_group_service),
) -> Any:
    user_id: str = current_user["sub"]
    try:
        test_group = await service.update_test_group(user_id, test_group_id, data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    if not test_group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Test group not found"
        )

    return test_group


@router.delete("/test-groups/{test_group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_test_group(
    test_group_id: str,
    current_user: dict = Depends(get_current_user),
    service: TestGroupService = Depends(get_test_group_service),
) -> None:
    user_id: str = current_user["sub"]
    try:
        deleted = await service.delete_test_group(user_id, test_group_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Test group not found"
        )
