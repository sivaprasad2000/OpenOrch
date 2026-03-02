"""Tests for test run endpoints, focused on the player endpoint."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from tests.routes.authenticated.conftest import setup_user_with_org


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_INTERNAL_HEADERS = {"x-internal-secret": settings.INTERNAL_SERVICE_SECRET}

_STEP_RESULTS = [
    {
        "index": 0,
        "action": "navigate",
        "group": None,
        "description": "Go to the homepage",
        "status": "passed",
        "duration_ms": 1200,
        "started_at_seconds": 0.0,
        "logs": ["browser_navigate({'url': 'https://example.com'}) → ok"],
        "screenshot_path": None,
        "error": None,
    },
    {
        "index": 1,
        "action": "click",
        "group": "Login flow",
        "description": "Click the login button",
        "status": "passed",
        "duration_ms": 800,
        "started_at_seconds": 3.412,
        "logs": ["browser_click({'selector': \"role=button[name='Login']\"}) → ok"],
        "screenshot_path": None,
        "error": None,
    },
    {
        "index": 2,
        "action": "type",
        "group": "Login flow",
        "description": "Type email address",
        "status": "failed",
        "duration_ms": 5000,
        "started_at_seconds": 7.891,
        "logs": [],
        "screenshot_path": None,
        "error": "Element not found after 3 attempts",
    },
]


def _create_run_with_steps(client: TestClient, headers: dict) -> str:
    """Create a test case, queue a run, populate it with step results, return run_id."""
    # Create group + test case
    group_resp = client.post("/api/v1/test-groups", json={"name": "My Group"}, headers=headers)
    group_id = group_resp.json()["id"]

    case_resp = client.post(
        f"/api/v1/test-groups/{group_id}/test-cases",
        json={"payload": {"steps": []}},
        headers=headers,
    )
    case_id = case_resp.json()["id"]

    # Trigger a run (mock RabbitMQ so nothing is actually published)
    with patch("app.services.test_run_service.publish_test_run"):
        run_resp = client.post(f"/api/v1/test-cases/{case_id}/run", headers=headers)

    assert run_resp.status_code == 202, run_resp.text
    run_id = run_resp.json()["id"]

    # Populate step results via the internal endpoint
    client.patch(
        f"/api/v1/internal/test-runs/{run_id}/result",
        json={
            "status": "failed",
            "step_results": _STEP_RESULTS,
            "recording_url": f"http://localhost:8000/recordings/{run_id}-video.webm",
            "trace_url": None,
            "error": None,
        },
        headers=_INTERNAL_HEADERS,
    )

    return run_id


# ---------------------------------------------------------------------------
# Player endpoint — happy path
# ---------------------------------------------------------------------------


def test_player_returns_200(client: TestClient, auth: dict) -> None:
    run_id = _create_run_with_steps(client, auth["headers"])
    resp = client.get(f"/api/v1/test-runs/{run_id}/player", headers=auth["headers"])
    assert resp.status_code == 200


def test_player_returns_recording_url(client: TestClient, auth: dict) -> None:
    run_id = _create_run_with_steps(client, auth["headers"])
    data = client.get(f"/api/v1/test-runs/{run_id}/player", headers=auth["headers"]).json()
    assert data["recording_url"] == f"http://localhost:8000/recordings/{run_id}-video.webm"


def test_player_returns_one_marker_per_step(client: TestClient, auth: dict) -> None:
    run_id = _create_run_with_steps(client, auth["headers"])
    data = client.get(f"/api/v1/test-runs/{run_id}/player", headers=auth["headers"]).json()
    assert len(data["markers"]) == len(_STEP_RESULTS)


def test_player_marker_fields_match_step_results(client: TestClient, auth: dict) -> None:
    run_id = _create_run_with_steps(client, auth["headers"])
    data = client.get(f"/api/v1/test-runs/{run_id}/player", headers=auth["headers"]).json()

    first = data["markers"][0]
    assert first["index"] == 0
    assert first["action"] == "navigate"
    assert first["description"] == "Go to the homepage"
    assert first["status"] == "passed"
    assert first["started_at_seconds"] == 0.0
    assert first["duration_ms"] == 1200
    assert first["group"] is None
    assert first["error"] is None


def test_player_marker_preserves_group_name(client: TestClient, auth: dict) -> None:
    run_id = _create_run_with_steps(client, auth["headers"])
    data = client.get(f"/api/v1/test-runs/{run_id}/player", headers=auth["headers"]).json()

    second = data["markers"][1]
    assert second["group"] == "Login flow"


def test_player_failed_marker_includes_error(client: TestClient, auth: dict) -> None:
    run_id = _create_run_with_steps(client, auth["headers"])
    data = client.get(f"/api/v1/test-runs/{run_id}/player", headers=auth["headers"]).json()

    failed = data["markers"][2]
    assert failed["status"] == "failed"
    assert "Element not found" in failed["error"]


def test_player_markers_have_correct_started_at_seconds(client: TestClient, auth: dict) -> None:
    run_id = _create_run_with_steps(client, auth["headers"])
    data = client.get(f"/api/v1/test-runs/{run_id}/player", headers=auth["headers"]).json()

    offsets = [m["started_at_seconds"] for m in data["markers"]]
    assert offsets == [0.0, 3.412, 7.891]


def test_player_does_not_expose_logs(client: TestClient, auth: dict) -> None:
    """Logs must be stripped — they belong to the full test run detail, not the player."""
    run_id = _create_run_with_steps(client, auth["headers"])
    data = client.get(f"/api/v1/test-runs/{run_id}/player", headers=auth["headers"]).json()

    for marker in data["markers"]:
        assert "logs" not in marker


# ---------------------------------------------------------------------------
# Player endpoint — no steps yet
# ---------------------------------------------------------------------------


def test_player_returns_empty_markers_when_no_steps(client: TestClient, auth: dict) -> None:
    """A freshly queued run has no step_results yet — markers should be empty."""
    group_resp = client.post(
        "/api/v1/test-groups", json={"name": "My Group"}, headers=auth["headers"]
    )
    group_id = group_resp.json()["id"]

    case_resp = client.post(
        f"/api/v1/test-groups/{group_id}/test-cases",
        json={"payload": {}},
        headers=auth["headers"],
    )
    case_id = case_resp.json()["id"]

    with patch("app.services.test_run_service.publish_test_run"):
        run_resp = client.post(f"/api/v1/test-cases/{case_id}/run", headers=auth["headers"])

    run_id = run_resp.json()["id"]
    data = client.get(f"/api/v1/test-runs/{run_id}/player", headers=auth["headers"]).json()

    assert data["markers"] == []
    assert data["recording_url"] is None


def test_player_defaults_started_at_seconds_for_legacy_steps(
    client: TestClient, auth: dict
) -> None:
    """Steps stored before started_at_seconds was added must default to 0.0."""
    group_id = client.post(
        "/api/v1/test-groups", json={"name": "G"}, headers=auth["headers"]
    ).json()["id"]
    case_id = client.post(
        f"/api/v1/test-groups/{group_id}/test-cases",
        json={"payload": {}},
        headers=auth["headers"],
    ).json()["id"]

    with patch("app.services.test_run_service.publish_test_run"):
        run_id = client.post(
            f"/api/v1/test-cases/{case_id}/run", headers=auth["headers"]
        ).json()["id"]

    # Patch with a step that has no started_at_seconds (simulates old data)
    legacy_step = {
        "index": 0,
        "action": "navigate",
        "description": "Go somewhere",
        "status": "passed",
        "duration_ms": 500,
        "logs": [],
        "screenshot_path": None,
        "error": None,
        # started_at_seconds intentionally absent
    }
    client.patch(
        f"/api/v1/internal/test-runs/{run_id}/result",
        json={"status": "passed", "step_results": [legacy_step]},
        headers=_INTERNAL_HEADERS,
    )

    data = client.get(f"/api/v1/test-runs/{run_id}/player", headers=auth["headers"]).json()
    assert data["markers"][0]["started_at_seconds"] == 0.0


# ---------------------------------------------------------------------------
# Player endpoint — auth / access control
# ---------------------------------------------------------------------------


def test_player_requires_authentication(client: TestClient, auth: dict) -> None:
    run_id = _create_run_with_steps(client, auth["headers"])
    resp = client.get(f"/api/v1/test-runs/{run_id}/player")
    assert resp.status_code == 403


def test_player_returns_404_for_unknown_run(client: TestClient, auth: dict) -> None:
    resp = client.get("/api/v1/test-runs/nonexistent-run-id/player", headers=auth["headers"])
    assert resp.status_code == 404


def test_player_returns_404_for_run_owned_by_other_user(
    client: TestClient, auth: dict
) -> None:
    run_id = _create_run_with_steps(client, auth["headers"])

    other = setup_user_with_org(client, email="other@example.com", org_name="Other Org")
    resp = client.get(f"/api/v1/test-runs/{run_id}/player", headers=other["headers"])
    assert resp.status_code == 404
