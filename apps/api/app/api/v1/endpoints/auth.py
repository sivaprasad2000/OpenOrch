
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_database
from app.services.auth_service import AuthService
from app.schemas.auth import (
    SignupRequest,
    SignupResponse,
    SigninRequest,
    TokenResponse,
    VerifyEmailRequest,
    VerifyEmailResponse,
    ResendOTPRequest,
    ResendOTPResponse
)

router = APIRouter()


def get_auth_service(db: AsyncSession = Depends(get_database)) -> AuthService:
    return AuthService(db)


@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    signup_data: SignupRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> Any:
    try:
        user, otp_code = await auth_service.signup(signup_data)

        return SignupResponse(
            message="User registered successfully. Please verify your email with the OTP sent.",
            user_id=user.id,
            email=user.email
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register user"
        )


@router.post("/signin", response_model=TokenResponse)
async def signin(
    signin_data: SigninRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> Any:
    try:
        user = await auth_service.signin(signin_data)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )

        access_token = auth_service.create_access_token(user)

        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user_id=user.id,
            email=user.email,
            is_verified=user.is_verified
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to sign in"
        )


@router.post("/verify-email", response_model=VerifyEmailResponse)
async def verify_email(
    verify_data: VerifyEmailRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> Any:
    try:
        user = await auth_service.verify_email(
            email=verify_data.email,
            otp_code=verify_data.otp
        )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid OTP or user not found"
            )

        access_token = auth_service.create_access_token(user)

        return VerifyEmailResponse(
            message="Email verified successfully",
            access_token=access_token,
            token_type="bearer"
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify email"
        )


@router.post("/resend-otp", response_model=ResendOTPResponse)
async def resend_otp(
    resend_data: ResendOTPRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> Any:
    try:
        otp_code = await auth_service.resend_otp(resend_data.email)

        return ResendOTPResponse(
            message="OTP sent successfully. Please check your email."
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resend OTP"
        )
