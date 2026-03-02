
import pytest
from fastapi.testclient import TestClient


SAMPLE_PAYLOAD = {
    "title": "Login with valid credentials",
    "description": "Navigate to login page and sign in",
    "steps": [
        {"action": "goto", "description": "Navigate to the login page"},
        {"action": "fill", "description": "Enter email address in the email field"},
        {"action": "fill", "description": "Enter password in the password field"},
        {"action": "click", "description": "Click the submit button to sign in"},
    ],
}


def _create_group(client: TestClient, headers: dict, name: str = "My Group") -> str:
    resp = client.post(
        "/api/v1/test-groups",
        json={"name": name},
        headers=headers,
    )
    return resp.json()["id"]


def test_create_test_case_success(client: TestClient, auth: dict):
    group_id = _create_group(client, auth["headers"])

    response = client.post(
        f"/api/v1/test-groups/{group_id}/test-cases",
        json={"payload": SAMPLE_PAYLOAD},
        headers=auth["headers"],
    )

    assert response.status_code == 201
    data = response.json()
    assert data["test_group_id"] == group_id
    assert data["payload"]["title"] == "Login with valid credentials"
    assert "id" in data
    assert "created_at" in data


def test_create_test_case_minimal_payload(client: TestClient, auth: dict):
    group_id = _create_group(client, auth["headers"])

    response = client.post(
        f"/api/v1/test-groups/{group_id}/test-cases",
        json={"payload": {"note": "placeholder"}},
        headers=auth["headers"],
    )

    assert response.status_code == 201
    assert response.json()["payload"] == {"note": "placeholder"}


def test_create_test_case_group_not_found(client: TestClient, auth: dict):
    response = client.post(
        "/api/v1/test-groups/nonexistent-group/test-cases",
        json={"payload": SAMPLE_PAYLOAD},
        headers=auth["headers"],
    )

    assert response.status_code == 404


def test_create_test_case_group_wrong_org(client: TestClient, auth: dict, auth2: dict):
    group_id = _create_group(client, auth["headers"])

    response = client.post(
        f"/api/v1/test-groups/{group_id}/test-cases",
        json={"payload": SAMPLE_PAYLOAD},
        headers=auth2["headers"],
    )

    assert response.status_code == 404


def test_create_test_case_missing_payload(client: TestClient, auth: dict):
    group_id = _create_group(client, auth["headers"])

    response = client.post(
        f"/api/v1/test-groups/{group_id}/test-cases",
        json={},
        headers=auth["headers"],
    )

    assert response.status_code == 422


def test_create_test_case_unauthenticated(client: TestClient, auth: dict):
    group_id = _create_group(client, auth["headers"])

    response = client.post(
        f"/api/v1/test-groups/{group_id}/test-cases",
        json={"payload": SAMPLE_PAYLOAD},
    )

    assert response.status_code == 403


def test_list_test_cases_empty(client: TestClient, auth: dict):
    group_id = _create_group(client, auth["headers"])

    response = client.get(
        f"/api/v1/test-groups/{group_id}/test-cases",
        headers=auth["headers"],
    )

    assert response.status_code == 200
    assert response.json() == []


def test_list_test_cases_multiple(client: TestClient, auth: dict):
    group_id = _create_group(client, auth["headers"])

    for i in range(3):
        client.post(
            f"/api/v1/test-groups/{group_id}/test-cases",
            json={"payload": {"index": i}},
            headers=auth["headers"],
        )

    response = client.get(
        f"/api/v1/test-groups/{group_id}/test-cases",
        headers=auth["headers"],
    )

    assert response.status_code == 200
    assert len(response.json()) == 3


