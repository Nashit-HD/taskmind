"""FastAPI application factory.

``create_app()`` builds the app from settings; the module-level ``app`` is what ``fastapi dev`` and
``fastapi run`` serve, named in ``pyproject.toml`` under ``[tool.fastapi]``.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from app.config import get_settings
from app.logging import REQUEST_ID_HEADER, configure_logging, request_logging_middleware

logger = logging.getLogger("taskmind.database")


async def database_unavailable(request: Request, exc: Exception) -> JSONResponse:
    """A connection-level database failure is an outage, not a bug.

    The caller gets a generic 503; the detail and the trace go to the log with the request id.
    """
    logger.error(
        "database unavailable",
        extra={"fields": {"method": request.method, "path": request.url.path}},
        exc_info=exc,
    )
    return JSONResponse(status_code=503, content={"detail": "Database unavailable"})


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    application = FastAPI(title="TaskMind API", version="0.1.0")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[REQUEST_ID_HEADER],
    )
    application.middleware("http")(request_logging_middleware)
    application.add_exception_handler(OperationalError, database_unavailable)
    return application


app = create_app()
