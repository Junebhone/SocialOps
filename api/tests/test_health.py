"""Liveness, readiness, and request correlation.

The split between the two probes is not ceremony. It is what step 10 added
after Docker's disk filled, Postgres refused to restart, and `docker compose ps`
went on reporting the API as healthy because the healthcheck asked a question
that stayed true (D19).
"""

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app import main
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



async def test_readiness_reports_both_dependencies(client: AsyncClient) -> None:
    """The healthcheck Compose actually uses. It touches Postgres and Redis, so
    it cannot go green in front of a database that is down."""
    response = await client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": True, "redis": True}


async def test_readiness_is_a_503_when_the_database_is_unreachable(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The incident, as a test. A green API in front of a dead Postgres is worse
    than a red one, because it sends you looking in the wrong place."""

    async def boom(session: object) -> None:
        raise OSError("connection refused")

    monkeypatch.setattr(main, "_ping_database", boom)

    response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "database": False, "redis": True}


async def test_readiness_names_which_dependency_failed(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """503 with a body, not a bare failure. "Redis is unreachable" and "the API
    is broken" have to look different at 2am."""

    async def boom() -> None:
        raise OSError("connection refused")

    monkeypatch.setattr(main, "_ping_redis", boom)

    body = (await client.get("/health/ready")).json()

    assert body["database"] is True
    assert body["redis"] is False


async def test_liveness_stays_up_when_a_dependency_is_down(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deliberately. A liveness probe that fails on someone else's outage asks
    to be restarted for it, which turns a database blip into a restart loop."""

    async def boom(session: object) -> None:
        raise OSError("connection refused")

    monkeypatch.setattr(main, "_ping_database", boom)

    assert (await client.get("/health")).status_code == 200
