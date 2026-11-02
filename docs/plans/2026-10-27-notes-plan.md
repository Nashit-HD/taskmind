# Notes Implementation Plan

> **For agentic workers:** Use `/explain-plan` to preview all tasks, then `/execute-plan` to implement task-by-task.

**Goal:** Let every signed-in user list, read and create notes, and let only a note's author change or delete it, with every list bounded.

**Spec:** `docs/plans/2026-10-20-backend-design.md` § Decisions (Authorisation, List bounds), § Schemas (Note), § Endpoints (`/notes`, `/notes/{id}`), § Edge cases, § Testing design. Terms per `GLOSSARY.md`: a note's **author**, a signed-in **user**.

**Affected components:** backend — `backend/`; README at the repo root

**Change class:** standard — new endpoints and new data access, no migration, no new dependency. Elevated per `review.md` § Overrides: every route decides authorisation. The decision it rests on is the spec's Authorisation row (author-only edit and delete).

| Revision | Closed | Sections changed |
|---|---|---|
| r2 | N1, N2 | Task 2 Step 4 (`params` annotation), Task 2 Step 3 (`SignedInUser` docstring) |

**Branch:** `feat/notes`, cut from `feat/auth` while PR 3 is still in review, because every route here declares the `get_current_user` dependency PR 3 adds. The pull request targets `feat/auth`; GitHub retargets it to `main` when PR 3 merges. This departs from `reset-to-base`, which cuts from the base branch, and the PR description says so.

---

## Policy answers, checked

- **Entry points and authorisation.** Five routes, all under one router that declares
  `get_current_user` at router level (`dependencies=[Depends(get_current_user)]`), so a route added
  later cannot forget it (`security.md` rule 1). A missing or bad token is the 401 PR 3 defined.
  List, read and create are open to every signed-in user, by the spec: notes are shared. Update and
  delete load the row and compare its `author_id` with the signed-in user's id from the token, never
  with anything in the request (`security.md` rule 3); a mismatch is 403 and nothing changes. A
  missing note is 404 before the author check, which reveals nothing, because every user may read
  every note anyway. Default is deny: the dependency raises before the handler runs.
- **Input.** `NoteCreate` and `NoteUpdate` strip the title and require it non-empty, at most 200
  characters, which is the column width. `PUT` replaces, so `NoteUpdate` requires both fields.
  `limit` is 1 to 100, default 50; `offset` is 0 or more; FastAPI returns 422 for anything else
  before the handler runs. Path ids are `int`, so a non-integer id is 422.
- **Content length, added here.** The spec caps message content at 4000 characters and says nothing
  about note content. Postgres `text` accepts up to a gigabyte, and PR 7 sends the whole note to the
  assistant on every message. This plan caps `content` at 20,000 characters (`security.md` rule 13,
  `performance.md` rule 8). It is the one addition to the approved spec; say so in the PR.
- **Data access.** List is one query: `ORDER BY created_at DESC, id DESC LIMIT :limit OFFSET
  :offset`. The existing `ix_notes_created_at` serves the sort; `id` breaks ties, because rows
  created in one transaction share a `now()` timestamp (`performance.md` rules 1, 3 and 5). Read,
  update and delete are one primary-key lookup each, plus one statement for the write. No loop over
  rows reaches the database (`performance.md` rule 2).
- **Delete.** A hard delete, by the spec; chats and messages go with it through `ON DELETE CASCADE`
  (PR 2), and `passive_deletes=True` keeps SQLAlchemy from loading them first. The row is loaded and
  author-checked before the delete, so a second call is 404 and nobody else's call does anything
  (`reliability.md` rule 11). There is no soft delete: the domain does not ask for one.
- **Dependency failure.** Postgres only; the 503 handler from PR 2 covers it. No outbound calls.
- **Observability.** Create, update and delete log the `note_id` and `user_id`. The 403 branch
  logs a warning with `note_id`, `user_id` and `author_id`; the 404 branch logs the `note_id`
  (`observability.md` rule 3). No title or content goes to the log. The per-request line from PR 1
  carries status, duration and `user_id`. The three lines rule 9 asks for go in the PR description.
- **Testing.** Unit: the schemas, no database. Integration: every route, every status code in the
  spec's table, through the test client with the rolled-back session from PR 2, as two signed-in
  users so the 403 cases are real.
