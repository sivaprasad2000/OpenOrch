from fastapi.testclient import TestClient


def test_health_check(client: TestClient):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "app_name" in data
    assert "version" in data


def test_readiness_check(client: TestClient):
    response = client.get("/api/v1/readiness")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_liveness_check(client: TestClient):
    response = client.get("/api/v1/liveness")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"


def test_root_endpoint(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "version" in data
