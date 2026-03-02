
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_database
from app.models.user import User
from app.schemas.user import (
    ActiveOrganizationInfo,
    SetActiveOrganizationRequest,
    UserMeResponse,
    UserOrganizationInfo,
)
from app.services.user_service import UserService

router = APIRouter()


def get_user_service(db: AsyncSession = Depends(get_database)) -> UserService:
    return UserService(db)


def _build_me_response(user: User) -> UserMeResponse:
    active_org = None
    if user.active_organization:
        active_org = ActiveOrganizationInfo(
            id=user.active_organization.id,
            name=user.active_organization.name,
        )

    organizations = [
        UserOrganizationInfo(
            id=uo.organization.id,
            name=uo.organization.name,
            role=uo.role,
            joined_at=uo.created_at,
        )
        for uo in user.user_organizations
    ]

    return UserMeResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        is_verified=user.is_verified,
        created_at=user.created_at,
        updated_at=user.updated_at,
        active_organization=active_org,
        organizations=organizations,
    )


@router.get("/users/me", response_model=UserMeResponse)
async def get_me(
    current_user: dict = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> UserMeResponse:
    user_id: str = current_user["sub"]
    user = await user_service.get_user_with_organizations(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return _build_me_response(user)


@router.put("/users/me/active-organization", response_model=UserMeResponse)
async def set_active_organization(
    body: SetActiveOrganizationRequest,
    current_user: dict = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> UserMeResponse:
    user_id: str = current_user["sub"]

    try:
        user = await user_service.set_active_organization(user_id, body.organization_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    user = await user_service.get_user_with_organizations(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return _build_me_response(user)
