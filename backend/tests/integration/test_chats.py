import logging
from collections.abc import Iterator, Sequence

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response  # TestClient is an httpx2 client in this FastAPI version
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.assistant import HISTORY_LIMIT, AssistantError, NoteContext, Turn, get_assistant
from app.main import app
from app.models import Chat, Message
from app.schemas.chat import TITLE_MAX_LENGTH
from app.schemas.message import CONTENT_MAX_LENGTH
from tests.integration.conftest import SignedInUser


class FailingAssistant:
    def reply(self, note: NoteContext, history: Sequence[Turn], question: str) -> str:
        raise AssistantError("provider down")


class RecordingAssistant:
    def __init__(self) -> None:
        self.calls: list[tuple[NoteContext, list[Turn], str]] = []

    def reply(self, note: NoteContext, history: Sequence[Turn], question: str) -> str:
        self.calls.append((note, list(history), question))
        return "ok"


@pytest.fixture
def failing_assistant(client: TestClient) -> Iterator[None]:
    """Depends on ``client`` so the override is set after the client's own and cleared with it."""
    app.dependency_overrides[get_assistant] = FailingAssistant
    yield
    app.dependency_overrides.pop(get_assistant, None)


@pytest.fixture
def recording_assistant(client: TestClient) -> Iterator[RecordingAssistant]:
    recorder = RecordingAssistant()
    app.dependency_overrides[get_assistant] = lambda: recorder
    yield recorder
    app.dependency_overrides.pop(get_assistant, None)


def _note(client: TestClient, user: SignedInUser, title: str = "Plan") -> int:
    response = client.post(
        "/notes", json={"title": title, "content": "Ship the chats API"}, headers=user.headers
    )
    assert response.status_code == 201, response.text
    note_id: int = response.json()["id"]
    return note_id


def _chat(client: TestClient, user: SignedInUser, note_id: int, title: str = "Questions") -> int:
    response = client.post(f"/notes/{note_id}/chats", json={"title": title}, headers=user.headers)
    assert response.status_code == 201, response.text
    chat_id: int = response.json()["id"]
    return chat_id


def _post(client: TestClient, user: SignedInUser, chat_id: int, content: str = "When?") -> Response:
    return client.post(
        f"/chats/{chat_id}/messages", json={"content": content}, headers=user.headers
    )


# Open a chat


def test_open_a_chat_on_any_users_note(
    client: TestClient, user: SignedInUser, second_user: SignedInUser
) -> None:
    note_id = _note(client, user)

    response = client.post(
        f"/notes/{note_id}/chats", json={"title": "  Questions "}, headers=second_user.headers
    )

    assert response.status_code == 201
    body = response.json()
    assert body["note_id"] == note_id
    assert body["user_id"] == second_user.id
    assert body["title"] == "Questions"
    assert body["created_at"] == body["updated_at"]


def test_open_a_chat_on_a_missing_note_is_404(client: TestClient, user: SignedInUser) -> None:
    response = client.post("/notes/999999/chats", json={"title": "Q"}, headers=user.headers)

    assert response.status_code == 404
    assert response.json() == {"detail": "Note not found"}


@pytest.mark.parametrize("title", ["", "   ", "x" * (TITLE_MAX_LENGTH + 1)])
def test_open_a_chat_with_a_bad_title_is_422(
    client: TestClient, user: SignedInUser, title: str
) -> None:
    note_id = _note(client, user)

    response = client.post(f"/notes/{note_id}/chats", json={"title": title}, headers=user.headers)

    assert response.status_code == 422


def test_chat_routes_without_a_token_are_401(client: TestClient, user: SignedInUser) -> None:
    note_id = _note(client, user)
    chat_id = _chat(client, user, note_id)

    assert client.get(f"/notes/{note_id}/chats").status_code == 401
    assert client.get(f"/chats/{chat_id}").status_code == 401
    assert client.post(f"/chats/{chat_id}/messages", json={"content": "hi"}).status_code == 401


# List


def test_list_shows_only_the_callers_chats_most_recently_updated_first(
    client: TestClient, user: SignedInUser, second_user: SignedInUser
) -> None:
    note_id = _note(client, user)
    first = _chat(client, user, note_id, "First")
    second = _chat(client, user, note_id, "Second")
    theirs = _chat(client, second_user, note_id, "Theirs")
    assert _post(client, user, first).status_code == 201

    mine = client.get(f"/notes/{note_id}/chats", headers=user.headers)
    other = client.get(f"/notes/{note_id}/chats", headers=second_user.headers)

    assert [chat["id"] for chat in mine.json()] == [first, second]
    assert [chat["id"] for chat in other.json()] == [theirs]


