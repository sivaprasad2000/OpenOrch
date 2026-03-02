import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.repositories.organization_repository import OrganizationRepository


@pytest.mark.asyncio
async def test_create_organization(db_session: AsyncSession) -> None:
    repo = OrganizationRepository(db_session)

    organization = Organization(name="Test Organization")

    created_org = await repo.create(organization)
    await db_session.commit()

    assert created_org.id is not None
    assert created_org.name == "Test Organization"


@pytest.mark.asyncio
async def test_get_organization_by_id(db_session: AsyncSession) -> None:
    repo = OrganizationRepository(db_session)

    organization = Organization(name="Test Org")
    created_org = await repo.create(organization)
    await db_session.commit()

    found_org = await repo.get_by_id(created_org.id)

    assert found_org is not None
    assert found_org.id == created_org.id
    assert found_org.name == "Test Org"


@pytest.mark.asyncio
async def test_get_organization_by_name(db_session: AsyncSession) -> None:
    repo = OrganizationRepository(db_session)

    organization = Organization(name="Unique Org Name")
    await repo.create(organization)
    await db_session.commit()

    found_org = await repo.get_by_name("Unique Org Name")

    assert found_org is not None
    assert found_org.name == "Unique Org Name"


@pytest.mark.asyncio
async def test_name_exists(db_session: AsyncSession) -> None:
    repo = OrganizationRepository(db_session)

    organization = Organization(name="Existing Org")
    await repo.create(organization)
    await db_session.commit()

    assert await repo.name_exists("Existing Org") is True
    assert await repo.name_exists("Non-Existent Org") is False


@pytest.mark.asyncio
async def test_get_all_organizations(db_session: AsyncSession) -> None:
    repo = OrganizationRepository(db_session)

    for i in range(5):
        org = Organization(name=f"Organization {i}")
        await repo.create(org)
    await db_session.commit()

    orgs = await repo.get_all(skip=0, limit=10)

    assert len(orgs) == 5


@pytest.mark.asyncio
async def test_update_organization(db_session: AsyncSession) -> None:
    repo = OrganizationRepository(db_session)

    organization = Organization(name="Original Name")
    created_org = await repo.create(organization)
    await db_session.commit()

    created_org.name = "Updated Name"
    updated_org = await repo.update(created_org)
    await db_session.commit()

    assert updated_org.name == "Updated Name"


@pytest.mark.asyncio
async def test_delete_organization(db_session: AsyncSession) -> None:
    repo = OrganizationRepository(db_session)

    organization = Organization(name="To Be Deleted")
    created_org = await repo.create(organization)
    await db_session.commit()

    await repo.delete(created_org)
    await db_session.commit()

    found_org = await repo.get_by_name("To Be Deleted")
    assert found_org is None


@pytest.mark.asyncio
async def test_search_by_name(db_session: AsyncSession) -> None:
    repo = OrganizationRepository(db_session)

    orgs_data = [
        "Acme Corporation",
        "Acme Industries",
        "Global Systems",
    ]

    for name in orgs_data:
        org = Organization(name=name)
        await repo.create(org)
    await db_session.commit()

    results = await repo.search_by_name("acme")

    assert len(results) == 2
    assert all("acme" in org.name.lower() for org in results)
