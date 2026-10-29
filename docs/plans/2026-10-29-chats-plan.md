# Chats and Messages Implementation Plan

> **For agentic workers:** Use `/explain-plan` to preview all tasks, then `/execute-plan` to implement task-by-task.

**Goal:** Let a signed-in user open private chats on any note, rename and delete them, and post messages that the assistant answers, with an echo assistant standing in until PR 7.

**Spec:** `docs/plans/2026-10-20-backend-design.md` § Decisions (Layers, Assistant down, Assistant grounding, List bounds), § Schemas (Chat, Message), § Endpoints (`/notes/{id}/chats`, `/chats/{id}`, `/chats/{id}/messages`), § Edge cases, § Testing design. ADR 0003: chats are private to their user and belong to one note. Terms per `GLOSSARY.md`.

**Affected components:** backend — `backend/`; README and `AGENTS.md` at the repo root

**Change class:** standard — new endpoints and data access, a new seam (the assistant protocol), no migration, no new dependency. Elevated per `review.md` § Overrides: every route decides authorisation.

**Branch:** `feat/chats`, cut from `feat/notes` while PR 4 is in review, because the routes reuse the pagination module and the signed-in-user fixtures from PR 4. The PR targets `feat/notes`; GitHub retargets it to `main` when PR 4 merges.

---

## Policy answers, checked

- **Entry points and authorisation.** Six routes on two routers, both declaring `get_current_user`
  at router level (`security.md` rule 1). Opening a chat and listing chats need the note to exist
  (404 otherwise); any signed-in user may do both, by the spec. The list filters by the caller's id
  in the query, so another user's chats are never fetched (`security.md` rule 3, ADR 0003). Read,
  rename, delete and post load the chat and compare its `user_id` with the token's user; a mismatch
  is 403 and nothing changes. 404 before 403 as for notes: a chat id reveals nothing. Default is
  deny.
- **Input.** Chat titles stripped, 1 to 100 characters (column width). Message content stripped,
  1 to 4000 characters (spec). `PUT` replaces the title. `limit` and `offset` reuse
  `app/pagination.py`. Path ids are `int`.
- **Data access.** List: one query on `(note_id, user_id)` ordered by `updated_at DESC, id DESC`,
  served by `ix_chats_note_id_user_id_updated_at` (`performance.md` rules 1, 3, 5). Chat detail:
  one primary-key lookup plus one bounded query for the last `MESSAGES_IN_DETAIL` (200) messages
  on `ix_messages_chat_id_created_at`, returned oldest first. **Departure from the spec**, which
  said "all messages, one query": an unbounded collection is never grandfathered under
  `performance.md`, so the detail carries the most recent 200. Post: the last `HISTORY_LIMIT`
  (20) messages for the assistant, same index. No loop touches the database.
- **The assistant call and the transaction.** The spec said the message insert, assistant call,
  reply insert and `updated_at` bump are "one transaction committed after the call succeeds".
  `performance.md` § HD decisions says a transaction is never held across an outbound call.
  **Departure:** the handler reads what it needs, ends the read transaction, calls the assistant
  with nothing open, then writes the user message, the reply and the bump in one short
  transaction. The invariant the spec wanted holds: a failing assistant leaves nothing behind
  (502 `Assistant unavailable`), and a chat never has a question without an answer
  (`reliability.md` rules 7, 8, 9). If the chat is deleted while the assistant is answering, the
  insert's foreign key fails and the handler answers 404 after a rollback.
- **The seam.** `app/assistant.py` holds an `Assistant` protocol, an `EchoAssistant` default, and
  `get_assistant`. Routers never call a provider directly (`maintainability.md` rule 5). PR 7
  replaces the default; tests override the dependency. No outbound call exists in this PR, so
  `reliability.md` rules 5 and 6 (timeout, retry) land with the OpenAI client in PR 7, and the
  echo needs none.