def test_list_is_bounded(client: TestClient, user: SignedInUser) -> None:
    note_id = _note(client, user)
    ids = [_chat(client, user, note_id, f"Chat {n}") for n in range(3)]

    response = client.get(
        f"/notes/{note_id}/chats", params={"limit": 1, "offset": 1}, headers=user.headers
    )

    assert [chat["id"] for chat in response.json()] == [ids[1]]


def test_list_on_a_missing_note_is_404(client: TestClient, user: SignedInUser) -> None:
    assert client.get("/notes/999999/chats", headers=user.headers).status_code == 404


# Read


def test_read_returns_the_chat_with_messages_oldest_first(
    client: TestClient, user: SignedInUser
) -> None:
    note_id = _note(client, user)
    chat_id = _chat(client, user, note_id)
    _post(client, user, chat_id, "First question")
    _post(client, user, chat_id, "Second question")

    response = client.get(f"/chats/{chat_id}", headers=user.headers)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == chat_id
    assert [m["role"] for m in body["messages"]] == ["user", "assistant", "user", "assistant"]
    assert body["messages"][0]["content"] == "First question"
    assert body["messages"][2]["content"] == "Second question"


def test_read_another_users_chat_is_403(
    client: TestClient, user: SignedInUser, second_user: SignedInUser
) -> None:
    chat_id = _chat(client, user, _note(client, user))

    response = client.get(f"/chats/{chat_id}", headers=second_user.headers)

    assert response.status_code == 403
    assert response.json() == {"detail": "Only the chat's user may access it"}


def test_read_a_missing_chat_is_404(client: TestClient, user: SignedInUser) -> None:
    response = client.get("/chats/999999", headers=user.headers)

    assert response.status_code == 404
    assert response.json() == {"detail": "Chat not found"}


# Rename and delete


def test_rename_by_the_chats_user(client: TestClient, user: SignedInUser) -> None:
    chat_id = _chat(client, user, _note(client, user))

    response = client.put(f"/chats/{chat_id}", json={"title": " Renamed "}, headers=user.headers)

    assert response.status_code == 200
    assert response.json()["title"] == "Renamed"


def test_rename_by_another_user_is_403_and_changes_nothing(
    client: TestClient, user: SignedInUser, second_user: SignedInUser
) -> None:
    chat_id = _chat(client, user, _note(client, user))

    response = client.put(f"/chats/{chat_id}", json={"title": "Mine"}, headers=second_user.headers)

    assert response.status_code == 403
    assert client.get(f"/chats/{chat_id}", headers=user.headers).json()["title"] == "Questions"


def test_delete_by_the_chats_user_removes_the_chat_and_its_messages(
    client: TestClient, user: SignedInUser, db_session: Session
) -> None:
    chat_id = _chat(client, user, _note(client, user))
    _post(client, user, chat_id)

    response = client.delete(f"/chats/{chat_id}", headers=user.headers)

    assert response.status_code == 204
    assert client.get(f"/chats/{chat_id}", headers=user.headers).status_code == 404
    assert client.delete(f"/chats/{chat_id}", headers=user.headers).status_code == 404
    remaining = db_session.scalar(
        select(func.count()).select_from(Message).where(Message.chat_id == chat_id)
    )
    assert remaining == 0


def test_delete_by_another_user_is_403(
    client: TestClient, user: SignedInUser, second_user: SignedInUser
) -> None:
    chat_id = _chat(client, user, _note(client, user))

    assert client.delete(f"/chats/{chat_id}", headers=second_user.headers).status_code == 403
    assert client.get(f"/chats/{chat_id}", headers=user.headers).status_code == 200


def test_deleting_the_note_removes_the_chat(client: TestClient, user: SignedInUser) -> None:
    note_id = _note(client, user)
    chat_id = _chat(client, user, note_id)

    assert client.delete(f"/notes/{note_id}", headers=user.headers).status_code == 204

    assert client.get(f"/chats/{chat_id}", headers=user.headers).status_code == 404


# Post a message


