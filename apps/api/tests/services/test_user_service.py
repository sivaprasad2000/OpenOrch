import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password
from app.schemas.user import UserCreate, UserUpdate
from app.services.user_service import UserService


@pytest.mark.asyncio
async def test_create_user(db_session: AsyncSession, sample_user_data: dict):
    service = UserService(db_session)
    user_data = UserCreate(**sample_user_data)

    user = await service.create_user(user_data)

    assert user.id is not None
    assert user.email == sample_user_data["email"].lower()
    assert user.name == sample_user_data["name"]
    assert user.is_verified is False
    assert verify_password(sample_user_data["password"], user.password)


@pytest.mark.asyncio
async def test_create_user_duplicate_email(db_session: AsyncSession, sample_user_data: dict):
    service = UserService(db_session)
    user_data = UserCreate(**sample_user_data)

    await service.create_user(user_data)

    with pytest.raises(ValueError, match="already exists"):
        await service.create_user(user_data)


@pytest.mark.asyncio
async def test_get_user_by_id(db_session: AsyncSession, sample_user_data: dict):
    service = UserService(db_session)
    user_data = UserCreate(**sample_user_data)

    created_user = await service.create_user(user_data)
    found_user = await service.get_user_by_id(created_user.id)

    assert found_user is not None
    assert found_user.id == created_user.id
    assert found_user.email == created_user.email


@pytest.mark.asyncio
async def test_get_user_by_id_not_found(db_session: AsyncSession):
    service = UserService(db_session)

    user = await service.get_user_by_id("nonexistent-id")

    assert user is None


@pytest.mark.asyncio
async def test_get_user_by_email(db_session: AsyncSession, sample_user_data: dict):
    service = UserService(db_session)
    user_data = UserCreate(**sample_user_data)

    created_user = await service.create_user(user_data)
    found_user = await service.get_user_by_email(sample_user_data["email"])

    assert found_user is not None
    assert found_user.email == created_user.email


@pytest.mark.asyncio
async def test_get_users(db_session: AsyncSession):
    service = UserService(db_session)

    for i in range(5):
        user_data = UserCreate(
            email=f"user{i}@example.com", name=f"User {i}", password="password123"
        )
        await service.create_user(user_data)

    users = await service.get_users(skip=0, limit=10)

    assert len(users) == 5


@pytest.mark.asyncio
async def test_update_user(db_session: AsyncSession, sample_user_data: dict):
    service = UserService(db_session)
    user_data = UserCreate(**sample_user_data)

    created_user = await service.create_user(user_data)

    update_data = UserUpdate(name="Updated Name")
    updated_user = await service.update_user(created_user.id, update_data)

    assert updated_user is not None
    assert updated_user.name == "Updated Name"
    assert updated_user.email == created_user.email


@pytest.mark.asyncio
async def test_update_user_email(db_session: AsyncSession, sample_user_data: dict):
    service = UserService(db_session)
    user_data = UserCreate(**sample_user_data)

    created_user = await service.create_user(user_data)
    original_id = created_user.id

    update_data = UserUpdate(email="newemail@example.com")
    updated_user = await service.update_user(created_user.id, update_data)

    assert updated_user is not None
    assert updated_user.email == "newemail@example.com"
    assert updated_user.id != original_id


@pytest.mark.asyncio
async def test_update_user_duplicate_email(
    db_session: AsyncSession, sample_user_data: dict, sample_user_data_2: dict
):
    service = UserService(db_session)

    await service.create_user(UserCreate(**sample_user_data))
    user2 = await service.create_user(UserCreate(**sample_user_data_2))

    update_data = UserUpdate(email=sample_user_data["email"])

    with pytest.raises(ValueError, match="already exists"):
        await service.update_user(user2.id, update_data)


@pytest.mark.asyncio
async def test_delete_user(db_session: AsyncSession, sample_user_data: dict):
    service = UserService(db_session)
    user_data = UserCreate(**sample_user_data)

    created_user = await service.create_user(user_data)
    result = await service.delete_user(created_user.id)

    assert result is True

    found_user = await service.get_user_by_id(created_user.id)
    assert found_user is None


@pytest.mark.asyncio
async def test_delete_user_not_found(db_session: AsyncSession):
    service = UserService(db_session)

    result = await service.delete_user("nonexistent-id")

    assert result is False


@pytest.mark.asyncio
async def test_verify_user_email(db_session: AsyncSession, sample_user_data: dict):
    service = UserService(db_session)
    user_data = UserCreate(**sample_user_data)

    created_user = await service.create_user(user_data)
    assert created_user.is_verified is False

    verified_user = await service.verify_user_email(created_user.id)

    assert verified_user is not None
    assert verified_user.is_verified is True


@pytest.mark.asyncio
async def test_authenticate_user(db_session: AsyncSession, sample_user_data: dict):
    service = UserService(db_session)
    user_data = UserCreate(**sample_user_data)

    await service.create_user(user_data)

    authenticated_user = await service.authenticate_user(
        sample_user_data["email"], sample_user_data["password"]
    )

    assert authenticated_user is not None
    assert authenticated_user.email == sample_user_data["email"].lower()


@pytest.mark.asyncio
async def test_authenticate_user_wrong_password(db_session: AsyncSession, sample_user_data: dict):
    service = UserService(db_session)
    user_data = UserCreate(**sample_user_data)

    await service.create_user(user_data)

    authenticated_user = await service.authenticate_user(sample_user_data["email"], "wrongpassword")

    assert authenticated_user is None


@pytest.mark.asyncio
async def test_authenticate_user_not_found(db_session: AsyncSession):
    service = UserService(db_session)

    authenticated_user = await service.authenticate_user("nonexistent@example.com", "password123")

    assert authenticated_user is None


@pytest.mark.asyncio
async def test_get_verified_users(db_session: AsyncSession):
    service = UserService(db_session)

    for i in range(3):
        user_data = UserCreate(
            email=f"verified{i}@example.com", name=f"Verified {i}", password="password123"
        )
        user = await service.create_user(user_data)
        await service.verify_user_email(user.id)

    for i in range(2):
        user_data = UserCreate(
            email=f"unverified{i}@example.com", name=f"Unverified {i}", password="password123"
        )
        await service.create_user(user_data)

    verified_users = await service.get_verified_users()

    assert len(verified_users) == 3
    assert all(user.is_verified for user in verified_users)


@pytest.mark.asyncio
async def test_search_users_by_name(db_session: AsyncSession):
    service = UserService(db_session)

    users_data = [
        ("john@example.com", "John Doe"),
        ("jane@example.com", "Jane Smith"),
        ("johnny@example.com", "Johnny Walker"),
    ]

    for email, name in users_data:
        user_data = UserCreate(email=email, name=name, password="password123")
        await service.create_user(user_data)

    results = await service.search_users_by_name("john")

    assert len(results) == 2
    assert all("john" in user.name.lower() for user in results)
