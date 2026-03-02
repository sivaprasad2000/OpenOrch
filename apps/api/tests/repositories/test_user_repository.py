import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.models.user import User
from app.repositories.user_repository import UserRepository


@pytest.mark.asyncio
async def test_create_user(db_session: AsyncSession):
    repo = UserRepository(db_session)

    user = User(
        id=User.generate_id_from_email("test@example.com"),
        email="test@example.com",
        name="Test User",
        password=get_password_hash("password123"),
        is_verified=False,
    )

    created_user = await repo.create(user)
    await db_session.commit()

    assert created_user.id is not None
    assert created_user.email == "test@example.com"
    assert created_user.name == "Test User"
    assert created_user.is_verified is False


@pytest.mark.asyncio
async def test_get_user_by_id(db_session: AsyncSession):
    repo = UserRepository(db_session)

    user_id = User.generate_id_from_email("test@example.com")
    user = User(
        id=user_id,
        email="test@example.com",
        name="Test User",
        password=get_password_hash("password123"),
        is_verified=False,
    )
    await repo.create(user)
    await db_session.commit()

    found_user = await repo.get_by_id(user_id)

    assert found_user is not None
    assert found_user.id == user_id
    assert found_user.email == "test@example.com"


@pytest.mark.asyncio
async def test_get_user_by_email(db_session: AsyncSession):
    repo = UserRepository(db_session)

    user = User(
        id=User.generate_id_from_email("test@example.com"),
        email="test@example.com",
        name="Test User",
        password=get_password_hash("password123"),
        is_verified=False,
    )
    await repo.create(user)
    await db_session.commit()

    found_user = await repo.get_by_email("test@example.com")

    assert found_user is not None
    assert found_user.email == "test@example.com"
    assert found_user.name == "Test User"


@pytest.mark.asyncio
async def test_get_user_by_email_case_insensitive(db_session: AsyncSession):
    repo = UserRepository(db_session)

    user = User(
        id=User.generate_id_from_email("test@example.com"),
        email="test@example.com",
        name="Test User",
        password=get_password_hash("password123"),
        is_verified=False,
    )
    await repo.create(user)
    await db_session.commit()

    found_user = await repo.get_by_email("TEST@EXAMPLE.COM")

    assert found_user is not None
    assert found_user.email == "test@example.com"


@pytest.mark.asyncio
async def test_email_exists(db_session: AsyncSession):
    repo = UserRepository(db_session)

    user = User(
        id=User.generate_id_from_email("test@example.com"),
        email="test@example.com",
        name="Test User",
        password=get_password_hash("password123"),
        is_verified=False,
    )
    await repo.create(user)
    await db_session.commit()

    assert await repo.email_exists("test@example.com") is True
    assert await repo.email_exists("nonexistent@example.com") is False


@pytest.mark.asyncio
async def test_get_all_users(db_session: AsyncSession):
    repo = UserRepository(db_session)

    for i in range(5):
        user = User(
            id=User.generate_id_from_email(f"user{i}@example.com"),
            email=f"user{i}@example.com",
            name=f"User {i}",
            password=get_password_hash("password123"),
            is_verified=False,
        )
        await repo.create(user)
    await db_session.commit()

    users = await repo.get_all(skip=0, limit=10)

    assert len(users) == 5


@pytest.mark.asyncio
async def test_update_user(db_session: AsyncSession):
    repo = UserRepository(db_session)

    user = User(
        id=User.generate_id_from_email("test@example.com"),
        email="test@example.com",
        name="Test User",
        password=get_password_hash("password123"),
        is_verified=False,
    )
    created_user = await repo.create(user)
    await db_session.commit()

    created_user.name = "Updated Name"
    updated_user = await repo.update(created_user)
    await db_session.commit()

    assert updated_user.name == "Updated Name"


@pytest.mark.asyncio
async def test_delete_user(db_session: AsyncSession):
    repo = UserRepository(db_session)

    user = User(
        id=User.generate_id_from_email("test@example.com"),
        email="test@example.com",
        name="Test User",
        password=get_password_hash("password123"),
        is_verified=False,
    )
    await repo.create(user)
    await db_session.commit()

    await repo.delete(user)
    await db_session.commit()

    found_user = await repo.get_by_email("test@example.com")
    assert found_user is None


@pytest.mark.asyncio
async def test_get_verified_users(db_session: AsyncSession):
    repo = UserRepository(db_session)

    for i in range(3):
        user = User(
            id=User.generate_id_from_email(f"verified{i}@example.com"),
            email=f"verified{i}@example.com",
            name=f"Verified User {i}",
            password=get_password_hash("password123"),
            is_verified=True,
        )
        await repo.create(user)

    for i in range(2):
        user = User(
            id=User.generate_id_from_email(f"unverified{i}@example.com"),
            email=f"unverified{i}@example.com",
            name=f"Unverified User {i}",
            password=get_password_hash("password123"),
            is_verified=False,
        )
        await repo.create(user)

    await db_session.commit()

    verified_users = await repo.get_verified_users()

    assert len(verified_users) == 3
    assert all(user.is_verified for user in verified_users)


@pytest.mark.asyncio
async def test_search_by_name(db_session: AsyncSession):
    repo = UserRepository(db_session)

    users_data = [
        ("john@example.com", "John Doe"),
        ("jane@example.com", "Jane Smith"),
        ("johnny@example.com", "Johnny Walker"),
    ]

    for email, name in users_data:
        user = User(
            id=User.generate_id_from_email(email),
            email=email,
            name=name,
            password=get_password_hash("password123"),
            is_verified=False,
        )
        await repo.create(user)
    await db_session.commit()

    results = await repo.search_by_name("john")

    assert len(results) == 2
    assert all("john" in user.name.lower() for user in results)