- **Cloud, monitoring, alerts.** Not applicable: nothing deploys.

## Files

| File | Job |
|---|---|
| `backend/app/pagination.py` | `limit` and `offset` query parameters with their bounds, shared by every list endpoint (chats reuse them in PR 5) |
| `backend/app/schemas/note.py` | `NoteCreate`, `NoteUpdate`, `NoteRead` |
| `backend/app/routers/notes.py` | The five routes and the author check |
| `backend/app/main.py` | Include the notes router |
| `backend/tests/unit/test_schemas.py` | Note schema tests, added to the existing file |
| `backend/tests/integration/conftest.py` | `user` and `second_user` fixtures: a registered, signed-in user with its bearer header |
| `backend/tests/integration/test_notes.py` | Endpoint tests |
| `README.md` | A Notes subsection under Running the backend locally |

The spec's code layout lists no `pagination.py`. It is added because `limit`/`offset` with the same
bounds appear on `/notes` now and on `/notes/{id}/chats` in PR 5, and one definition keeps the
bounds equal (`maintainability.md` rule 4).

---

### Task 1: Note schemas and list bounds

**Files:**
- Create: `backend/app/pagination.py`
- Create: `backend/app/schemas/note.py`
- Modify: `backend/tests/unit/test_schemas.py`

- [ ] **Step 1: The list bounds**

`backend/app/pagination.py`:

```python
"""Bounds for every list endpoint.

A list with no bound returns the whole table one day. ``limit`` defaults to 50 and may not exceed
100; ``offset`` may not be negative; FastAPI answers 422 to anything else before the handler runs.
The numbers are the spec's (§ Decisions, List bounds). Declare a parameter as

    limit: LimitQuery = DEFAULT_LIMIT, offset: OffsetQuery = 0
"""

from typing import Annotated

from fastapi import Query

DEFAULT_LIMIT = 50
MAX_LIMIT = 100

LimitQuery = Annotated[int, Query(ge=1, le=MAX_LIMIT)]
OffsetQuery = Annotated[int, Query(ge=0)]
```

- [ ] **Step 2: The schemas**

`backend/app/schemas/note.py`:

```python
"""Request and response schemas for notes.

Request and response classes are separate. ``PUT`` replaces the note, so ``NoteUpdate`` requires
every field. Titles are stripped before the length check, so a whitespace-only title is empty and
rejected; the maximum is the column width.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

TITLE_MAX_LENGTH = 200
# Not in the spec, which caps only message content. The whole note goes to the assistant on every
# message, so its size needs a ceiling. Generous for a note; far below anything the database or
# the model would choke on.
CONTENT_MAX_LENGTH = 20_000


def _strip(value: object) -> object:
    """Trim a string before validation; leave anything else for Pydantic to reject."""
    return value.strip() if isinstance(value, str) else value


class NoteCreate(BaseModel):
    title: str = Field(min_length=1, max_length=TITLE_MAX_LENGTH)
    content: str = Field(default="", max_length=CONTENT_MAX_LENGTH)

    @field_validator("title", mode="before")
    @classmethod
    def _strip_title(cls, value: object) -> object:
        return _strip(value)


class NoteUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=TITLE_MAX_LENGTH)
    content: str = Field(max_length=CONTENT_MAX_LENGTH)

    @field_validator("title", mode="before")
    @classmethod
    def _strip_title(cls, value: object) -> object:
        return _strip(value)


class NoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    author_id: int
    title: str
    content: str
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 3: Unit tests**

Append to `backend/tests/unit/test_schemas.py`, and add
`from app.schemas.note import CONTENT_MAX_LENGTH, TITLE_MAX_LENGTH, NoteCreate, NoteUpdate` to its
imports, after the `app.schemas.user` line:

```python
def test_note_create_strips_the_title_and_defaults_the_content() -> None:
    body = NoteCreate(title="  Plan  ")

    assert body.title == "Plan"
    assert body.content == ""


@pytest.mark.parametrize("title", ["", "   ", "\n\t", "x" * (TITLE_MAX_LENGTH + 1)])
def test_note_create_rejects_an_empty_or_over_long_title(title: str) -> None:
    with pytest.raises(ValidationError):
        NoteCreate(title=title)


