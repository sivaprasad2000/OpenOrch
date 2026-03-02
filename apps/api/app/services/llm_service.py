
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm import LLM
from app.repositories.llm_repository import LLMRepository
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.schemas.llm import LLMCreate, LLMResponse, LLMUpdate


class LLMService:

    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm_repo = LLMRepository(db)
        self.user_repo = UserRepository(db)
        self.org_repo = OrganizationRepository(db)

    async def create_llm(self, user_id: str, llm_data: LLMCreate) -> LLM:
        user = await self.user_repo.get_by_id(user_id)
        if not user or not user.active_organization_id:
            raise ValueError("No active organization set")

        llm = LLM(
            organization_id=user.active_organization_id,
            name=llm_data.name,
            provider=llm_data.provider,
            api_key=llm_data.api_key,
            model_name=llm_data.model_name,
        )

        try:
            created_llm = await self.llm_repo.create(llm)
            await self.db.commit()
            return created_llm
        except Exception as e:
            await self.db.rollback()
            raise e

    async def list_llms(self, user_id: str) -> list[LLMResponse]:
        user = await self.user_repo.get_by_id(user_id)
        if not user or not user.active_organization_id:
            raise ValueError("No active organization set")

        org = await self.org_repo.get_by_id(user.active_organization_id)
        active_llm_id = org.active_llm_id if org else None

        llms = await self.llm_repo.get_by_organization_id(user.active_organization_id)
        return [
            LLMResponse.model_validate(llm).model_copy(
                update={"is_active": llm.id == active_llm_id}
            )
            for llm in llms
        ]

    async def update_llm(self, user_id: str, llm_id: str, data: LLMUpdate) -> LLM | None:
        user = await self.user_repo.get_by_id(user_id)
        if not user or not user.active_organization_id:
            raise ValueError("No active organization set")

        llm = await self.llm_repo.get_by_id(llm_id)
        if not llm or llm.organization_id != user.active_organization_id:
            return None

        if data.name is not None:
            llm.name = data.name
        if data.api_key is not None:
            llm.api_key = data.api_key
        if data.model_name is not None:
            llm.model_name = data.model_name

        try:
            updated = await self.llm_repo.update(llm)
            await self.db.commit()
            return updated
        except Exception:
            await self.db.rollback()
            raise

    async def delete_llm(self, user_id: str, llm_id: str) -> bool:
        user = await self.user_repo.get_by_id(user_id)
        if not user or not user.active_organization_id:
            raise ValueError("No active organization set")

        llm = await self.llm_repo.get_by_id(llm_id)
        if not llm or llm.organization_id != user.active_organization_id:
            return False

        try:
            await self.llm_repo.delete(llm)
            await self.db.commit()
            return True
        except Exception as e:
            await self.db.rollback()
            raise e
