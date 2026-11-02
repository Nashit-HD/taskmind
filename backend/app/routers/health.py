"""Liveness with its one dependency: 200 only when the database answers.

Unauthenticated by design: Compose's healthcheck, and later a load balancer, call it with no
token. It reveals up or down and nothing else. A connection failure raises ``OperationalError``,
which the app-wide handler turns into 503 ``Database unavailable`` with the trace in the log.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.database import SessionDep

router = APIRouter(tags=["health"])


class HealthRead(BaseModel):
    status: str
    database: str


@router.get("/health")
def health(db: SessionDep) -> HealthRead:
    db.execute(text("SELECT 1"))
    return HealthRead(status="ok", database="ok")