def test_post_stores_both_messages_and_bumps_updated_at(
    client: TestClient, user: SignedInUser
) -> None:
    chat_id = _chat(client, user, _note(client, user))
    before = client.get(f"/chats/{chat_id}", headers=user.headers).json()["updated_at"]

    response = _post(client, user, chat_id, " When? ")

    assert response.status_code == 201
    body = response.json()
    assert body["user_message"]["role"] == "user"
    assert body["user_message"]["content"] == "When?"
    assert body["assistant_message"]["role"] == "assistant"
    assert "When?" in body["assistant_message"]["content"]
    assert body["assistant_message"]["id"] > body["user_message"]["id"]
    after = client.get(f"/chats/{chat_id}", headers=user.headers).json()
    assert after["updated_at"] > before
    assert len(after["messages"]) == 2


def test_post_to_another_users_chat_is_403(
    client: TestClient, user: SignedInUser, second_user: SignedInUser
) -> None:
    chat_id = _chat(client, user, _note(client, user))

    assert _post(client, second_user, chat_id).status_code == 403
    assert client.get(f"/chats/{chat_id}", headers=user.headers).json()["messages"] == []


def test_post_to_a_missing_chat_is_404(client: TestClient, user: SignedInUser) -> None:
    assert _post(client, user, 999999).status_code == 404


@pytest.mark.parametrize("content", ["", "   ", "x" * (CONTENT_MAX_LENGTH + 1)])
def test_post_with_bad_content_is_422(client: TestClient, user: SignedInUser, content: str) -> None:
    chat_id = _chat(client, user, _note(client, user))

    assert _post(client, user, chat_id, content).status_code == 422


def test_the_assistant_sees_the_note_and_at_most_the_history_limit(
    client: TestClient, user: SignedInUser, recording_assistant: RecordingAssistant
) -> None:
    note_id = _note(client, user, title="Roadmap")
    chat_id = _chat(client, user, note_id)
    exchanges = HISTORY_LIMIT // 2 + 1

    for n in range(exchanges):
        assert _post(client, user, chat_id, f"q{n}").status_code == 201

    first_note, first_history, first_question = recording_assistant.calls[0]
    assert first_note == NoteContext(title="Roadmap", content="Ship the chats API")
    assert first_history == []
    assert first_question == "q0"
    _, last_history, _ = recording_assistant.calls[-1]
    assert len(last_history) == HISTORY_LIMIT
    assert last_history[0].role == "user"
    assert last_history[-1] == Turn(role="assistant", content="ok")


def test_a_chat_deleted_while_the_assistant_answers_is_404_and_stores_nothing(
    client: TestClient, user: SignedInUser, db_session: Session
) -> None:
    chat_id = _chat(client, user, _note(client, user))

    class DeletingAssistant:
        """Deletes the chat mid-reply, as another request could; the insert must then fail."""

        def reply(self, note: NoteContext, history: Sequence[Turn], question: str) -> str:
            db_session.execute(delete(Chat).where(Chat.id == chat_id))
            db_session.commit()
            return "too late"

    app.dependency_overrides[get_assistant] = DeletingAssistant
    response = _post(client, user, chat_id)
    app.dependency_overrides.pop(get_assistant, None)

    assert response.status_code == 404
    assert response.json() == {"detail": "Chat not found"}
    stored = db_session.scalar(
        select(func.count()).select_from(Message).where(Message.chat_id == chat_id)
    )
    assert stored == 0


@pytest.mark.usefixtures("failing_assistant")
def test_a_failing_assistant_is_502_and_stores_nothing(
    client: TestClient, user: SignedInUser, caplog: pytest.LogCaptureFixture
) -> None:
    chat_id = _chat(client, user, _note(client, user))
    before = client.get(f"/chats/{chat_id}", headers=user.headers).json()["updated_at"]

    with caplog.at_level(logging.ERROR, logger="taskmind.chats"):
        response = _post(client, user, chat_id)

    assert response.status_code == 502
    assert response.json() == {"detail": "Assistant unavailable"}
    after = client.get(f"/chats/{chat_id}", headers=user.headers).json()
    assert after["messages"] == []
    assert after["updated_at"] == before
    errors = [r for r in caplog.records if r.name == "taskmind.chats"]
    assert len(errors) == 1
    assert errors[0].__dict__["fields"] == {"chat_id": chat_id, "user_id": user.id}
    assert errors[0].exc_info is not None
