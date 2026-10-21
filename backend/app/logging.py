"""Structured logging and the request id.

Every log event is one JSON object with ``timestamp``, ``level``, ``logger``, ``message`` and
``request_id``. Call sites pass extra fields as ``extra={"fields": {...}}`` and never interpolate
them into the message.

The request id is taken from the ``X-Request-Id`` header when the caller sends one, or generated,
and is returned on the response so a client can quote it.
"""

import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from datetime import UTC, datetime

from fastapi import Request, Response

REQUEST_ID_HEADER = "X-Request-Id"
_MAX_REQUEST_ID_LENGTH = 128

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

logger = logging.getLogger("taskmind.request")


class JsonFormatter(logging.Formatter):
    """Formats a record as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        event: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        fields = record.__dict__.get("fields")
        if isinstance(fields, dict):
            event.update(fields)
        if record.exc_info:
            event["exception"] = self.formatException(record.exc_info)
        return json.dumps(event, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    """Route every logger, uvicorn's included, through the JSON formatter.

    Uvicorn's access log is switched off because ``request_logging_middleware`` emits the request
    line with the request id, which uvicorn's line cannot carry.

    Only a previous JSON handler is replaced, so calling this twice (every ``create_app()`` does)
    never stacks handlers, and handlers other tools add, such as pytest's capture, are kept.
    """
    root = logging.getLogger()
    for existing in list(root.handlers):
        if isinstance(existing.formatter, JsonFormatter):
            root.removeHandler(existing)
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level)
    for name in ("uvicorn", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True
    logging.getLogger("uvicorn.access").disabled = True


def _incoming_request_id(request: Request) -> str:
    supplied = request.headers.get(REQUEST_ID_HEADER, "").strip()
    if supplied and len(supplied) <= _MAX_REQUEST_ID_LENGTH:
        return supplied
    return str(uuid.uuid4())


async def request_logging_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Bind the request id, time the request, log one line per request, and echo the id back.

    The success line is logged inside the ``try`` so the formatter still sees the request id; the
    ``finally`` resets it afterwards.
    """
    request_id = _incoming_request_id(request)
    token = request_id_var.set(request_id)
    started = time.perf_counter()
    try:
        response = await call_next(request)
        logger.info(
            "request",
            extra={
                "fields": {
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                }
            },
        )
    except Exception:
        logger.exception(
            "request failed",
            extra={
                "fields": {
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                }
            },
        )
        raise
    finally:
        request_id_var.reset(token)
    response.headers[REQUEST_ID_HEADER] = request_id
    return response