def test_note_create_accepts_a_title_at_the_maximum_length_after_stripping() -> None:
    body = NoteCreate(title=" " + "x" * TITLE_MAX_LENGTH + " ")

    assert len(body.title) == TITLE_MAX_LENGTH


def test_note_create_rejects_over_long_content() -> None:
    with pytest.raises(ValidationError):
        NoteCreate(title="Plan", content="x" * (CONTENT_MAX_LENGTH + 1))


def test_note_update_requires_both_fields() -> None:
    with pytest.raises(ValidationError):
        NoteUpdate.model_validate({"title": "Plan"})
    with pytest.raises(ValidationError):
        NoteUpdate.model_validate({"content": "text"})


def test_note_update_strips_the_title() -> None:
    body = NoteUpdate(title=" Plan ", content="text")

    assert body.title == "Plan"
```

Check: `cd backend && uv run pytest tests/unit/test_schemas.py` passes; `uv run mypy` and
`uv run ruff check .` are clean.

---

### Task 2: The notes router, fixtures and endpoint tests

**Files:**
- Create: `backend/app/routers/notes.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/integration/conftest.py`
- Create: `backend/tests/integration/test_notes.py`

- [ ] **Step 1: The router**

Authorisation is at the router, so every route under `/notes` needs a signed-in user before its
handler runs. Update and delete check the row's author against that user. Each error branch logs.

`backend/app/routers/notes.py`:

```python
"""Notes: readable by every user, changed only by their author.

``get_current_user`` is declared on the router, so a route added here later cannot skip it.
Handlers that need the user also declare ``CurrentUserDep``; FastAPI resolves the dependency once
per request.

404 comes before the author check on purpose: every user may read every note, so telling a
non-author that a note exists reveals nothing.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentUserDep, get_current_user
from app.database import SessionDep
from app.models import Note, User
from app.pagination import DEFAULT_LIMIT, LimitQuery, OffsetQuery
from app.schemas.note import NoteCreate, NoteRead, NoteUpdate

logger = logging.getLogger("taskmind.notes")

router = APIRouter(prefix="/notes", tags=["notes"], dependencies=[Depends(get_current_user)])


def _load(db: Session, note_id: int) -> Note:
    note = db.get(Note, note_id)
    if note is None:
        logger.info("note not found", extra={"fields": {"note_id": note_id}})
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    return note


def _load_for_author(db: Session, note_id: int, user: User) -> Note:
    """The note, only if ``user`` wrote it: checked against the token's user, never the request."""
    note = _load(db, note_id)
    if note.author_id != user.id:
        logger.warning(
            "note change refused",
            extra={"fields": {"note_id": note_id, "user_id": user.id, "author_id": note.author_id}},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Only the author may change this note"
        )
    return note


@router.get("")
def list_notes(
    db: SessionDep, limit: LimitQuery = DEFAULT_LIMIT, offset: OffsetQuery = 0
) -> list[NoteRead]:
    """Every user's notes, newest first.

    ``ix_notes_created_at`` serves the sort. ``id`` breaks ties: rows written in one transaction
    share a ``now()`` timestamp, and a page must not shuffle between requests.
    """
    notes = db.scalars(
        select(Note).order_by(Note.created_at.desc(), Note.id.desc()).limit(limit).offset(offset)
    ).all()
    return [NoteRead.model_validate(note) for note in notes]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_note(body: NoteCreate, user: CurrentUserDep, db: SessionDep) -> NoteRead:
    note = Note(author_id=user.id, title=body.title, content=body.content)
    db.add(note)
    db.commit()
    db.refresh(note)
    logger.info("note created", extra={"fields": {"note_id": note.id, "user_id": user.id}})
    return NoteRead.model_validate(note)


@router.get("/{note_id}")
def read_note(note_id: int, db: SessionDep) -> NoteRead:
    return NoteRead.model_validate(_load(db, note_id))


@router.put("/{note_id}")
def update_note(note_id: int, body: NoteUpdate, user: CurrentUserDep, db: SessionDep) -> NoteRead:
    note = _load_for_author(db, note_id, user)
    note.title = body.title
    note.content = body.content
    db.commit()
    db.refresh(note)
    logger.info("note updated", extra={"fields": {"note_id": note.id, "user_id": user.id}})
    return NoteRead.model_validate(note)


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(note_id: int, user: CurrentUserDep, db: SessionDep) -> None:
    """Deletes the note and, through ``ON DELETE CASCADE``, its chats and their messages."""
    note = _load_for_author(db, note_id, user)
    db.delete(note)
    db.commit()
    logger.info("note deleted", extra={"fields": {"note_id": note_id, "user_id": user.id}})
