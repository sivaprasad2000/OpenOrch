from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    def __init__(self, model: type[ModelType], db: AsyncSession) -> None:
        self.model = model
        self.db = db

    async def create(self, obj: ModelType) -> ModelType:
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def get_by_id(self, item_id: Any) -> ModelType | None:
        result = await self.db.execute(
            select(self.model).where(self.model.id == item_id)  # type: ignore[attr-defined]
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        order_by: Any | None = None,
    ) -> list[ModelType]:
        query = select(self.model).offset(skip).limit(limit)

        if order_by is not None:
            query = query.order_by(order_by)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update(self, obj: ModelType) -> ModelType:
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def delete(self, obj: ModelType) -> None:
        await self.db.delete(obj)
        await self.db.flush()

    async def count(self) -> int:
        result = await self.db.execute(select(func.count()).select_from(self.model))
        return result.scalar() or 0

    async def exists(self, item_id: Any) -> bool:
        result = await self.db.execute(
            select(func.count()).select_from(self.model).where(self.model.id == item_id)  # type: ignore[attr-defined]
        )
        count = result.scalar() or 0
        return count > 0
