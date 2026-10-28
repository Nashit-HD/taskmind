import logging
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response  # TestClient is an httpx2 client in this FastAPI version
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config import get_settings
from app.logging import REQUEST_ID_HEADER
from app.models import User
from app.security import create_access_token

EMAIL = "ada@example.com"
PASSWORD = "correct horse battery"


def _register(client: TestClient, email: str = EMAIL, password: str = PASSWORD) -> Response:
    return client.post("/auth/register", json={"email": email, "password": password})


def _login(client: TestClient, email: str = EMAIL, password: str = PASSWORD) -> Response:
    return client.post("/auth/login", json={"email": email, "password": password})


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_register_returns_the_user_without_any_secret(client: TestClient) -> None:
    response = _register(client)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == EMAIL
    assert isinstance(body["id"], int)
    assert body["created_at"].endswith("Z") or "+00:00" in body["created_at"]
    assert "password" not in response.text


def test_register_twice_with_any_letter_case_is_a_conflict(client: TestClient) -> None:
    assert _register(client).status_code == 201

    response = _register(client, email="ADA@Example.com")

    assert response.status_code == 409
    assert response.json() == {"detail": "Email already registered"}


def test_register_validates_the_body(client: TestClient) -> None:
    response = client.post("/auth/register", json={"email": "nope", "password": "short"})

    assert response.status_code == 422


def test_login_returns_a_bearer_token(client: TestClient) -> None:
    _register(client)

    response = _login(client)

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"].count(".") == 2


def test_login_with_the_wrong_password_and_with_an_unknown_email_look_the_same(
    client: TestClient,
) -> None:
    _register(client)

    wrong_password = _login(client, password="not it")
    unknown_email = _login(client, email="nobody@example.com")

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert (
        wrong_password.json() == unknown_email.json() == {"detail": "Incorrect email or password"}
    )
    assert wrong_password.headers["WWW-Authenticate"] == "Bearer"


def test_me_returns_the_signed_in_user(client: TestClient) -> None:
    registered = _register(client).json()
    token = _login(client).json()["access_token"]

    response = client.get("/auth/me", headers=_bearer(token))

    assert response.status_code == 200
    assert response.json() == registered


def test_me_without_a_token_is_401_with_a_challenge(client: TestClient) -> None:
    response = client.get("/auth/me")

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "authorization",
    ["Bearer not.a.token", "Basic YWRhOnB3", "Bearer "],
)
def test_me_with_a_malformed_token_is_401(client: TestClient, authorization: str) -> None:
    response = client.get("/auth/me", headers={"Authorization": authorization})

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_me_with_an_expired_token_is_401(client: TestClient) -> None:
    user_id = _register(client).json()["id"]
    settings = get_settings()
    expired = create_access_token(
        user_id,
        settings,
        now=datetime.now(UTC) - timedelta(minutes=settings.jwt_expire_minutes + 1),
    )

    response = client.get("/auth/me", headers=_bearer(expired))

    assert response.status_code == 401


def test_me_with_a_token_for_a_deleted_user_is_401(client: TestClient, db_session: Session) -> None:
    user_id = _register(client).json()["id"]
    token = _login(client).json()["access_token"]
    db_session.execute(delete(User).where(User.id == user_id))
    db_session.commit()

    response = client.get("/auth/me", headers=_bearer(token))

    assert response.status_code == 401


def test_a_signed_in_request_logs_the_user_id(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    user_id = _register(client).json()["id"]
    token = _login(client).json()["access_token"]

    with caplog.at_level(logging.INFO, logger="taskmind.request"):
        client.get("/auth/me", headers={**_bearer(token), REQUEST_ID_HEADER: "me-1"})

    lines = [r.__dict__["fields"] for r in caplog.records if r.name == "taskmind.request"]
    assert lines[-1]["path"] == "/auth/me"
    assert lines[-1]["user_id"] == user_id


def test_failed_authentication_is_logged_with_a_reason_and_no_token(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger="taskmind.auth"):
        client.get("/auth/me", headers=_bearer("abc.def.ghi"))

    warnings = [r for r in caplog.records if r.name == "taskmind.auth"]
    assert len(warnings) == 1
    assert warnings[0].__dict__["fields"]["reason"] == "invalid token"
    assert "abc.def.ghi" not in warnings[0].getMessage()
    assert "abc.def.ghi" not in str(warnings[0].__dict__["fields"])
