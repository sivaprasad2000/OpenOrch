from fastapi.testclient import TestClient

from app.core.security import create_access_token


def test_create_test_group_success(client: TestClient, auth: dict):
    response = client.post(
        "/api/v1/test-groups",
        json={"name": "Login Tests"},
        headers=auth["headers"],
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Login Tests"
    assert data["status"] == "active"
    assert data["organization_id"] == auth["org_id"]
    assert data["created_by"] == auth["user_id"]
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_create_test_group_with_all_fields(client: TestClient, auth: dict):
    response = client.post(
        "/api/v1/test-groups",
        json={
            "name": "Checkout Flow",
            "description": "Tests for the checkout process",
            "base_url": "https://example.com",
        },
        headers=auth["headers"],
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Checkout Flow"
    assert data["description"] == "Tests for the checkout process"
    assert data["base_url"] == "https://example.com"


def test_create_test_group_missing_name(client: TestClient, auth: dict):
    response = client.post(
        "/api/v1/test-groups",
        json={"description": "No name provided"},
        headers=auth["headers"],
    )

    assert response.status_code == 422


def test_create_test_group_empty_name(client: TestClient, auth: dict):
    response = client.post(
        "/api/v1/test-groups",
        json={"name": ""},
        headers=auth["headers"],
    )

    assert response.status_code == 422


def test_create_test_group_unauthenticated(client: TestClient):
    response = client.post(
        "/api/v1/test-groups",
        json={"name": "Should Fail"},
    )

    assert response.status_code == 403


def test_create_test_group_no_active_org(client: TestClient):
    client.post(
        "/api/v1/auth/signup",
        json={"email": "noorg@example.com", "name": "No Org", "password": "password123"},
    )
    from app.models.user import User

    user_id = User.generate_id_from_email("noorg@example.com")
    token = create_access_token({"sub": user_id, "email": "noorg@example.com"})

    response = client.post(
        "/api/v1/test-groups",
        json={"name": "Should Fail"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    assert "active organization" in response.json()["detail"].lower()


def test_list_test_groups_empty(client: TestClient, auth: dict):
    response = client.get("/api/v1/test-groups", headers=auth["headers"])

    assert response.status_code == 200
    assert response.json() == []


def test_list_test_groups_returns_own_org_only(client: TestClient, auth: dict, auth2: dict):
    client.post(
        "/api/v1/test-groups",
        json={"name": "User 1 Group"},
        headers=auth["headers"],
    )
    client.post(
        "/api/v1/test-groups",
        json={"name": "User 2 Group"},
        headers=auth2["headers"],
    )

    response = client.get("/api/v1/test-groups", headers=auth["headers"])
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "User 1 Group"


def test_list_test_groups_multiple(client: TestClient, auth: dict):
    client.post("/api/v1/test-groups", json={"name": "Group A"}, headers=auth["headers"])
    client.post("/api/v1/test-groups", json={"name": "Group B"}, headers=auth["headers"])
    client.post("/api/v1/test-groups", json={"name": "Group C"}, headers=auth["headers"])

    response = client.get("/api/v1/test-groups", headers=auth["headers"])

    assert response.status_code == 200
    assert len(response.json()) == 3


def test_list_test_groups_unauthenticated(client: TestClient):
    response = client.get("/api/v1/test-groups")
    assert response.status_code == 403


def test_get_test_group_success(client: TestClient, auth: dict):
    create_resp = client.post(
        "/api/v1/test-groups",
        json={"name": "My Group"},
        headers=auth["headers"],
    )
    group_id = create_resp.json()["id"]

    response = client.get(f"/api/v1/test-groups/{group_id}", headers=auth["headers"])

    assert response.status_code == 200
    assert response.json()["id"] == group_id
    assert response.json()["name"] == "My Group"


def test_get_test_group_not_found(client: TestClient, auth: dict):
    response = client.get("/api/v1/test-groups/nonexistent-id", headers=auth["headers"])

    assert response.status_code == 404


def test_get_test_group_wrong_org(client: TestClient, auth: dict, auth2: dict):
    create_resp = client.post(
        "/api/v1/test-groups",
        json={"name": "Org 1 Group"},
        headers=auth["headers"],
    )
    group_id = create_resp.json()["id"]

    response = client.get(f"/api/v1/test-groups/{group_id}", headers=auth2["headers"])

    assert response.status_code == 404


def test_update_test_group_name(client: TestClient, auth: dict):
    create_resp = client.post(
        "/api/v1/test-groups",
        json={"name": "Old Name"},
        headers=auth["headers"],
    )
    group_id = create_resp.json()["id"]

    response = client.put(
        f"/api/v1/test-groups/{group_id}",
        json={"name": "New Name"},
        headers=auth["headers"],
    )

    assert response.status_code == 200
    assert response.json()["name"] == "New Name"


def test_update_test_group_status(client: TestClient, auth: dict):
    create_resp = client.post(
        "/api/v1/test-groups",
        json={"name": "Active Group"},
        headers=auth["headers"],
    )
    group_id = create_resp.json()["id"]

    response = client.put(
        f"/api/v1/test-groups/{group_id}",
        json={"status": "archived"},
        headers=auth["headers"],
    )

    assert response.status_code == 200
    assert response.json()["status"] == "archived"


def test_update_test_group_not_found(client: TestClient, auth: dict):
    response = client.put(
        "/api/v1/test-groups/nonexistent-id",
        json={"name": "New Name"},
        headers=auth["headers"],
    )

    assert response.status_code == 404


def test_update_test_group_wrong_org(client: TestClient, auth: dict, auth2: dict):
    create_resp = client.post(
        "/api/v1/test-groups",
        json={"name": "Org 1 Group"},
        headers=auth["headers"],
    )
    group_id = create_resp.json()["id"]

    response = client.put(
        f"/api/v1/test-groups/{group_id}",
        json={"name": "Hacked"},
        headers=auth2["headers"],
    )

    assert response.status_code == 404


def test_delete_test_group_success(client: TestClient, auth: dict):
    create_resp = client.post(
        "/api/v1/test-groups",
        json={"name": "To Delete"},
        headers=auth["headers"],
    )
    group_id = create_resp.json()["id"]

    response = client.delete(f"/api/v1/test-groups/{group_id}", headers=auth["headers"])
    assert response.status_code == 204

    get_response = client.get(f"/api/v1/test-groups/{group_id}", headers=auth["headers"])
    assert get_response.status_code == 404


def test_delete_test_group_not_found(client: TestClient, auth: dict):
    response = client.delete("/api/v1/test-groups/nonexistent-id", headers=auth["headers"])
    assert response.status_code == 404


def test_delete_test_group_wrong_org(client: TestClient, auth: dict, auth2: dict):
    create_resp = client.post(
        "/api/v1/test-groups",
        json={"name": "Org 1 Group"},
        headers=auth["headers"],
    )
    group_id = create_resp.json()["id"]

    response = client.delete(f"/api/v1/test-groups/{group_id}", headers=auth2["headers"])
    assert response.status_code == 404

    get_response = client.get(f"/api/v1/test-groups/{group_id}", headers=auth["headers"])
    assert get_response.status_code == 200
