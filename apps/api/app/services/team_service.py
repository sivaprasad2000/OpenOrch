
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.team import Team
from app.models.user_organization import OrgRole
from app.repositories.team_repository import TeamRepository
from app.repositories.user_organization_repository import UserOrganizationRepository
from app.repositories.user_repository import UserRepository
from app.schemas.team import TeamCreate, TeamUpdate


class TeamService:

    def __init__(self, db: AsyncSession):
        self.db = db
        self.team_repo = TeamRepository(db)
        self.user_repo = UserRepository(db)
        self.user_org_repo = UserOrganizationRepository(db)

    async def create_team(self, user_id: str, data: TeamCreate) -> Team:
        user = await self.user_repo.get_by_id(user_id)
        if not user or not user.active_organization_id:
            raise ValueError("No active organization set")

        org_id = user.active_organization_id

        membership = await self.user_org_repo.get_by_user_and_org(user_id, org_id)
        if not membership:
            raise ValueError("You are not a member of this organization")

        is_privileged = membership.role in (OrgRole.OWNER, OrgRole.ADMIN)

        if data.parent_team_id:
            parent = await self.team_repo.get_by_id_and_org(data.parent_team_id, org_id)
            if not parent:
                raise ValueError("Parent team not found in active organization")

            if not is_privileged:
                if not user.team_id or user.team_id != data.parent_team_id:  # type: ignore[attr-defined]
                    raise ValueError(
                        "Members can only create teams under their own team"
                    )
        elif not is_privileged:
            raise ValueError(
                "Only owner or admin can create top-level teams"
            )

        team = Team(
            organization_id=org_id,
            parent_team_id=data.parent_team_id,
            name=data.name,
        )

        try:
            created = await self.team_repo.create(team)
            await self.db.commit()
            return created
        except Exception as e:
            await self.db.rollback()
            raise e

    async def update_team(
        self, user_id: str, team_id: str, data: TeamUpdate
    ) -> Optional[Team]:
        user = await self.user_repo.get_by_id(user_id)
        if not user or not user.active_organization_id:
            raise ValueError("No active organization set")

        org_id = user.active_organization_id

        membership = await self.user_org_repo.get_by_user_and_org(user_id, org_id)
        if not membership or membership.role not in (OrgRole.OWNER, OrgRole.ADMIN):
            raise ValueError("Only owner or admin can update teams")

        team = await self.team_repo.get_by_id_and_org(team_id, org_id)
        if not team:
            return None

        if data.parent_team_id is not None:
            if data.parent_team_id == team_id:
                raise ValueError("A team cannot be its own parent")
            parent = await self.team_repo.get_by_id_and_org(data.parent_team_id, org_id)
            if not parent:
                raise ValueError("Parent team not found in active organization")
            team.parent_team_id = data.parent_team_id

        if data.name is not None:
            team.name = data.name

        try:
            updated = await self.team_repo.update(team)
            await self.db.commit()
            return updated
        except Exception as e:
            await self.db.rollback()
            raise e
