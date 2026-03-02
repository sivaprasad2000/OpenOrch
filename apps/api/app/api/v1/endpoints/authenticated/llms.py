
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_database
from app.schemas.llm import LLMCreate, LLMResponse, LLMUpdate
from app.services.llm_service import LLMService

router = APIRouter()


def get_llm_service(db: AsyncSession = Depends(get_database)) -> LLMService:
    return LLMService(db)


@router.get("/llms", response_model=list[LLMResponse])
async def list_llms(
    current_user: dict = Depends(get_current_user),
    llm_service: LLMService = Depends(get_llm_service),
) -> Any:
    user_id: str = current_user["sub"]

    try:
        return await llm_service.list_llms(user_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/llms", response_model=LLMResponse, status_code=status.HTTP_201_CREATED)
async def create_llm(
    llm_data: LLMCreate,
    current_user: dict = Depends(get_current_user),
    llm_service: LLMService = Depends(get_llm_service),
) -> Any:
    user_id: str = current_user["sub"]

    try:
        return await llm_service.create_llm(user_id, llm_data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.patch("/llms/{llm_id}", response_model=LLMResponse)
async def update_llm(
    llm_id: str,
    llm_data: LLMUpdate,
    current_user: dict = Depends(get_current_user),
    llm_service: LLMService = Depends(get_llm_service),
) -> Any:
    user_id: str = current_user["sub"]
    try:
        updated = await llm_service.update_llm(user_id, llm_id, llm_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="LLM not found")

    return updated


@router.delete("/llms/{llm_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_llm(
    llm_id: str,
    current_user: dict = Depends(get_current_user),
    llm_service: LLMService = Depends(get_llm_service),
) -> None:
    user_id: str = current_user["sub"]

    try:
        deleted = await llm_service.delete_llm(user_id, llm_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="LLM not found",
        )
