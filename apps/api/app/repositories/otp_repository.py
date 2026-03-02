
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.otp import OTP
from app.repositories.base import BaseRepository


class OTPRepository(BaseRepository[OTP]):

    def __init__(self, db: AsyncSession):
        super().__init__(OTP, db)

    async def get_valid_otp(self, user_id: str, code: str) -> Optional[OTP]:
        result = await self.db.execute(
            select(OTP).where(
                and_(
                    OTP.user_id == user_id,
                    OTP.code == code,
                    OTP.is_used == False,
                    OTP.expires_at > datetime.now(timezone.utc),
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_latest_otp(self, user_id: str) -> Optional[OTP]:
        result = await self.db.execute(
            select(OTP)
            .where(OTP.user_id == user_id)
            .order_by(OTP.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def invalidate_user_otps(self, user_id: str) -> None:
        result = await self.db.execute(
            select(OTP).where(
                and_(
                    OTP.user_id == user_id,
                    OTP.is_used == False,
                )
            )
        )
        otps = result.scalars().all()

        for otp in otps:
            otp.is_used = True

        await self.db.flush()