- **`updated_at` bump.** The post sets `updated_at = clock_timestamp()` explicitly rather than
  relying on `onupdate=now()`: `now()` is frozen at transaction start in Postgres, so two bumps in
  one transaction (as in the test suite's rolled-back session) would tie, and "most recently
  updated first" would be untestable. `clock_timestamp()` is the wall clock at the statement.
- **Delete.** Hard delete; messages go through `ON DELETE CASCADE`; the row is loaded and
  user-checked first, so a second call is 404 (`reliability.md` rule 11).
- **Observability.** Create, rename, delete and exchange log `chat_id` and `user_id`; the exchange
  also logs the reply length, never its text. 403 logs a warning with `chat_id`, `user_id` and
  the chat's `user_id`; 404 logs the id; assistant failure logs an error with the exception
  (`observability.md` rule 3). The three lines rule 9 asks for go in the PR.
- **Testing.** Unit: the schemas and the echo assistant, no database. Integration: every route and
  every status in the spec's table, with two users, the default echo assistant, a failing assistant
  overriding the dependency, and a recording assistant to prove the history cap.
- **Cloud, monitoring, alerts.** Not applicable.

## Files

| File | Job |
|---|---|
| `backend/app/schemas/text.py` | `strip_text`, the before-validator notes, chats and messages share |
| `backend/app/schemas/note.py` | Use `strip_text` instead of its private copy |
| `backend/app/schemas/chat.py` | `ChatCreate`, `ChatUpdate`, `ChatRead`, `ChatDetail` |
| `backend/app/schemas/message.py` | `MessageCreate`, `MessageRead`, `MessageExchange` |
| `backend/app/assistant.py` | `Assistant` protocol, `NoteContext`, `Turn`, `AssistantError`, `EchoAssistant`, `get_assistant`, `AssistantDep` |
| `backend/app/routers/chats.py` | The six routes, the user check, the message exchange |
| `backend/app/main.py` | Include the two chat routers |
| `backend/tests/unit/test_schemas.py` | Chat and message schema tests, appended |
| `backend/tests/unit/test_assistant.py` | Echo assistant and default dependency |
| `backend/tests/integration/test_chats.py` | Endpoint tests |
| `README.md` | A Chats subsection |
| `AGENTS.md` | Architecture lines for `assistant.py` and `pagination.py` |

---

### Task 1: Schemas and the assistant seam

**Files:**
- Create: `backend/app/schemas/text.py`
- Modify: `backend/app/schemas/note.py`
- Create: `backend/app/schemas/chat.py`
- Create: `backend/app/schemas/message.py`
- Create: `backend/app/assistant.py`
- Modify: `backend/tests/unit/test_schemas.py`
- Create: `backend/tests/unit/test_assistant.py`

- [ ] **Step 1: The shared strip helper**

`backend/app/schemas/text.py`:

```python
"""Text handling every request schema shares."""


def strip_text(value: object) -> object:
    """Trim a string before validation, so a whitespace-only value is empty and the length rules
    see the real text. Anything that is not a string is left for Pydantic to reject."""
    return value.strip() if isinstance(value, str) else value
```

- [ ] **Step 2: Note schemas use it**

`backend/app/schemas/note.py` becomes:

```python
"""Request and response schemas for notes.

Request and response classes are separate. ``PUT`` replaces the note, so ``NoteUpdate`` requires
every field. Titles are stripped before the length check, so a whitespace-only title is empty and
rejected; the maximum is the column width.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.text import strip_text

TITLE_MAX_LENGTH = 200
# Not in the spec, which caps only message content. The whole note goes to the assistant on every
# message, so its size needs a ceiling. Generous for a note; far below anything the database or
# the model would choke on.
CONTENT_MAX_LENGTH = 20_000


class NoteCreate(BaseModel):
    title: str = Field(min_length=1, max_length=TITLE_MAX_LENGTH)
    content: str = Field(default="", max_length=CONTENT_MAX_LENGTH)

    @field_validator("title", mode="before")
    @classmethod
    def _strip_title(cls, value: object) -> object:
        return strip_text(value)


class NoteUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=TITLE_MAX_LENGTH)
    content: str = Field(max_length=CONTENT_MAX_LENGTH)

    @field_validator("title", mode="before")
    @classmethod
    def _strip_title(cls, value: object) -> object:
        return strip_text(value)


class NoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    author_id: int
    title: str
    content: str
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 3: Message schemas**

`backend/app/schemas/message.py`:

```python
"""Request and response schemas for messages.

A message is written once and never changes, so there is no update schema. Posting one returns
both halves of the exchange: the user's message and the assistant's reply.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.text import strip_text

CONTENT_MAX_LENGTH = 4000


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=CONTENT_MAX_LENGTH)

    @field_validator("content", mode="before")
    @classmethod
    def _strip_content(cls, value: object) -> object:
        return strip_text(value)


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    chat_id: int
    role: str
    content: str
    created_at: datetime


class MessageExchange(BaseModel):
    user_message: MessageRead
    assistant_message: MessageRead
```

- [ ] **Step 4: Chat schemas**

`backend/app/schemas/chat.py`:

```python
"""Request and response schemas for chats.

``ChatDetail`` is a chat with its most recent messages, oldest first; the list and create routes
return ``ChatRead`` without them.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.message import MessageRead
from app.schemas.text import strip_text

TITLE_MAX_LENGTH = 100


class ChatCreate(BaseModel):
    title: str = Field(min_length=1, max_length=TITLE_MAX_LENGTH)

    @field_validator("title", mode="before")
    @classmethod
    def _strip_title(cls, value: object) -> object:
        return strip_text(value)


class ChatUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=TITLE_MAX_LENGTH)

    @field_validator("title", mode="before")
    @classmethod
    def _strip_title(cls, value: object) -> object:
        return strip_text(value)


class ChatRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    note_id: int
    user_id: int
    title: str
    created_at: datetime
    updated_at: datetime


class ChatDetail(ChatRead):
    messages: list[MessageRead]
```

- [ ] **Step 5: The assistant seam**

`backend/app/assistant.py`:

```python
"""The assistant, behind one seam.

The assistant is the one thing in the backend that will leave the process (PR 7 adds the OpenAI
client). Routers never call a provider directly: they declare ``AssistantDep`` and call ``reply``.
Tests override ``get_assistant`` with a fake; PR 7 replaces the default.

Until then the default is ``EchoAssistant``, which quotes the question back and names the note, so
the whole chat flow works end to end with no network and no key.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Annotated, Protocol

from fastapi import Depends

# How many earlier messages the assistant is shown. Bounds the payload per the spec.
HISTORY_LIMIT = 20


class AssistantError(Exception):
    """The assistant could not answer. The router answers 502 and writes nothing."""


@dataclass(frozen=True)
class NoteContext:
    """The one note the assistant may answer from."""

    title: str
    content: str


@dataclass(frozen=True)
class Turn:
    """One earlier message in the chat, as the assistant sees it."""

    role: str
    content: str


class Assistant(Protocol):
    def reply(self, note: NoteContext, history: Sequence[Turn], question: str) -> str:
        """Answer ``question`` from ``note`` only. Raises ``AssistantError`` when it cannot."""
        ...


class EchoAssistant:
    """A stand-in that proves the flow: it quotes the question back and names the note."""

    def reply(self, note: NoteContext, history: Sequence[Turn], question: str) -> str:
        return f'(echo) About "{note.title}": {question}'


_default = EchoAssistant()


def get_assistant() -> Assistant:
    return _default


AssistantDep = Annotated[Assistant, Depends(get_assistant)]
```

- [ ] **Step 6: Unit tests**

Append to `backend/tests/unit/test_schemas.py`, with these imports added before the
`app.schemas.note` line (Ruff sorts them alphabetically):
`from app.schemas.chat import TITLE_MAX_LENGTH as CHAT_TITLE_MAX_LENGTH` and
`from app.schemas.chat import ChatCreate, ChatUpdate` and
`from app.schemas.message import CONTENT_MAX_LENGTH as MESSAGE_MAX_LENGTH` and
`from app.schemas.message import MessageCreate`:

```python
def test_chat_create_strips_the_title() -> None:
    assert ChatCreate(title="  Questions ").title == "Questions"


@pytest.mark.parametrize("title", ["", "  ", "x" * (CHAT_TITLE_MAX_LENGTH + 1)])
def test_chat_create_rejects_an_empty_or_over_long_title(title: str) -> None:
    with pytest.raises(ValidationError):
        ChatCreate(title=title)


def test_chat_update_requires_a_title() -> None:
    with pytest.raises(ValidationError):
        ChatUpdate.model_validate({})


def test_message_create_strips_the_content() -> None:
    assert MessageCreate(content=" hi ").content == "hi"


@pytest.mark.parametrize("content", ["", "\n", "x" * (MESSAGE_MAX_LENGTH + 1)])
def test_message_create_rejects_empty_or_over_long_content(content: str) -> None:
    with pytest.raises(ValidationError):
        MessageCreate(content=content)
```

`backend/tests/unit/test_assistant.py`:

```python
from app.assistant import EchoAssistant, NoteContext, Turn, get_assistant


def test_the_echo_quotes_the_question_and_names_the_note() -> None:
    reply = EchoAssistant().reply(
        NoteContext(title="Plan", content="Ship it"), [Turn("user", "earlier")], "When?"
    )

    assert "When?" in reply
    assert "Plan" in reply
    assert "Ship it" not in reply


def test_the_default_assistant_is_the_echo() -> None:
    assert isinstance(get_assistant(), EchoAssistant)
```

Check: `cd backend && uv run pytest tests/unit` passes; `uv run mypy` and `uv run ruff check .`
are clean.

---

### Task 2: The chat routers and endpoint tests

**Files:**
- Create: `backend/app/routers/chats.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/integration/test_chats.py`

- [ ] **Step 1: The routers**

`backend/app/routers/chats.py`:

```python
"""Chats and messages: private to the user who opened the chat (ADR 0003).

