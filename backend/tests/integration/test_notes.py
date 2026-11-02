import logging

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response  # TestClient is an httpx2 client in this FastAPI version
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Chat
from app.schemas.note import TITLE_MAX_LENGTH
from tests.integration.conftest import SignedInUser


def _create(
    client: TestClient, user: SignedInUser, title: str = "Plan", content: str = "text"
) -> Response:
    return client.post("/notes", json={"title": title, "content": content}, headers=user.headers)


def _create_id(client: TestClient, user: SignedInUser, title: str = "Plan") -> int:
    response = _create(client, user, title)
    assert response.status_code == 201, response.text
    note_id: int = response.json()["id"]
    return note_id


# Create


def test_create_returns_the_note_with_the_caller_as_author(
    client: TestClient, user: SignedInUser
) -> None:
    response = _create(client, user, title="  Plan  ")

    assert response.status_code == 201
    body = response.json()
    assert body["author_id"] == user.id
    assert body["title"] == "Plan"
    assert body["content"] == "text"
    assert isinstance(body["id"], int)
    assert body["created_at"] == body["updated_at"]


def test_create_defaults_the_content(client: TestClient, user: SignedInUser) -> None:
    response = client.post("/notes", json={"title": "Plan"}, headers=user.headers)

    assert response.status_code == 201
    assert response.json()["content"] == ""


def test_create_without_a_token_is_401(client: TestClient) -> None:
    response = client.post("/notes", json={"title": "Plan"})

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize("title", ["", "   ", "x" * (TITLE_MAX_LENGTH + 1)])
def test_create_with_a_bad_title_is_422(client: TestClient, user: SignedInUser, title: str) -> None:
    response = _create(client, user, title=title)

    assert response.status_code == 422


# List


def test_list_shows_every_users_notes_newest_first(
    client: TestClient, user: SignedInUser, second_user: SignedInUser
) -> None:
    first = _create_id(client, user, "First")
    second = _create_id(client, second_user, "Second")
    third = _create_id(client, user, "Third")

    response = client.get("/notes", headers=second_user.headers)

    assert response.status_code == 200
    assert [note["id"] for note in response.json()] == [third, second, first]


def test_list_is_bounded_by_limit_and_offset(client: TestClient, user: SignedInUser) -> None:
    ids = [_create_id(client, user, f"Note {n}") for n in range(5)]
    newest_first = list(reversed(ids))

    page_one = client.get("/notes", params={"limit": 2}, headers=user.headers)
    page_two = client.get("/notes", params={"limit": 2, "offset": 2}, headers=user.headers)

    assert [note["id"] for note in page_one.json()] == newest_first[:2]
    assert [note["id"] for note in page_two.json()] == newest_first[2:4]


@pytest.mark.parametrize(
    "params",
    [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"limit": "ten"}],
)
def test_list_with_out_of_range_bounds_is_422(
    client: TestClient, user: SignedInUser, params: dict[str, int | str]
) -> None:
    response = client.get("/notes", params=params, headers=user.headers)

    assert response.status_code == 422


def test_list_without_a_token_is_401(client: TestClient) -> None:
    assert client.get("/notes").status_code == 401


# Read


def test_read_returns_another_users_note(
    client: TestClient, user: SignedInUser, second_user: SignedInUser
) -> None:
    note_id = _create_id(client, user)

    response = client.get(f"/notes/{note_id}", headers=second_user.headers)

    assert response.status_code == 200
    assert response.json()["id"] == note_id
    assert response.json()["author_id"] == user.id


def test_read_a_missing_note_is_404(client: TestClient, user: SignedInUser) -> None:
    response = client.get("/notes/999999", headers=user.headers)

    assert response.status_code == 404
    assert response.json() == {"detail": "Note not found"}


def test_read_with_a_non_integer_id_is_422(client: TestClient, user: SignedInUser) -> None:
    assert client.get("/notes/abc", headers=user.headers).status_code == 422


# Update


def test_update_by_the_author_replaces_title_and_content(
    client: TestClient, user: SignedInUser
) -> None:
    note_id = _create_id(client, user)

    response = client.put(
        f"/notes/{note_id}", json={"title": " New ", "content": "changed"}, headers=user.headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "New"
    assert body["content"] == "changed"
    assert body["updated_at"] >= body["created_at"]
    assert client.get(f"/notes/{note_id}", headers=user.headers).json()["title"] == "New"


def test_update_by_another_user_is_403_and_changes_nothing(
    client: TestClient, user: SignedInUser, second_user: SignedInUser
) -> None:
    note_id = _create_id(client, user)

    response = client.put(
        f"/notes/{note_id}", json={"title": "Mine now", "content": ""}, headers=second_user.headers
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Only the author may change this note"}
    assert client.get(f"/notes/{note_id}", headers=user.headers).json()["title"] == "Plan"


def test_update_requires_every_field(client: TestClient, user: SignedInUser) -> None:
    note_id = _create_id(client, user)

    response = client.put(f"/notes/{note_id}", json={"title": "New"}, headers=user.headers)

    assert response.status_code == 422


def test_update_a_missing_note_is_404(client: TestClient, user: SignedInUser) -> None:
    response = client.put(
        "/notes/999999", json={"title": "New", "content": ""}, headers=user.headers
    )

    assert response.status_code == 404


# Delete


def test_delete_by_the_author_removes_the_note(client: TestClient, user: SignedInUser) -> None:
    note_id = _create_id(client, user)

    response = client.delete(f"/notes/{note_id}", headers=user.headers)

    assert response.status_code == 204
    assert response.content == b""
    assert client.get(f"/notes/{note_id}", headers=user.headers).status_code == 404


def test_delete_twice_is_404_the_second_time(client: TestClient, user: SignedInUser) -> None:
    note_id = _create_id(client, user)
    assert client.delete(f"/notes/{note_id}", headers=user.headers).status_code == 204

    assert client.delete(f"/notes/{note_id}", headers=user.headers).status_code == 404


def test_delete_by_another_user_is_403_and_keeps_the_note(
    client: TestClient, user: SignedInUser, second_user: SignedInUser
) -> None:
    note_id = _create_id(client, user)

    response = client.delete(f"/notes/{note_id}", headers=second_user.headers)

    assert response.status_code == 403
    assert client.get(f"/notes/{note_id}", headers=user.headers).status_code == 200


def test_delete_removes_the_notes_chats(
    client: TestClient, user: SignedInUser, db_session: Session
) -> None:
    note_id = _create_id(client, user)
    db_session.add(Chat(note_id=note_id, user_id=user.id, title="Questions"))
    db_session.commit()

    assert client.delete(f"/notes/{note_id}", headers=user.headers).status_code == 204

    remaining = db_session.scalar(
        select(func.count()).select_from(Chat).where(Chat.note_id == note_id)
    )
    assert remaining == 0


# Logging


def test_a_refused_change_is_logged_with_who_and_which(
    client: TestClient,
    user: SignedInUser,
    second_user: SignedInUser,
    caplog: pytest.LogCaptureFixture,
) -> None:
    note_id = _create_id(client, user)

    with caplog.at_level(logging.WARNING, logger="taskmind.notes"):
        client.delete(f"/notes/{note_id}", headers=second_user.headers)

    warnings = [r for r in caplog.records if r.name == "taskmind.notes"]
    assert len(warnings) == 1
    assert warnings[0].__dict__["fields"] == {
        "note_id": note_id,
        "user_id": second_user.id,
        "author_id": user.id,
    }
    assert "Plan" not in str(warnings[0].__dict__["fields"])