```

- [ ] **Step 2: Include the router**

In `backend/app/main.py`, change the routers import and add the include, so the two lines read:

```python
from app.routers import auth, notes
```

and, after `application.include_router(auth.router)`:

```python
    application.include_router(notes.router)
```

- [ ] **Step 3: Signed-in user fixtures**

Append to `backend/tests/integration/conftest.py`. Add `from dataclasses import dataclass` to the
imports, between `from collections.abc import Iterator` and `from pathlib import Path`.

```python


PASSWORD = "correct horse battery"


@dataclass(frozen=True)
class SignedInUser:
    """A registered user and the ``Authorization`` header a request sends to act as them."""

    id: int
    email: str
    headers: dict[str, str]


def sign_in(client: TestClient, email: str) -> SignedInUser:
    """Register ``email`` through the API and log in, so the token is one the app issued."""
    registered = client.post("/auth/register", json={"email": email, "password": PASSWORD})
    assert registered.status_code == 201, registered.text
    login = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    return SignedInUser(
        id=registered.json()["id"], email=email, headers={"Authorization": f"Bearer {token}"}
    )


@pytest.fixture
def user(client: TestClient) -> SignedInUser:
    return sign_in(client, "ada@example.com")


@pytest.fixture
def second_user(client: TestClient) -> SignedInUser:
    """Another signed-in user, for the cases where the caller is not the author."""
    return sign_in(client, "grace@example.com")
```

- [ ] **Step 4: Endpoint tests**

`backend/tests/integration/test_notes.py`:

```python
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
```

Check: `cd backend && uv run pytest tests/integration/test_notes.py` passes against the Compose
test database; the Validate command is clean; `uv run pytest tests/unit` still passes (the unit
suite imports `app.main`, which now includes the router).

---

### Task 3: README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: A Notes subsection**

Insert after the "Signing in" subsection (after the line
"Tokens last `JWT_EXPIRE_MINUTES` (default 60). On `/docs`, the Authorize button takes the token.")
and before "### Changing the schema":

````markdown
### Notes

Every signed-in user sees every note; only the author can change or delete one.

```bash
TOKEN=<access_token>
curl -s -X POST localhost:8000/notes -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"title": "Plan", "content": "Ship the notes API"}'
curl -s 'localhost:8000/notes?limit=10&offset=0' -H "Authorization: Bearer $TOKEN"
curl -s localhost:8000/notes/1 -H "Authorization: Bearer $TOKEN"
curl -s -X PUT localhost:8000/notes/1 -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"title": "Plan", "content": "Shipped"}'
curl -s -X DELETE localhost:8000/notes/1 -H "Authorization: Bearer $TOKEN" -o /dev/null -w '%{http_code}\n'
```

`limit` is 1 to 100 (default 50). Changing someone else's note is a 403; a missing note is a 404.
````

Check: the README renders with a single bash fence inside the new subsection.

---

## Gaps against HD policy, recorded on purpose

- None new. The spec's recorded gap (no Phoenix tracing) is unchanged; nothing here calls out.

## Documentation Notes

- How the five routes are observed (where output goes, what can be asked, what failing looks like) → **PR**, per `observability.md` rule 9: JSON lines on `taskmind.notes` and the per-request line on `taskmind.request`; `docker compose logs backend` once PR 6 adds the service; a 403 or 404 line with `note_id`, or a 5xx on the request line.
- `content` is capped at 20,000 characters, which the spec did not state → **PR**, and **decision**: add the cap to the spec's Schemas paragraph when the spec is next revised.
- The branch is stacked on `feat/auth` and the PR targets it until PR 3 merges → **PR**.
- `limit`/`offset` live in `app/pagination.py`, shared by every list endpoint → **AGENTS.md** Architecture & Structure, new: the spec's layout does not list the module.
- 404 before 403 on update and delete, and why → **code** `app/routers/notes.py` docstring (written in Task 2).
- `id` as the tiebreaker on the list sort, and why → **code** `app/routers/notes.py` `list_notes` docstring (written in Task 2).
