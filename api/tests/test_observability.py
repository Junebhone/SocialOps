"""The 5xx metric's inputs (Milestone 6).

CloudWatch counts log lines whose status_code is >= 500. These tests pin the two
things that count depends on: every failed request logs a status_code, and the
controlled error route produces exactly one such line per call, on both the
returned-500 path and the unhandled-exception path.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import logging as app_logging
from app.config import get_settings
from app.main import app

# raise_server_exceptions=False: the client sees the 500 a real caller would get,
# instead of the test re-raising the exception.
client = TestClient(app, raise_server_exceptions=False)


class RecordingLog:
    """Stands in for the module logger so the test reads the exact fields logged."""

    def __init__(self) -> None:
        self.lines: list[tuple[str, dict[str, Any]]] = []

    def info(self, event: str, **fields: Any) -> None:
        self.lines.append((event, fields))

    def exception(self, event: str, **fields: Any) -> None:
        self.lines.append((event, fields))

    def five_xx(self) -> list[tuple[str, dict[str, Any]]]:
        return [line for line in self.lines if line[1].get("status_code", 0) >= 500]


@pytest.fixture
def log(monkeypatch: pytest.MonkeyPatch) -> RecordingLog:
    recording = RecordingLog()
    monkeypatch.setattr(app_logging, "log", recording)
    return recording


@pytest.fixture
def error_route_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "enable_error_route", True)


def test_error_route_is_off_by_default(log: RecordingLog) -> None:
    """Without the opt-in the route is indistinguishable from a missing one, so
    nobody outside the team can trip the alarm."""
    assert get_settings().enable_error_route is False

    response = client.get("/debug/error")

    assert response.status_code == 404
    assert log.five_xx() == []


@pytest.mark.usefixtures("error_route_on")
def test_returned_500_is_counted_once(log: RecordingLog) -> None:
    response = client.get("/debug/error")

    assert response.status_code == 500
    assert len(log.five_xx()) == 1
    event, fields = log.five_xx()[0]
    assert event == "request"
    assert fields["status_code"] == 500
    assert fields["path"] == "/debug/error"


@pytest.mark.usefixtures("error_route_on")
def test_unhandled_exception_is_counted_once(log: RecordingLog) -> None:
    """The gap this milestone closed: request.failed used to carry no
    status_code, so a metric on status_code missed every crash."""
    response = client.get("/debug/error", params={"kind": "raise"})

    assert response.status_code == 500
    assert len(log.five_xx()) == 1
    event, fields = log.five_xx()[0]
    assert event == "request.failed"
    assert fields["status_code"] == 500


def test_a_normal_request_is_not_counted(log: RecordingLog) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert log.five_xx() == []
    assert log.lines[0][1]["status_code"] == 200


def test_ssm_flag_turns_route_on_without_redeploy(
    monkeypatch: pytest.MonkeyPatch, log: RecordingLog
) -> None:
    from app.routers import debug

    monkeypatch.setattr(get_settings(), "error_route_ssm_parameter", "/x/flag")
    monkeypatch.setattr(debug, "_read_ssm_flag", lambda name, region: True)

    assert client.get("/debug/error").status_code == 500


def test_ssm_flag_false_keeps_route_off(
    monkeypatch: pytest.MonkeyPatch, log: RecordingLog
) -> None:
    from app.routers import debug

    monkeypatch.setattr(get_settings(), "error_route_ssm_parameter", "/x/flag")
    monkeypatch.setattr(debug, "_read_ssm_flag", lambda name, region: False)

    assert client.get("/debug/error").status_code == 404
    assert log.five_xx() == []


def test_unreadable_ssm_parameter_counts_as_off(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.routers import debug

    class Denied:
        def get_parameter(self, **_: object) -> None:
            raise RuntimeError("AccessDenied")

    monkeypatch.setattr(debug.boto3, "client", lambda *a, **k: Denied())

    assert debug._read_ssm_flag("/x/flag", "us-east-1") is False
