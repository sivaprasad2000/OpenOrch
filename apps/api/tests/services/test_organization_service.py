import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.organization import OrganizationCreate, OrganizationUpdate
from app.services.organization_service import OrganizationService


@pytest.mark.asyncio
async def test_create_organization(db_session: AsyncSession) -> None:
    service = OrganizationService(db_session)
    org_data = OrganizationCreate(name="Test Organization")

    organization = await service.create_organization(org_data)

    assert organization.id is not None
    assert organization.name == "Test Organization"


@pytest.mark.asyncio
async def test_create_organization_duplicate_name(db_session: AsyncSession) -> None:
    service = OrganizationService(db_session)
    org_data = OrganizationCreate(name="Duplicate Org")

    await service.create_organization(org_data)

    with pytest.raises(ValueError, match="already exists"):
        await service.create_organization(org_data)


@pytest.mark.asyncio
async def test_get_organization_by_id(db_session: AsyncSession) -> None:
    service = OrganizationService(db_session)
    org_data = OrganizationCreate(name="Get By ID Org")

    created_org = await service.create_organization(org_data)
    found_org = await service.get_organization_by_id(created_org.id)

    assert found_org is not None
    assert found_org.id == created_org.id
    assert found_org.name == created_org.name


@pytest.mark.asyncio
async def test_get_organization_by_id_not_found(db_session: AsyncSession) -> None:
    service = OrganizationService(db_session)

    organization = await service.get_organization_by_id(99999)

    assert organization is None


@pytest.mark.asyncio
async def test_get_organization_by_name(db_session: AsyncSession) -> None:
    service = OrganizationService(db_session)
    org_data = OrganizationCreate(name="Find By Name")

    created_org = await service.create_organization(org_data)
    found_org = await service.get_organization_by_name("Find By Name")

    assert found_org is not None
    assert found_org.name == created_org.name


@pytest.mark.asyncio
async def test_get_organizations(db_session: AsyncSession) -> None:
    service = OrganizationService(db_session)

    for i in range(5):
        org_data = OrganizationCreate(name=f"Organization {i}")
        await service.create_organization(org_data)

    organizations = await service.get_organizations(skip=0, limit=10)

    assert len(organizations) == 5


@pytest.mark.asyncio
async def test_update_organization(db_session: AsyncSession) -> None:
    service = OrganizationService(db_session)
    org_data = OrganizationCreate(name="Original Name")

    created_org = await service.create_organization(org_data)

    update_data = OrganizationUpdate(name="Updated Name")
    updated_org = await service.update_organization(created_org.id, update_data)

    assert updated_org is not None
    assert updated_org.name == "Updated Name"


@pytest.mark.asyncio
async def test_update_organization_duplicate_name(db_session: AsyncSession) -> None:
    service = OrganizationService(db_session)

    await service.create_organization(OrganizationCreate(name="Org One"))
    org2 = await service.create_organization(OrganizationCreate(name="Org Two"))

    update_data = OrganizationUpdate(name="Org One")

    with pytest.raises(ValueError, match="already exists"):
        await service.update_organization(org2.id, update_data)


@pytest.mark.asyncio
async def test_delete_organization(db_session: AsyncSession) -> None:
    service = OrganizationService(db_session)
    org_data = OrganizationCreate(name="To Delete")

    created_org = await service.create_organization(org_data)
    result = await service.delete_organization(created_org.id)

    assert result is True

    found_org = await service.get_organization_by_id(created_org.id)
    assert found_org is None


@pytest.mark.asyncio
async def test_delete_organization_not_found(db_session: AsyncSession) -> None:
    service = OrganizationService(db_session)

    result = await service.delete_organization(99999)

    assert result is False


@pytest.mark.asyncio
async def test_search_organizations(db_session: AsyncSession) -> None:
    service = OrganizationService(db_session)

    orgs_data = [
        "Acme Corporation",
        "Acme Industries",
        "Global Systems",
    ]

    for name in orgs_data:
        org_data = OrganizationCreate(name=name)
        await service.create_organization(org_data)

    results = await service.search_organizations("acme")

    assert len(results) == 2
    assert all("acme" in org.name.lower() for org in results)
