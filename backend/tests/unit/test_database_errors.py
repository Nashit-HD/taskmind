import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.logging import REQUEST_ID_HEADER
from app.main import create_app


def _app_whose_route_loses_the_database() -> FastAPI:
    failing = create_app()

    @failing.get("/needs-db")
    def needs_db() -> None:
        raise OperationalError("SELECT 1", {}, ConnectionRefusedError("connection refused"))

    return failing


def test_a_database_connection_failure_returns_503_with_a_generic_body(
    caplog: pytest.LogCaptureFixture,
) -> None:
    failing = _app_whose_route_loses_the_database()
    with (
        caplog.at_level(logging.ERROR, logger="taskmind.database"),
        TestClient(failing, raise_server_exceptions=False) as client,
    ):
        response = client.get("/needs-db", headers={REQUEST_ID_HEADER: "db-down"})

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
    assert "refused" not in response.text
    assert response.headers[REQUEST_ID_HEADER] == "db-down"


def test_a_database_connection_failure_is_logged_with_its_trace(
    caplog: pytest.LogCaptureFixture,
) -> None:
    failing = _app_whose_route_loses_the_database()
    with (
        caplog.at_level(logging.ERROR, logger="taskmind.database"),
        TestClient(failing, raise_server_exceptions=False) as client,
    ):
        client.get("/needs-db")

    errors = [r for r in caplog.records if r.name == "taskmind.database"]
    assert len(errors) == 1
    assert errors[0].levelno == logging.ERROR
    assert errors[0].exc_info is not None
    assert errors[0].__dict__["fields"]["path"] == "/needs-db"
