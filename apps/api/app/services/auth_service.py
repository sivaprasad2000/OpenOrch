
import secrets
from datetime import timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.otp import OTP
from app.models.user import User
from app.repositories.otp_repository import OTPRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import SigninRequest, SignupRequest
from app.services.email_service import EmailService


class AuthService:

    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)
        self.otp_repo = OTPRepository(db)
        self.email_service = EmailService()

    @staticmethod
    def generate_otp(length: int = 6) -> str:
        return "".join(secrets.choice("0123456789") for _ in range(length))

    async def signup(self, signup_data: SignupRequest) -> tuple[User, str]:
        if await self.user_repo.email_exists(signup_data.email):
            raise ValueError("Email already registered")

        hashed_password = get_password_hash(signup_data.password)

        user_id = User.generate_id_from_email(signup_data.email)

        user = User(
            id=user_id,
            email=signup_data.email.lower(),
            name=signup_data.name,
            password=hashed_password,
            is_verified=False
        )

        try:
            created_user = await self.user_repo.create(user)

            otp_code = self.generate_otp()

            otp = OTP(
                user_id=created_user.id,
                code=otp_code,
                expires_at=OTP.generate_expiry(minutes=10),
                is_used=False
            )
            await self.otp_repo.create(otp)

            await self.db.commit()

            await self.email_service.send_verification_email(
                to_email=created_user.email,
                user_name=created_user.name,
                otp_code=otp_code
            )

            return created_user, otp_code

        except Exception as e:
            await self.db.rollback()
            raise e

    async def signin(self, signin_data: SigninRequest) -> Optional[User]:
        user = await self.user_repo.get_by_email(signin_data.email)

        if not user:
            return None

        if not verify_password(signin_data.password, user.password):
            return None

        return user

    async def verify_email(self, email: str, otp_code: str) -> Optional[User]:
        user = await self.user_repo.get_by_email(email)

        if not user:
            raise ValueError("User not found")

        if user.is_verified:
            raise ValueError("Email already verified")

        otp = await self.otp_repo.get_valid_otp(user.id, otp_code)

        if not otp:
            raise ValueError("Invalid or expired OTP")

        try:
            user.is_verified = True
            await self.user_repo.update(user)

            otp.is_used = True
            await self.otp_repo.update(otp)

            await self.db.commit()

            await self.email_service.send_welcome_email(
                to_email=user.email,
                user_name=user.name
            )

            return user

        except Exception as e:
            await self.db.rollback()
            raise e

    async def resend_otp(self, email: str) -> str:
        user = await self.user_repo.get_by_email(email)

        if not user:
            raise ValueError("User not found")

        if user.is_verified:
            raise ValueError("Email already verified")

        try:
            await self.otp_repo.invalidate_user_otps(user.id)

            otp_code = self.generate_otp()

            otp = OTP(
                user_id=user.id,
                code=otp_code,
                expires_at=OTP.generate_expiry(minutes=10),
                is_used=False
            )
            await self.otp_repo.create(otp)

            await self.db.commit()

            await self.email_service.send_verification_email(
                to_email=user.email,
                user_name=user.name,
                otp_code=otp_code
            )

            return otp_code

        except Exception as e:
            await self.db.rollback()
            raise e

    def create_access_token(self, user: User) -> str:
        token_data = {
            "sub": user.id,
            "email": user.email,
            "is_verified": user.is_verified
        }

        return create_access_token(
            data=token_data,
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