def test_list_test_cases_isolated_by_group(client: TestClient, auth: dict):
    group_a = _create_group(client, auth["headers"], name="Group A")
    group_b = _create_group(client, auth["headers"], name="Group B")

    client.post(
        f"/api/v1/test-groups/{group_a}/test-cases",
        json={"payload": {"group": "A"}},
        headers=auth["headers"],
    )
    client.post(
        f"/api/v1/test-groups/{group_b}/test-cases",
        json={"payload": {"group": "B"}},
        headers=auth["headers"],
    )

    response = client.get(
        f"/api/v1/test-groups/{group_a}/test-cases",
        headers=auth["headers"],
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["payload"]["group"] == "A"


def test_list_test_cases_group_not_found(client: TestClient, auth: dict):
    response = client.get(
        "/api/v1/test-groups/nonexistent/test-cases",
        headers=auth["headers"],
    )

    assert response.status_code == 404


def test_get_test_case_success(client: TestClient, auth: dict):
    group_id = _create_group(client, auth["headers"])
    create_resp = client.post(
        f"/api/v1/test-groups/{group_id}/test-cases",
        json={"payload": SAMPLE_PAYLOAD},
        headers=auth["headers"],
    )
    case_id = create_resp.json()["id"]

    response = client.get(
        f"/api/v1/test-groups/{group_id}/test-cases/{case_id}",
        headers=auth["headers"],
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == case_id
    assert data["test_group_id"] == group_id


def test_get_test_case_not_found(client: TestClient, auth: dict):
    group_id = _create_group(client, auth["headers"])

    response = client.get(
        f"/api/v1/test-groups/{group_id}/test-cases/nonexistent-id",
        headers=auth["headers"],
    )

    assert response.status_code == 404


def test_get_test_case_wrong_group(client: TestClient, auth: dict):
    group_a = _create_group(client, auth["headers"], name="Group A")
    group_b = _create_group(client, auth["headers"], name="Group B")

    create_resp = client.post(
        f"/api/v1/test-groups/{group_a}/test-cases",
        json={"payload": {"data": "test"}},
        headers=auth["headers"],
    )
    case_id = create_resp.json()["id"]

    response = client.get(
        f"/api/v1/test-groups/{group_b}/test-cases/{case_id}",
        headers=auth["headers"],
    )

    assert response.status_code == 404


def test_update_test_case_success(client: TestClient, auth: dict):
    group_id = _create_group(client, auth["headers"])
    create_resp = client.post(
        f"/api/v1/test-groups/{group_id}/test-cases",
        json={"payload": {"version": 1}},
        headers=auth["headers"],
    )
    case_id = create_resp.json()["id"]

    response = client.put(
        f"/api/v1/test-groups/{group_id}/test-cases/{case_id}",
        json={"payload": {"version": 2, "updated": True}},
        headers=auth["headers"],
    )

    assert response.status_code == 200
    data = response.json()
    assert data["payload"]["version"] == 2
    assert data["payload"]["updated"] is True


def test_update_test_case_not_found(client: TestClient, auth: dict):
    group_id = _create_group(client, auth["headers"])

    response = client.put(
        f"/api/v1/test-groups/{group_id}/test-cases/nonexistent-id",
        json={"payload": {"data": "x"}},
        headers=auth["headers"],
    )

    assert response.status_code == 404


def test_delete_test_case_success(client: TestClient, auth: dict):
    group_id = _create_group(client, auth["headers"])
    create_resp = client.post(
        f"/api/v1/test-groups/{group_id}/test-cases",
        json={"payload": SAMPLE_PAYLOAD},
        headers=auth["headers"],
    )
    case_id = create_resp.json()["id"]

    response = client.delete(
        f"/api/v1/test-groups/{group_id}/test-cases/{case_id}",
        headers=auth["headers"],
    )
    assert response.status_code == 204

    get_response = client.get(
        f"/api/v1/test-groups/{group_id}/test-cases/{case_id}",
        headers=auth["headers"],
    )
    assert get_response.status_code == 404


def test_delete_test_case_not_found(client: TestClient, auth: dict):
    group_id = _create_group(client, auth["headers"])

    response = client.delete(
        f"/api/v1/test-groups/{group_id}/test-cases/nonexistent-id",
        headers=auth["headers"],
    )

    assert response.status_code == 404


def test_delete_cascades_when_group_deleted(client: TestClient, auth: dict):
    group_id = _create_group(client, auth["headers"])
    create_resp = client.post(
        f"/api/v1/test-groups/{group_id}/test-cases",
        json={"payload": SAMPLE_PAYLOAD},
        headers=auth["headers"],
    )
    case_id = create_resp.json()["id"]

    client.delete(f"/api/v1/test-groups/{group_id}", headers=auth["headers"])

    response = client.get(
        f"/api/v1/test-groups/{group_id}/test-cases/{case_id}",
        headers=auth["headers"],
    )
    assert response.status_code == 404
