
import logging
from typing import Optional
from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:

    def __init__(self) -> None:
        self.is_development = settings.ENVIRONMENT == "development"

    async def send_verification_email(
        self,
        to_email: str,
        user_name: str,
        otp_code: str
    ) -> bool:
        if self.is_development:
            return await self._mock_send_email(to_email, user_name, otp_code)
        else:
            return await self._send_email_production(to_email, user_name, otp_code)

    async def _mock_send_email(
        self,
        to_email: str,
        user_name: str,
        otp_code: str
    ) -> bool:
        print("\n" + "=" * 70)
        print("📧 EMAIL VERIFICATION (DEVELOPMENT MODE)")
        print("=" * 70)
        print(f"To: {to_email}")
        print(f"Name: {user_name}")
        print(f"\nYour verification code is: {otp_code}")
        print(f"\nThis code will expire in 10 minutes.")
        print("=" * 70 + "\n")

        logger.info(
            f"Mock email sent to {to_email} with OTP: {otp_code}"
        )

        return True

    async def _send_email_production(
        self,
        to_email: str,
        user_name: str,
        otp_code: str
    ) -> bool:
        logger.warning(
            "Production email sending not implemented yet. "
            f"Would send OTP {otp_code} to {to_email}"
        )


        return False

    async def send_welcome_email(self, to_email: str, user_name: str) -> bool:
        if self.is_development:
            print("\n" + "=" * 70)
            print("📧 WELCOME EMAIL (DEVELOPMENT MODE)")
            print("=" * 70)
            print(f"To: {to_email}")
            print(f"Name: {user_name}")
            print(f"\nWelcome to {settings.APP_NAME}!")
            print("Your email has been verified successfully.")
            print("=" * 70 + "\n")

            logger.info(f"Mock welcome email sent to {to_email}")
            return True

        return False
