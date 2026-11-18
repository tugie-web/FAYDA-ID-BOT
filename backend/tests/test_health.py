from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_status_is_safe() -> None:
    response = client.get("/api/v1/status")
    assert response.status_code == 200
    assert response.json()["identity_integration"] == "disabled_until_authorized"