Two routers: ``note_chats`` for ``/notes/{note_id}/chats`` and ``chats`` for ``/chats/{chat_id}``.
Both require a signed-in user at router level. Every chat route loads the row and compares its
``user_id`` with the token's user; the list filters by that id in the query, so another user's
chats are never fetched at all. 404 comes before 403: a chat id reveals nothing.

Posting a message: the handler reads the chat, the note and the recent history, ends that read
transaction, and calls the assistant with nothing open and nothing written. Then the user message,
the reply and the chat's ``updated_at`` bump are one short transaction. A failing assistant is 502
and leaves nothing behind, so a chat never has a question without an answer. The spec said "one
transaction around the call"; HD never holds a transaction across an outbound call, so the writes
come after it instead, with the same invariant.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.assistant import HISTORY_LIMIT, AssistantDep, AssistantError, NoteContext, Turn
from app.auth import CurrentUserDep, get_current_user
from app.database import SessionDep
from app.models import Chat, Message, MessageRole, Note, User
from app.pagination import DEFAULT_LIMIT, LimitQuery, OffsetQuery
from app.schemas.chat import ChatCreate, ChatDetail, ChatRead, ChatUpdate
from app.schemas.message import MessageCreate, MessageExchange, MessageRead

logger = logging.getLogger("taskmind.chats")

note_chats = APIRouter(
    prefix="/notes/{note_id}/chats", tags=["chats"], dependencies=[Depends(get_current_user)]
)
chats = APIRouter(prefix="/chats", tags=["chats"], dependencies=[Depends(get_current_user)])

# How many messages a chat detail carries: the most recent ones, oldest first. A bound, because a
# response that grows with the table is never acceptable; the frontend can page later if needed.
MESSAGES_IN_DETAIL = 200


def _load_note(db: Session, note_id: int) -> Note:
    note = db.get(Note, note_id)
    if note is None:
        logger.info("note not found", extra={"fields": {"note_id": note_id}})
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    return note


def _load_chat_for_user(db: Session, chat_id: int, user: User) -> Chat:
    """The chat, only if ``user`` opened it: checked against the token's user, never the request."""
    chat = db.get(Chat, chat_id)
    if chat is None:
        logger.info("chat not found", extra={"fields": {"chat_id": chat_id}})
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    if chat.user_id != user.id:
        logger.warning(
            "chat access refused",
            extra={
                "fields": {"chat_id": chat_id, "user_id": user.id, "chat_user_id": chat.user_id}
            },
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Only the chat's user may access it"
        )
    return chat


def _recent_messages(db: Session, chat_id: int, limit: int) -> list[Message]:
    """The last ``limit`` messages of the chat, oldest first, via ix_messages_chat_id_created_at."""
    newest_first = db.scalars(
        select(Message)
        .where(Message.chat_id == chat_id)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(limit)
    ).all()
    return list(reversed(newest_first))


