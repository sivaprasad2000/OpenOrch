from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.repositories.user_organization_repository import UserOrganizationRepository
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate, UserUpdate


class UserService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.user_repo = UserRepository(db)
        self.user_org_repo = UserOrganizationRepository(db)

    async def create_user(self, user_data: UserCreate) -> User:
        if await self.user_repo.email_exists(user_data.email):
            raise ValueError("User with this email already exists")

        hashed_password = get_password_hash(user_data.password)

        user_id = User.generate_id_from_email(user_data.email)

        user = User(
            id=user_id,
            email=user_data.email.lower(),
            name=user_data.name,
            password=hashed_password,
            is_verified=False,
        )

        try:
            created_user = await self.user_repo.create(user)
            await self.db.commit()
            return created_user
        except Exception:
            await self.db.rollback()
            raise

    async def get_user_by_id(self, user_id: str) -> User | None:
        return await self.user_repo.get_by_id(user_id)

    async def get_user_with_organizations(self, user_id: str) -> User | None:
        return await self.user_repo.get_by_id_with_organizations(user_id)

    async def get_user_by_email(self, email: str) -> User | None:
        return await self.user_repo.get_by_email(email)

    async def get_users(self, skip: int = 0, limit: int = 100) -> list[User]:
        return await self.user_repo.get_all(skip=skip, limit=limit, order_by=User.created_at.desc())

    async def update_user(self, user_id: str, user_data: UserUpdate) -> User | None:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            return None

        try:
            if user_data.email is not None and user_data.email.lower() != user.email:
                if await self.user_repo.email_exists(user_data.email):
                    raise ValueError("Email already exists")

                user.email = user_data.email.lower()
                user.id = User.generate_id_from_email(user.email)

            if user_data.name is not None:
                user.name = user_data.name

            if user_data.password is not None:
                user.password = get_password_hash(user_data.password)

            updated_user = await self.user_repo.update(user)
            await self.db.commit()
            return updated_user

        except Exception:
            await self.db.rollback()
            raise

    async def delete_user(self, user_id: str) -> bool:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            return False

        try:
            await self.user_repo.delete(user)
            await self.db.commit()
            return True
        except Exception:
            await self.db.rollback()
            raise

    async def verify_user_email(self, user_id: str) -> User | None:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            return None

        try:
            user.is_verified = True
            updated_user = await self.user_repo.update(user)
            await self.db.commit()
            return updated_user
        except Exception:
            await self.db.rollback()
            raise

    async def authenticate_user(self, email: str, password: str) -> User | None:
        user = await self.user_repo.get_by_email(email)

        if not user:
            return None

        if not verify_password(password, user.password):
            return None

        return user

    async def get_verified_users(self, skip: int = 0, limit: int = 100) -> list[User]:
        return await self.user_repo.get_verified_users(skip=skip, limit=limit)

    async def get_unverified_users(self, skip: int = 0, limit: int = 100) -> list[User]:
        return await self.user_repo.get_unverified_users(skip=skip, limit=limit)

    async def search_users_by_name(self, name: str, skip: int = 0, limit: int = 100) -> list[User]:
        return await self.user_repo.search_by_name(name=name, skip=skip, limit=limit)

    async def set_active_organization(self, user_id: str, organization_id: str) -> User | None:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            return None

        if not await self.user_org_repo.membership_exists(user_id, organization_id):
            raise ValueError("User is not a member of this organization")

        try:
            user.active_organization_id = organization_id
            updated_user = await self.user_repo.update(user)
            await self.db.commit()
            return updated_user
        except Exception:
            await self.db.rollback()
            raise
