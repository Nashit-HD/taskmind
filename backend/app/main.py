"""FastAPI application factory.

``create_app()`` builds the app from settings; the module-level ``app`` is what ``fastapi dev`` and
``fastapi run`` serve, named in ``pyproject.toml`` under ``[tool.fastapi]``.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.logging import REQUEST_ID_HEADER, configure_logging, request_logging_middleware


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
    return application


app = create_app()
