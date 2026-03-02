
import pytest
from fastapi.testclient import TestClient


def _create_llm(client: TestClient, headers: dict, name: str = "Test LLM") -> dict:
    resp = client.post(
        "/api/v1/llms",
        json={
            "name": name,
            "provider": "openai",
            "api_key": "sk-test",
            "model_name": "gpt-4o",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.json()
    return resp.json()


# ---------------------------------------------------------------------------
# set_active_llm
# ---------------------------------------------------------------------------

def test_set_active_llm_success(client: TestClient, auth: dict):
    llm = _create_llm(client, auth["headers"])

    response = client.put(
        f"/api/v1/organizations/{auth['org_id']}/active-llm",
        json={"llm_id": llm["id"]},
        headers=auth["headers"],
    )

    assert response.status_code == 200
    assert response.json()["active_llm_id"] == llm["id"]


def test_set_active_llm_switch(client: TestClient, auth: dict):
    """Switching from one LLM to another must reflect the new ID in the response."""
    llm1 = _create_llm(client, auth["headers"], name="LLM 1")
    llm2 = _create_llm(client, auth["headers"], name="LLM 2")

    r1 = client.put(
        f"/api/v1/organizations/{auth['org_id']}/active-llm",
        json={"llm_id": llm1["id"]},
        headers=auth["headers"],
    )
    assert r1.json()["active_llm_id"] == llm1["id"]

    r2 = client.put(
        f"/api/v1/organizations/{auth['org_id']}/active-llm",
        json={"llm_id": llm2["id"]},
        headers=auth["headers"],
    )
    assert r2.json()["active_llm_id"] == llm2["id"]


def test_set_active_llm_clear(client: TestClient, auth: dict):
    """Passing llm_id=None should clear the active LLM."""
    llm = _create_llm(client, auth["headers"])

    client.put(
        f"/api/v1/organizations/{auth['org_id']}/active-llm",
        json={"llm_id": llm["id"]},
        headers=auth["headers"],
    )

    response = client.put(
        f"/api/v1/organizations/{auth['org_id']}/active-llm",
        json={"llm_id": None},
        headers=auth["headers"],
    )

    assert response.status_code == 200
    assert response.json()["active_llm_id"] is None


def test_set_active_llm_llm_model_name_saved(client: TestClient, auth: dict):
    """LLM created via POST /llms must have model_name persisted."""
    llm = _create_llm(client, auth["headers"])
    assert llm["model_name"] == "gpt-4o"


def test_set_active_llm_non_member_forbidden(client: TestClient, auth: dict, auth2: dict):
    """A user who is not a member of the org cannot set the active LLM."""
    llm = _create_llm(client, auth["headers"])

    response = client.put(
        f"/api/v1/organizations/{auth['org_id']}/active-llm",
        json={"llm_id": llm["id"]},
        headers=auth2["headers"],
    )

    assert response.status_code == 400
    assert "not a member" in response.json()["detail"].lower()


def test_set_active_llm_non_owner_member_forbidden(client: TestClient, auth: dict, db_session):
    """A regular member (not owner/admin) cannot set the active LLM."""
    import asyncio
    from app.core.security import create_access_token
    from app.models.user import User
    from app.models.user_organization import OrgRole, UserOrganization

    # Sign up a second user
    client.post(
        "/api/v1/auth/signup",
        json={"email": "member@example.com", "name": "Member", "password": "password123"},
    )
    member_id = User.generate_id_from_email("member@example.com")
    member_token = create_access_token({"sub": member_id, "email": "member@example.com"})
    member_headers = {"Authorization": f"Bearer {member_token}"}

    # Insert a plain MEMBER row directly (no HTTP endpoint exists for this)
    membership = UserOrganization(
        user_id=member_id,
        organization_id=auth["org_id"],
        role=OrgRole.MEMBER,
    )
    asyncio.get_event_loop().run_until_complete(_add_membership(db_session, membership))

    llm = _create_llm(client, auth["headers"])

    response = client.put(
        f"/api/v1/organizations/{auth['org_id']}/active-llm",
        json={"llm_id": llm["id"]},
        headers=member_headers,
    )

    assert response.status_code == 403


async def _add_membership(db_session, membership):
    db_session.add(membership)
    await db_session.commit()


def test_set_active_llm_llm_from_wrong_org_rejected(client: TestClient, auth: dict, auth2: dict):
    """An LLM that belongs to a different org must be rejected."""
    llm_other_org = _create_llm(client, auth2["headers"])

    response = client.put(
        f"/api/v1/organizations/{auth['org_id']}/active-llm",
        json={"llm_id": llm_other_org["id"]},
        headers=auth["headers"],
    )

    assert response.status_code == 400
    assert "not found" in response.json()["detail"].lower()


def test_set_active_llm_nonexistent_llm_rejected(client: TestClient, auth: dict):
    response = client.put(
        f"/api/v1/organizations/{auth['org_id']}/active-llm",
        json={"llm_id": "nonexistent-llm-id"},
        headers=auth["headers"],
    )

    assert response.status_code == 400
    assert "not found" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# clear_active_llm  DELETE /organizations/{id}/active-llm
# ---------------------------------------------------------------------------

def test_clear_active_llm_success(client: TestClient, auth: dict):
    llm = _create_llm(client, auth["headers"])
    client.put(
        f"/api/v1/organizations/{auth['org_id']}/active-llm",
        json={"llm_id": llm["id"]},
        headers=auth["headers"],
    )

    response = client.delete(
        f"/api/v1/organizations/{auth['org_id']}/active-llm",
        headers=auth["headers"],
    )

    assert response.status_code == 200
    assert response.json()["active_llm_id"] is None


def test_clear_active_llm_when_already_none(client: TestClient, auth: dict):
    """Clearing when no LLM is set should succeed without error."""
    response = client.delete(
        f"/api/v1/organizations/{auth['org_id']}/active-llm",
        headers=auth["headers"],
    )

    assert response.status_code == 200
    assert response.json()["active_llm_id"] is None


def test_clear_active_llm_non_member_forbidden(client: TestClient, auth: dict, auth2: dict):
    response = client.delete(
        f"/api/v1/organizations/{auth['org_id']}/active-llm",
        headers=auth2["headers"],
    )

    assert response.status_code == 400


def test_clear_active_llm_unauthenticated(client: TestClient, auth: dict):
    response = client.delete(f"/api/v1/organizations/{auth['org_id']}/active-llm")

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# GET /llms  is_active flag
# ---------------------------------------------------------------------------

def test_list_llms_reflects_active(client: TestClient, auth: dict):
    llm1 = _create_llm(client, auth["headers"], name="LLM 1")
    llm2 = _create_llm(client, auth["headers"], name="LLM 2")

    client.put(
        f"/api/v1/organizations/{auth['org_id']}/active-llm",
        json={"llm_id": llm1["id"]},
        headers=auth["headers"],
    )

    resp = client.get("/api/v1/llms", headers=auth["headers"])
    assert resp.status_code == 200
    by_id = {llm["id"]: llm for llm in resp.json()}
    assert by_id[llm1["id"]]["is_active"] is True
    assert by_id[llm2["id"]]["is_active"] is False


def test_list_llms_no_active_all_false(client: TestClient, auth: dict):
    _create_llm(client, auth["headers"])

    resp = client.get("/api/v1/llms", headers=auth["headers"])
    assert all(llm["is_active"] is False for llm in resp.json())


def test_set_active_llm_unauthenticated(client: TestClient, auth: dict):
    llm = _create_llm(client, auth["headers"])

    response = client.put(
        f"/api/v1/organizations/{auth['org_id']}/active-llm",
        json={"llm_id": llm["id"]},
    )

    assert response.status_code == 403