@note_chats.get("")
def list_chats(
    note_id: int,
    user: CurrentUserDep,
    db: SessionDep,
    limit: LimitQuery = DEFAULT_LIMIT,
    offset: OffsetQuery = 0,
) -> list[ChatRead]:
    """The caller's chats on the note, most recently updated first.

    Filtered by the caller's id in the query, so nobody else's chats are read.
    ``ix_chats_note_id_user_id_updated_at`` serves the filter and the sort; ``id`` breaks ties.
    """
    _load_note(db, note_id)
    rows = db.scalars(
        select(Chat)
        .where(Chat.note_id == note_id, Chat.user_id == user.id)
        .order_by(Chat.updated_at.desc(), Chat.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [ChatRead.model_validate(chat) for chat in rows]


@note_chats.post("", status_code=status.HTTP_201_CREATED)
def create_chat(note_id: int, body: ChatCreate, user: CurrentUserDep, db: SessionDep) -> ChatRead:
    _load_note(db, note_id)
    chat = Chat(note_id=note_id, user_id=user.id, title=body.title)
    db.add(chat)
    db.commit()
    db.refresh(chat)
    logger.info(
        "chat opened",
        extra={"fields": {"chat_id": chat.id, "note_id": note_id, "user_id": user.id}},
    )
    return ChatRead.model_validate(chat)


@chats.get("/{chat_id}")
def read_chat(chat_id: int, user: CurrentUserDep, db: SessionDep) -> ChatDetail:
    chat = _load_chat_for_user(db, chat_id, user)
    messages = _recent_messages(db, chat.id, MESSAGES_IN_DETAIL)
    return ChatDetail(
        **ChatRead.model_validate(chat).model_dump(),
        messages=[MessageRead.model_validate(message) for message in messages],
    )


@chats.put("/{chat_id}")
def rename_chat(chat_id: int, body: ChatUpdate, user: CurrentUserDep, db: SessionDep) -> ChatRead:
    chat = _load_chat_for_user(db, chat_id, user)
    chat.title = body.title
    db.commit()
    db.refresh(chat)
    logger.info("chat renamed", extra={"fields": {"chat_id": chat_id, "user_id": user.id}})
    return ChatRead.model_validate(chat)


@chats.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chat(chat_id: int, user: CurrentUserDep, db: SessionDep) -> None:
    """Deletes the chat and, through ``ON DELETE CASCADE``, its messages."""
    chat = _load_chat_for_user(db, chat_id, user)
    db.delete(chat)
    db.commit()
    logger.info("chat deleted", extra={"fields": {"chat_id": chat_id, "user_id": user.id}})


@chats.post("/{chat_id}/messages", status_code=status.HTTP_201_CREATED)
def post_message(
    chat_id: int,
    body: MessageCreate,
    user: CurrentUserDep,
    db: SessionDep,
    assistant: AssistantDep,
) -> MessageExchange:
    chat = _load_chat_for_user(db, chat_id, user)
    note = db.get_one(Note, chat.note_id)
    context = NoteContext(title=note.title, content=note.content)
    history = [
        Turn(role=message.role, content=message.content)
        for message in _recent_messages(db, chat_id, HISTORY_LIMIT)
    ]
    # Nothing has been written. End the read transaction so no connection or snapshot is held
    # while the assistant works; the session starts a fresh one at the next statement.
    db.commit()

    try:
        reply = assistant.reply(context, history, body.content)
    except AssistantError as exc:
        logger.error(
            "assistant failed",
            extra={"fields": {"chat_id": chat_id, "user_id": user.id}},
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Assistant unavailable"
        ) from exc

    user_message = Message(chat_id=chat_id, role=MessageRole.USER, content=body.content)
    assistant_message = Message(chat_id=chat_id, role=MessageRole.ASSISTANT, content=reply)
    db.add_all([user_message, assistant_message])
    try:
        db.flush()
        # clock_timestamp(), not now(): now() is frozen at transaction start, so two bumps in one
        # transaction would tie and "most recently updated first" would not hold.
        db.execute(update(Chat).where(Chat.id == chat_id).values(updated_at=func.clock_timestamp()))
        db.commit()
    except IntegrityError:
        # The chat was deleted while the assistant was answering: the foreign key refuses the
        # insert. Nothing is kept.
        db.rollback()
        logger.warning("chat vanished during reply", extra={"fields": {"chat_id": chat_id}})
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found"
        ) from None
    db.refresh(user_message)
    db.refresh(assistant_message)
    logger.info(
        "message exchanged",
        extra={"fields": {"chat_id": chat_id, "user_id": user.id, "reply_chars": len(reply)}},
    )
    return MessageExchange(
        user_message=MessageRead.model_validate(user_message),
        assistant_message=MessageRead.model_validate(assistant_message),
    )
```

- [ ] **Step 2: Include the routers**

In `backend/app/main.py`, the routers import becomes:

```python
from app.routers import auth, chats, notes
```

and after `application.include_router(notes.router)`:

```python
    application.include_router(chats.note_chats)
    application.include_router(chats.chats)
```

- [ ] **Step 3: Endpoint tests**

`backend/tests/integration/test_chats.py`:

```python
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
```

Check: `cd backend && uv run pytest tests/integration/test_chats.py` passes; the Validate command
is clean; the full suite passes.

---

### Task 3: README and AGENTS.md

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`

- [ ] **Step 1: A Chats subsection in the README**

Insert after the Notes subsection (after the line
"`limit` is 1 to 100 (default 50). Changing someone else's note is a 403; a missing note is a 404.")
and before "### Changing the schema":

````markdown
### Chats

A chat belongs to one note and is private to the user who opened it. Posting a message stores it,
asks the assistant, and stores the reply. Until PR 7 the assistant is an echo, so the flow can be
tried without an API key.

```bash
curl -s -X POST localhost:8000/notes/1/chats -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"title": "Questions"}'
curl -s localhost:8000/notes/1/chats -H "Authorization: Bearer $TOKEN"
curl -s -X POST localhost:8000/chats/1/messages -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"content": "What is the plan?"}'
curl -s localhost:8000/chats/1 -H "Authorization: Bearer $TOKEN"
curl -s -X PUT localhost:8000/chats/1 -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"title": "Plan questions"}'
curl -s -X DELETE localhost:8000/chats/1 -H "Authorization: Bearer $TOKEN" -o /dev/null -w '%{http_code}\n'
```

A chat detail carries its most recent 200 messages, oldest first. Messages are at most 4000
characters. Another user's chat is a 403; if the assistant fails the reply is a 502 and nothing
is stored.
````

- [ ] **Step 2: AGENTS.md architecture lines**

In `AGENTS.md` under "## Architecture & Structure", replace the line beginning
"- Planned per `docs/plans/2026-10-20-backend-design.md`:" with these three lines:

```markdown
- `backend/app/assistant.py` — the `Assistant` protocol, `get_assistant` and `AssistantDep`; routers never call a provider directly, tests override the dependency, PR 7 swaps the `EchoAssistant` default for OpenAI
- `backend/app/pagination.py` — `LimitQuery`/`OffsetQuery`, the bounds every list endpoint shares
- Planned per `docs/plans/2026-10-20-backend-design.md`: `models/`, `schemas/`, `routers/` as built; a Dockerfile and `/health` in PR 6
```

Check: the README renders with one bash fence in the new subsection; `AGENTS.md` still has the
HD required section above the divider.

---

## Gaps against HD policy, recorded on purpose

- Observability rule 11 (OpenInference tracing in Phoenix) stays a gap, as the spec records; the
  assistant call is logged with its ids and reply length. Timeout and retry obligations belong to
  the OpenAI client in PR 7; the echo makes no outbound call.

## Documentation Notes

- How the six routes are observed → **PR**: JSON lines on `taskmind.chats` (opened, renamed, deleted, exchanged with `reply_chars`, refused, not found, assistant failed with the exception) plus the per-request line; failing looks like a 502 line with `exc_info` or a 5xx on the request line.
- The writes come after the assistant call, not around it, and why → **code** `app/routers/chats.py` docstring (Task 2), and **PR** as a departure from the spec.
- Chat detail is bounded at 200 messages → **PR** as a departure from the spec; **decision**: the spec's Endpoints row should say so on next revision.
- `clock_timestamp()` for the bump → **code** comment in `post_message` (Task 2).
- The assistant is a dependency; routers never call OpenAI directly → **AGENTS.md** Architecture & Structure (Task 3, the spec's own note).
