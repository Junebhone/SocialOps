"""Step 0 acceptance: the app boots, /health answers 200, and every request is logged."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_every_response_carries_a_request_id() -> None:
    """Hard rule #8: one log line per request, correlated by request_id."""
    response = client.get("/health")

    assert response.headers["X-Request-ID"]


def test_inbound_request_id_is_preserved() -> None:
    """A caller-supplied id is honoured so a trace spans web → api → job."""
    response = client.get("/health", headers={"X-Request-ID": "trace-me"})

    assert response.headers["X-Request-ID"] == "trace-me"
