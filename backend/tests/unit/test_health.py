from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.database import get_db
from app.main import create_app


class _LostDatabase:
    """Stands in for a session whose connection is gone."""

    def execute(self, *args: object, **kwargs: object) -> None:
        raise OperationalError("SELECT 1", {}, ConnectionRefusedError("connection refused"))


def _lost_database() -> Iterator[_LostDatabase]:
    yield _LostDatabase()


def test_health_is_503_with_a_generic_body_when_the_database_is_gone() -> None:
    app = create_app()
    app.dependency_overrides[get_db] = _lost_database
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
    assert "refused" not in response.text
