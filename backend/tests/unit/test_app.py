import json
import logging
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.logging import REQUEST_ID_HEADER, JsonFormatter
from app.main import app, create_app


def test_openapi_docs_are_served() -> None:
    with TestClient(app) as client:
        response = client.get("/docs")

    assert response.status_code == 200


def test_response_carries_a_generated_request_id() -> None:
    with TestClient(app) as client:
        response = client.get("/openapi.json")

    assert uuid.UUID(response.headers[REQUEST_ID_HEADER])


def test_response_echoes_a_supplied_request_id() -> None:
    with TestClient(app) as client:
        response = client.get("/openapi.json", headers={REQUEST_ID_HEADER: "client-abc"})

    assert response.headers[REQUEST_ID_HEADER] == "client-abc"


def test_an_oversized_request_id_is_replaced() -> None:
    with TestClient(app) as client:
        response = client.get("/openapi.json", headers={REQUEST_ID_HEADER: "x" * 129})

    assert uuid.UUID(response.headers[REQUEST_ID_HEADER])


def test_cors_allows_the_frontend_origin() -> None:
    with TestClient(app) as client:
        response = client.options(
            "/openapi.json",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_rejects_an_unknown_origin() -> None:
    with TestClient(app) as client:
        response = client.options(
            "/openapi.json",
            headers={
                "Origin": "http://evil.example",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert "access-control-allow-origin" not in response.headers


def test_each_request_logs_one_line_with_the_request_id(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="taskmind.request"), TestClient(app) as client:
        client.get("/openapi.json", headers={REQUEST_ID_HEADER: "log-me"})

    records = [r for r in caplog.records if r.name == "taskmind.request"]
    assert len(records) == 1
    fields = records[0].__dict__["fields"]
    assert fields["method"] == "GET"
    assert fields["path"] == "/openapi.json"
    assert fields["status"] == 200
    assert fields["duration_ms"] >= 0


def _app_with_a_failing_route() -> FastAPI:
    failing = create_app()

    @failing.get("/boom")
    def boom() -> None:
        raise RuntimeError("boom")

    return failing


def test_an_unhandled_error_is_logged_and_returns_500(caplog: pytest.LogCaptureFixture) -> None:
    failing = _app_with_a_failing_route()
    with (
        caplog.at_level(logging.ERROR, logger="taskmind.request"),
        TestClient(failing, raise_server_exceptions=False) as client,
    ):
        response = client.get("/boom")

    assert response.status_code == 500
    assert response.text == "Internal Server Error"
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1
    assert errors[0].__dict__["fields"]["path"] == "/boom"
    assert errors[0].exc_info is not None


def test_exactly_one_json_handler_is_on_the_root_logger_after_repeated_setup() -> None:
    create_app()
    create_app()
    json_handlers = [
        h for h in logging.getLogger().handlers if isinstance(h.formatter, JsonFormatter)
    ]

    assert len(json_handlers) == 1
    event = json.loads(json_handlers[0].format(logging.makeLogRecord({"msg": "x"})))
    assert event["message"] == "x"
