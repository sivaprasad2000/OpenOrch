from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_database
from app.schemas.organization import (
    AssignRoleRequest,
    OrganizationCreate,
    OrganizationResponse,
    SetActiveLLMRequest,
)
from app.services.organization_service import OrganizationService

router = APIRouter()


def get_organization_service(
    db: AsyncSession = Depends(get_database),
) -> OrganizationService:
    return OrganizationService(db)


@router.post(
    "/organizations",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_organization(
    org_data: OrganizationCreate,
    current_user: dict = Depends(get_current_user),
    org_service: OrganizationService = Depends(get_organization_service),
) -> Any:
    user_id: str = current_user["sub"]
    return await org_service.create_organization(org_data, creator_user_id=user_id)


@router.put(
    "/organizations/{organization_id}/active-llm",
    response_model=OrganizationResponse,
)
async def set_active_llm(
    organization_id: str,
    body: SetActiveLLMRequest,
    current_user: dict = Depends(get_current_user),
    org_service: OrganizationService = Depends(get_organization_service),
) -> Any:
    requester_id: str = current_user["sub"]
    try:
        return await org_service.set_active_llm(
            requester_id=requester_id,
            organization_id=organization_id,
            llm_id=body.llm_id,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.delete(
    "/organizations/{organization_id}/active-llm",
    response_model=OrganizationResponse,
)
async def clear_active_llm(
    organization_id: str,
    current_user: dict = Depends(get_current_user),
    org_service: OrganizationService = Depends(get_organization_service),
) -> Any:
    requester_id: str = current_user["sub"]
    try:
        return await org_service.set_active_llm(
            requester_id=requester_id,
            organization_id=organization_id,
            llm_id=None,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.put("/organizations/{organization_id}/roles")
async def assign_role(
    organization_id: str,
    body: AssignRoleRequest,
    current_user: dict = Depends(get_current_user),
    org_service: OrganizationService = Depends(get_organization_service),
) -> dict[str, Any]:
    requester_id: str = current_user["sub"]

    try:
        membership = await org_service.assign_role(
            requester_id=requester_id,
            organization_id=organization_id,
            target_user_id=body.user_id,
            role=body.role,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    return {
        "user_id": membership.user_id,
        "organization_id": membership.organization_id,
        "role": membership.role,
    }
