from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.models.user_organization import OrgRole, UserOrganization
from app.repositories.llm_repository import LLMRepository
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.user_organization_repository import UserOrganizationRepository
from app.schemas.organization import OrganizationCreate, OrganizationUpdate


class OrganizationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.org_repo = OrganizationRepository(db)
        self.user_org_repo = UserOrganizationRepository(db)
        self.llm_repo = LLMRepository(db)

    async def create_organization(
        self, org_data: OrganizationCreate, creator_user_id: str | None = None
    ) -> Organization:
        existing = await self.org_repo.get_by_name(org_data.name)
        if existing:
            raise ValueError("Organization name already exists")

        organization = Organization(name=org_data.name)

        try:
            created_org = await self.org_repo.create(organization)
            if creator_user_id:
                membership = UserOrganization(
                    user_id=creator_user_id,
                    organization_id=created_org.id,
                    role=OrgRole.OWNER,
                )
                await self.user_org_repo.create(membership)
            await self.db.commit()
            return created_org
        except Exception:
            await self.db.rollback()
            raise

    async def get_organization_by_id(self, org_id: str) -> Organization | None:
        return await self.org_repo.get_by_id(org_id)

    async def get_organization_by_name(self, name: str) -> Organization | None:
        return await self.org_repo.get_by_name(name)

    async def get_organizations(self, skip: int = 0, limit: int = 100) -> list[Organization]:
        return await self.org_repo.get_all(
            skip=skip, limit=limit, order_by=Organization.created_at.desc()
        )

    async def update_organization(
        self, org_id: str, org_data: OrganizationUpdate
    ) -> Organization | None:
        organization = await self.org_repo.get_by_id(org_id)
        if not organization:
            return None

        try:
            existing_org = await self.org_repo.get_by_name(org_data.name)
            if existing_org and existing_org.id != org_id:
                raise ValueError("Organization name already exists")

            organization.name = org_data.name

            updated_org = await self.org_repo.update(organization)
            await self.db.commit()
            return updated_org

        except Exception:
            await self.db.rollback()
            raise

    async def delete_organization(self, org_id: str) -> bool:
        organization = await self.org_repo.get_by_id(org_id)
        if not organization:
            return False

        try:
            await self.org_repo.delete(organization)
            await self.db.commit()
            return True
        except Exception:
            await self.db.rollback()
            raise

    async def search_organizations(
        self, name: str, skip: int = 0, limit: int = 100
    ) -> list[Organization]:
        return await self.org_repo.search_by_name(name=name, skip=skip, limit=limit)

    async def set_active_llm(
        self,
        requester_id: str,
        organization_id: str,
        llm_id: str | None,
    ) -> Organization:
        membership = await self.user_org_repo.get_by_user_and_org(requester_id, organization_id)
        if not membership:
            raise ValueError("You are not a member of this organization")
        if membership.role not in (OrgRole.OWNER, OrgRole.ADMIN):
            raise PermissionError("Only admins and owners can set the active LLM")

        organization = await self.org_repo.get_by_id(organization_id)
        if not organization:
            raise ValueError("Organization not found")

        if llm_id is not None:
            llm = await self.llm_repo.get_by_id(llm_id)
            if not llm or llm.organization_id != organization_id:
                raise ValueError("LLM not found in this organization")

        try:
            organization.active_llm_id = llm_id
            updated = await self.org_repo.update(organization)
            await self.db.commit()
            return updated
        except Exception:
            await self.db.rollback()
            raise

    async def assign_role(
        self,
        requester_id: str,
        organization_id: str,
        target_user_id: str,
        role: OrgRole,
    ) -> UserOrganization:
        if role == OrgRole.OWNER:
            raise ValueError("Owner role cannot be assigned")

        requester_membership = await self.user_org_repo.get_by_user_and_org(
            requester_id, organization_id
        )
        if not requester_membership:
            raise ValueError("You are not a member of this organization")

        if role == OrgRole.ADMIN and requester_membership.role != OrgRole.OWNER:
            raise ValueError("Only the owner can assign admin role")

        target_membership = await self.user_org_repo.get_by_user_and_org(
            target_user_id, organization_id
        )
        if not target_membership:
            raise ValueError("Target user is not a member of this organization")

        if target_membership.role == OrgRole.OWNER:
            raise ValueError("Cannot change the owner's role")

        try:
            target_membership.role = role
            updated = await self.user_org_repo.update(target_membership)
            await self.db.commit()
            return updated
        except Exception:
            await self.db.rollback()
            raise
