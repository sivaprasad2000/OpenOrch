from fastapi.testclient import TestClient
import pytest

from app.core.security import create_access_token

_SKIP_UNIMPLEMENTED = pytest.mark.skip(reason="Endpoint not implemented in current API")


@_SKIP_UNIMPLEMENTED
def test_create_user(client: TestClient):
    response = client.post(
        "/api/v1/users",
        json={"email": "test@example.com", "name": "Test User", "password": "securepassword123"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["name"] == "Test User"
    assert data["is_verified"] is False
    assert "password" not in data
    assert "id" in data


@_SKIP_UNIMPLEMENTED
def test_create_user_duplicate_email(client: TestClient):
    user_data = {"email": "duplicate@example.com", "name": "User One", "password": "password123"}

    response1 = client.post("/api/v1/users", json=user_data)
    assert response1.status_code == 201

    response2 = client.post("/api/v1/users", json=user_data)
    assert response2.status_code == 400
    assert "already exists" in response2.json()["detail"].lower()


@_SKIP_UNIMPLEMENTED
def test_create_user_invalid_email(client: TestClient):
    response = client.post(
        "/api/v1/users",
        json={"email": "invalid-email", "name": "Test User", "password": "password123"},
    )
    assert response.status_code == 422


@_SKIP_UNIMPLEMENTED
def test_create_user_short_password(client: TestClient):
    response = client.post(
        "/api/v1/users",
        json={"email": "test@example.com", "name": "Test User", "password": "short"},
    )
    assert response.status_code == 422


def test_get_me(client: TestClient):
    client.post(
        "/api/v1/auth/signup",
        json={
            "email": "getme@example.com",
            "name": "Get Me Test",
            "password": "password123",
        },
    )

    from app.models.user import User

    user_id = User.generate_id_from_email("getme@example.com")
    token = create_access_token({"sub": user_id, "email": "getme@example.com"})

    response = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == user_id
    assert data["email"] == "getme@example.com"
    assert data["name"] == "Get Me Test"
    assert "organizations" in data
    assert isinstance(data["organizations"], list)


def test_get_me_not_found(client: TestClient):
    token = create_access_token({"sub": "nonexistent-id", "email": "no@one.com"})
    response = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


def test_get_me_unauthorized(client: TestClient):
    response = client.get("/api/v1/users/me")
    assert response.status_code == 403


@_SKIP_UNIMPLEMENTED
def test_list_users(client: TestClient):
    response = client.get("/api/v1/users")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@_SKIP_UNIMPLEMENTED
def test_update_user(client: TestClient):
    create_response = client.post(
        "/api/v1/users",
        json={"email": "update@example.com", "name": "Original Name", "password": "password123"},
    )
    user_id = create_response.json()["id"]

    response = client.put(f"/api/v1/users/{user_id}", json={"name": "Updated Name"})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Name"
    assert data["email"] == "update@example.com"


@_SKIP_UNIMPLEMENTED
def test_delete_user(client: TestClient):
    create_response = client.post(
        "/api/v1/users",
        json={"email": "delete@example.com", "name": "Delete Test", "password": "password123"},
    )
    user_id = create_response.json()["id"]

    response = client.delete(f"/api/v1/users/{user_id}")
    assert response.status_code == 204

    get_response = client.get(f"/api/v1/users/{user_id}")
    assert get_response.status_code == 404


@_SKIP_UNIMPLEMENTED
def test_verify_user_email(client: TestClient):
    create_response = client.post(
        "/api/v1/users",
        json={"email": "verify@example.com", "name": "Verify Test", "password": "password123"},
    )
    user_id = create_response.json()["id"]

    response = client.post(f"/api/v1/users/{user_id}/verify")
    assert response.status_code == 200
    data = response.json()
    assert data["is_verified"] is True


@_SKIP_UNIMPLEMENTED
def test_get_user_by_email(client: TestClient):
    client.post(
        "/api/v1/users",
        json={"email": "emailtest@example.com", "name": "Email Test", "password": "password123"},
    )

    response = client.get("/api/v1/users/email/emailtest@example.com")
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "emailtest@example.com"
