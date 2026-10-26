import json
import logging

from app.logging import JsonFormatter, request_id_var


def _record(**attrs: object) -> logging.LogRecord:
    return logging.makeLogRecord(
        {"name": "test", "levelno": logging.INFO, "levelname": "INFO", "msg": "hello", **attrs}
    )


def test_formatter_emits_one_json_object_with_the_request_id() -> None:
    token = request_id_var.set("req-1")
    try:
        event = json.loads(JsonFormatter().format(_record()))
    finally:
        request_id_var.reset(token)

    assert event["message"] == "hello"
    assert event["level"] == "info"
    assert event["logger"] == "test"
    assert event["request_id"] == "req-1"
    assert event["timestamp"].endswith("+00:00")


def test_formatter_merges_extra_fields() -> None:
    event = json.loads(JsonFormatter().format(_record(fields={"status": 200, "path": "/x"})))

    assert event["status"] == 200
    assert event["path"] == "/x"


def test_formatter_has_null_request_id_outside_a_request() -> None:
    event = json.loads(JsonFormatter().format(_record()))

    assert event["request_id"] is None
