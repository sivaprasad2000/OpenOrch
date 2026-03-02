
import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.models.user import User


def setup_user_with_org(
    client: TestClient,
    email: str = "testuser@example.com",
    org_name: str = "Test Org",
) -> dict:
    client.post(
        "/api/v1/auth/signup",
        json={"email": email, "name": "Test User", "password": "password123"},
    )

    user_id = User.generate_id_from_email(email)
    token = create_access_token({"sub": user_id, "email": email})
    headers = {"Authorization": f"Bearer {token}"}

    org_resp = client.post(
        "/api/v1/organizations",
        json={"name": org_name},
        headers=headers,
    )
    org_id = org_resp.json()["id"]

    client.put(
        "/api/v1/users/me/active-organization",
        json={"organization_id": org_id},
        headers=headers,
    )

    return {"user_id": user_id, "token": token, "headers": headers, "org_id": org_id}


@pytest.fixture
def auth(client: TestClient) -> dict:
    return setup_user_with_org(client)


@pytest.fixture
def auth2(client: TestClient) -> dict:
    return setup_user_with_org(client, email="otheruser@example.com", org_name="Test Org 2")
