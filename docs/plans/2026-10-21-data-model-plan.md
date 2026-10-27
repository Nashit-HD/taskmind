# Data Model and Initial Migration Implementation Plan

> **For agentic workers:** Use `/explain-plan` to preview all tasks, then `/execute-plan` to implement task-by-task.

**Goal:** Add the database layer: the SQLAlchemy models for users, notes, chats and messages, the session dependency, and the first Alembic migration that creates and can drop the schema, proven by tests that run the real migration against the test database.

**Spec:** `docs/plans/2026-10-20-backend-design.md` § Data model and § Delivery item 2. Terms per `GLOSSARY.md`; decisions per `docs/adr/0001` to `0003`.

**Affected components:** backend — `backend/`; README at the repo root

**Change class:** structural — a migration and a dependency added. Decision record: the spec's Decisions table and ADRs 0001 to 0003.

**Branch:** cut `feat/data-model` from `main` once PR 1 has merged. Nothing here is built before that.

| Revision | Closed | Sections changed |
|---|---|---|
| r2 | N1, N2, N3 | Task 1 (Ruff isort config), Task 2 (`path_separator` in `alembic.ini`, two assertions in `test_migrations.py`) |
| r3 | execution | mypy `files` gains `alembic` in Task 2, not Task 1, because the directory does not exist until then; Task 2 Step 11 builds on the merged `conftest.py` |

---

## Policy answers, checked

The spec's answers hold. What this PR carries, and what it does not:

- **Entry points:** none. No route reads or writes data yet, so no authorisation check is added. The
  one behavioural change to the app is an exception handler: a database connection failure becomes a
  503 with a generic body, logged with its trace.
- **Data:** four tables, exactly the spec's columns. `users.email` is unique on the stored value; the
  auth schema in PR 3 lower-cases it before it gets here. No personal data beyond the email.
- **Access patterns and indexes:** no queries yet. The three indexes the spec names are created now,
  with the queries in PRs 4 and 5 in mind: `notes(created_at)`, `chats(note_id, user_id, updated_at)`
  and `messages(chat_id, created_at)`. Chat ordering is per user and per note because chats are
  private (ADR 0003).
- **Cascade:** `notes → chats → messages` cascade in the database with `ON DELETE CASCADE`. The ORM
  relationships use `passive_deletes=True` so SQLAlchemy relies on the database rather than loading
  children to delete them one by one.
- **Migration reverse:** `downgrade()` drops the four tables in dependency order. A test runs
  downgrade and upgrade both ways.
- **Dependency failure:** the engine has `pool_pre_ping=True` and a 5-second connect timeout. A
  connection failure on any future route becomes 503 `{"detail": "Database unavailable"}` and an
  `error` log line with the trace and the request id.
- **Observability:** the 503 handler logs before responding. Alembic's own console logging stays as
  the tool ships it: it is operator-facing CLI output, which the observability policy exempts.
- **Testing:** integration tests build the schema with the real migration on `TEST_DATABASE_URL`,
  through a connection passed to Alembic, so the development database is never touched. Each test
  runs in a transaction that is rolled back. One test runs `alembic check` so the migration and the
  models cannot drift. A unit test covers the 503 handler without a database.

Two details the spec leaves open, settled here:

- `messages.role` is a `varchar(16)` with a check constraint allowing `user` and `assistant`, and a
  `MessageRole` string enum in Python for code that writes it. A native Postgres enum would need its
  own migration to change later.
- `updated_at` uses the database's `now()`, which in Postgres is the transaction start time. Every
  request is its own transaction, so it moves per request, which is what "most recently updated"
  needs.

## Files

| File | Job |
|---|---|
| `backend/pyproject.toml`, `backend/uv.lock` | Add Alembic; type-check the `alembic/` directory |
| `backend/app/database.py` | Engine, `Base` with a naming convention, `SessionLocal`, `get_db`, `SessionDep` |
| `backend/app/main.py` | The `OperationalError` → 503 handler |
| `backend/tests/unit/test_database_errors.py` | The handler's response and log line |
| `backend/app/models/__init__.py` | Imports every model so `Base.metadata` is complete for Alembic |
| `backend/app/models/user.py`, `note.py`, `chat.py`, `message.py` | One table each |
| `backend/alembic.ini` | Alembic config; no URL in it |
| `backend/alembic/env.py` | Reads the URL from `Settings`, or uses a connection the caller passes |
| `backend/alembic/script.py.mako` | Template for future revisions, typed |
| `backend/alembic/versions/0001_create_users_notes_chats_messages.py` | The schema, up and down |
| `backend/tests/integration/conftest.py` | Migrated engine and a rolled-back session per test |
| `backend/tests/integration/test_migrations.py` | Up, down, up again; models and migration agree |
| `backend/tests/integration/test_models.py` | Constraints, cascades, defaults, `updated_at` |
| `README.md` | Migration step before running the API; how to add a migration |

---

### Task 1: Database module, session dependency and the 503 handler

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/uv.lock` (generated)
- Create: `backend/app/database.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/unit/test_database_errors.py`

- [ ] **Step 1: Add Alembic**

In `backend/pyproject.toml`, change the runtime dependencies:

```toml
dependencies = [
    "fastapi[standard]>=0.156.4",
    "pydantic-settings>=2.16.1",
    "sqlalchemy>=2.1.5",
    "psycopg[binary]>=3.3.6",
    "alembic>=1.20.0",
]
```

Add, after `[tool.ruff.lint]`:

```toml
[tool.ruff.lint.isort]
# The migrations directory is also called "alembic", so Ruff would otherwise sort the
# alembic package as first-party.
known-third-party = ["alembic"]
```

Then from `backend/`:

```bash
uv lock
uv sync --locked
```

- [ ] **Step 2: The database module**

`backend/app/database.py`:

```python
"""Engine, declarative base, session factory and the per-request session dependency.

``Base.metadata`` carries a naming convention so every index, unique, check and foreign-key
constraint gets a predictable name. A migration can then drop a constraint by name, and
``alembic check`` can compare the models with the database without guessing names.
"""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


engine = create_engine(
    get_settings().database_url,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 5},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """One session per request, closed when the request ends. Handlers commit what they change."""
    with SessionLocal() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_db)]
```

`expire_on_commit=False` keeps a committed row usable for the response without a reload. The
engine is created at import time from `Settings`, so `DATABASE_URL` must be set wherever `app`
is imported; the test `conftest.py` already defaults it to the test database.

- [ ] **Step 3: The 503 handler**

`backend/app/main.py` becomes:

```python
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
```

`OperationalError` is what psycopg raises when it cannot connect or loses the connection. The
handler takes `exc: Exception` because that is the type Starlette's handler signature declares.

- [ ] **Step 4: Unit test for the handler**

`backend/tests/unit/test_database_errors.py`:

```python
import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.logging import REQUEST_ID_HEADER
from app.main import create_app


def _app_whose_route_loses_the_database() -> FastAPI:
    failing = create_app()

    @failing.get("/needs-db")
    def needs_db() -> None:
        raise OperationalError("SELECT 1", {}, ConnectionRefusedError("connection refused"))

    return failing


def test_a_database_connection_failure_returns_503_with_a_generic_body(
    caplog: pytest.LogCaptureFixture,
) -> None:
    failing = _app_whose_route_loses_the_database()
    with (
        caplog.at_level(logging.ERROR, logger="taskmind.database"),
        TestClient(failing, raise_server_exceptions=False) as client,
    ):
        response = client.get("/needs-db", headers={REQUEST_ID_HEADER: "db-down"})

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
    assert "refused" not in response.text
    assert response.headers[REQUEST_ID_HEADER] == "db-down"


def test_a_database_connection_failure_is_logged_with_its_trace(
    caplog: pytest.LogCaptureFixture,
) -> None:
    failing = _app_whose_route_loses_the_database()
    with (
        caplog.at_level(logging.ERROR, logger="taskmind.database"),
        TestClient(failing, raise_server_exceptions=False) as client,
    ):
        client.get("/needs-db")

    errors = [r for r in caplog.records if r.name == "taskmind.database"]
    assert len(errors) == 1
    assert errors[0].levelno == logging.ERROR
    assert errors[0].exc_info is not None
    assert errors[0].__dict__["fields"]["path"] == "/needs-db"
```

- [ ] **Step 5: Run the gate**

From `backend/`:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest tests/unit
```

Expected: 15 unit tests pass, mypy clean.

---

### Task 2: Models, the initial migration, and the tests that prove them

**Files:**
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/user.py`
- Create: `backend/app/models/note.py`
- Create: `backend/app/models/chat.py`
- Create: `backend/app/models/message.py`
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`
- Create: `backend/alembic/versions/0001_create_users_notes_chats_messages.py`
- Modify: `backend/tests/integration/conftest.py`
- Create: `backend/tests/integration/test_migrations.py`
- Create: `backend/tests/integration/test_models.py`

- [ ] **Step 1: User**

`backend/app/models/user.py`:

```python
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    """A person who has signed in.

    ``email`` is unique on the stored value. The auth schema lower-cases it before it gets here, so
    two spellings of one address cannot both register.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 2: Note**

`backend/app/models/note.py`:

```python
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.chat import Chat


class Note(Base):
    """A titled piece of text written by its author and readable by every user.

    Deleting a note deletes its chats, and through them their messages, in the database
    (``ON DELETE CASCADE``). ``passive_deletes=True`` tells SQLAlchemy to rely on that rather than
    load the chats to delete them itself.
    """

    __tablename__ = "notes"
    __table_args__ = (Index("ix_notes_created_at", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text, server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    chats: Mapped[list[Chat]] = relationship(cascade="all, delete-orphan", passive_deletes=True)
```

- [ ] **Step 3: Chat**

`backend/app/models/chat.py`:

```python
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.message import Message


class Chat(Base):
    """A private series of messages between one user and the assistant about exactly one note.

    ``user_id`` is the user the chat belongs to; nobody else can see it (ADR 0003). The index
    serves "this user's chats on this note, most recently updated first".
    """

    __tablename__ = "chats"
    __table_args__ = (
        Index("ix_chats_note_id_user_id_updated_at", "note_id", "user_id", "updated_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    note_id: Mapped[int] = mapped_column(ForeignKey("notes.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    messages: Mapped[list[Message]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, order_by="Message.created_at"
    )
```

- [ ] **Step 4: Message**

`backend/app/models/message.py`:

```python
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class Message(Base):
    """One entry in a chat, written by the user or the assistant. Once stored it never changes.

    ``role`` is a plain string column with a check constraint rather than a Postgres enum, so
    adding a role later is a one-line migration instead of an enum alteration.
    """

    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')", name="role"),
        Index("ix_messages_chat_id_created_at", "chat_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

The check constraint's name becomes `ck_messages_role` through the naming convention.

- [ ] **Step 5: The models package**

`backend/app/models/__init__.py`:

```python
"""SQLAlchemy models.

Importing this package imports every model, which registers every table on ``Base.metadata``.
Alembic's ``env.py`` imports it for that reason: a model missing here is a table Alembic cannot
see, and ``alembic check`` would report the drift.
"""

from app.models.chat import Chat
from app.models.message import Message, MessageRole
from app.models.note import Note
from app.models.user import User

__all__ = ["Chat", "Message", "MessageRole", "Note", "User"]
```

- [ ] **Step 6: Type-check the migrations directory**

Now that `backend/alembic/` exists, add it to mypy's `files` in `backend/pyproject.toml`:

```toml
[tool.mypy]
strict = true
python_version = "3.13"
files = ["app", "alembic", "tests"]
plugins = ["pydantic.mypy"]
```

- [ ] **Step 7: Alembic configuration**

`backend/alembic.ini`:

```ini
# Alembic configuration. The database URL is not here: alembic/env.py reads it from the
# application's Settings (DATABASE_URL), or uses a connection the caller passes in.

[alembic]
script_location = %(here)s/alembic
prepend_sys_path = %(here)s
path_separator = os

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARNING
handlers = console
qualname =

[logger_sqlalchemy]
level = WARNING
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

`%(here)s` is the directory holding `alembic.ini`, so the commands work from any directory and
inside the container.

- [ ] **Step 8: The environment**

`backend/alembic/env.py`:

```python
"""Alembic environment.

The database URL comes from the application's ``Settings``, so ``alembic.ini`` carries none and
there is one place a URL is configured. A caller may instead pass an open connection through
``config.attributes["connection"]``; the test suite does this to migrate the test database on its
own engine, so a developer's ``DATABASE_URL`` is never migrated by a test run.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection, create_engine

import app.models  # noqa: F401  registers every table on Base.metadata
from app.config import get_settings
from app.database import Base

config = context.config

if config.config_file_name is not None:
    # disable_existing_loggers defaults to True, which would silence every logger created before
    # this point, including the app's own when the migrations run inside the test process.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of running it. Used for `alembic upgrade head --sql`."""
    context.configure(
        url=get_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _run_on(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    supplied: Connection | None = config.attributes.get("connection")
    if supplied is not None:
        _run_on(supplied)
        return
    engine = create_engine(get_settings().database_url, connect_args={"connect_timeout": 5})
    with engine.connect() as connection:
        _run_on(connection)
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 9: The revision template**

`backend/alembic/script.py.mako`:

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: str | None = ${repr(down_revision)}
branch_labels: str | Sequence[str] | None = ${repr(branch_labels)}
depends_on: str | Sequence[str] | None = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 10: The migration**

`backend/alembic/versions/0001_create_users_notes_chats_messages.py`:

```python
"""create users, notes, chats and messages

Revision ID: 0001
Revises:
Create Date: 2026-10-21

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    op.create_table(
        "notes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content", sa.Text(), server_default="", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], name="fk_notes_author_id_users"),
        sa.PrimaryKeyConstraint("id", name="pk_notes"),
    )
    op.create_index("ix_notes_created_at", "notes", ["created_at"])

    op.create_table(
        "chats",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("note_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["note_id"], ["notes.id"], name="fk_chats_note_id_notes", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_chats_user_id_users"),
        sa.PrimaryKeyConstraint("id", name="pk_chats"),
    )
    op.create_index(
        "ix_chats_note_id_user_id_updated_at", "chats", ["note_id", "user_id", "updated_at"]
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("chat_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="ck_messages_role"),
        sa.ForeignKeyConstraint(
            ["chat_id"], ["chats.id"], name="fk_messages_chat_id_chats", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_messages"),
    )
    op.create_index("ix_messages_chat_id_created_at", "messages", ["chat_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_messages_chat_id_created_at", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ix_chats_note_id_user_id_updated_at", table_name="chats")
    op.drop_table("chats")
    op.drop_index("ix_notes_created_at", table_name="notes")
    op.drop_table("notes")
    op.drop_table("users")
```

Written by hand rather than autogenerated so every name and `ondelete` is deliberate. The test in
Step 12 runs `alembic check`, which fails if this file and the models disagree.

- [ ] **Step 11: Integration fixtures**

`backend/tests/integration/conftest.py` becomes:

```python
"""Fixtures that need the test database.

``TEST_DATABASE_URL`` must point at a database the suite may own. Locally that is ``taskmind_test``
on the Compose Postgres; in CI it is the service container. The schema is built by the real
migrations, through a connection handed to Alembic, so the development database is never touched.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

BACKEND_DIR = Path(__file__).resolve().parents[2]


def upgrade_to_head(engine: Engine, alembic_config: Config) -> None:
    with engine.begin() as connection:
        alembic_config.attributes["connection"] = connection
        command.upgrade(alembic_config, "head")


def downgrade_to_base(engine: Engine, alembic_config: Config) -> None:
    with engine.begin() as connection:
        alembic_config.attributes["connection"] = connection
        command.downgrade(alembic_config, "base")


@pytest.fixture(scope="session")
def engine() -> Engine:
    return create_engine(
        os.environ["TEST_DATABASE_URL"],
        pool_pre_ping=True,
        connect_args={"connect_timeout": 5},
    )


@pytest.fixture(scope="session")
def alembic_config() -> Config:
    return Config(str(BACKEND_DIR / "alembic.ini"))


@pytest.fixture(scope="session")
def migrated_engine(engine: Engine, alembic_config: Config) -> Engine:
    """A clean schema at the head revision, rebuilt by the migrations at the start of every run."""
    downgrade_to_base(engine, alembic_config)
    upgrade_to_head(engine, alembic_config)
    return engine


@pytest.fixture
def db_session(migrated_engine: Engine) -> Iterator[Session]:
    """A session inside a transaction that is rolled back after the test.

    ``join_transaction_mode="create_savepoint"`` lets code under test call ``commit()`` without
    ending the outer transaction, so tests never see each other's rows.
    """
    with migrated_engine.connect() as connection:
        transaction = connection.begin()
        with Session(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        ) as session:
            yield session
        transaction.rollback()
```

- [ ] **Step 12: Migration tests**

`backend/tests/integration/test_migrations.py`:

```python
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect

from tests.integration.conftest import downgrade_to_base, upgrade_to_head

TABLES = {"users", "notes", "chats", "messages"}


def _tables(engine: Engine) -> set[str]:
    return set(inspect(engine).get_table_names())


def test_upgrade_to_head_creates_the_four_tables(migrated_engine: Engine) -> None:
    assert _tables(migrated_engine) >= TABLES


def test_downgrade_removes_the_tables_and_upgrade_restores_them(
    migrated_engine: Engine, alembic_config: Config
) -> None:
    downgrade_to_base(migrated_engine, alembic_config)
    assert not TABLES & _tables(migrated_engine)

    upgrade_to_head(migrated_engine, alembic_config)
    assert _tables(migrated_engine) >= TABLES


def test_the_migration_and_the_models_agree(
    migrated_engine: Engine, alembic_config: Config
) -> None:
    """``alembic check`` raises when autogenerate would add anything, so drift fails the suite."""
    with migrated_engine.begin() as connection:
        alembic_config.attributes["connection"] = connection
        command.check(alembic_config)


def test_the_cascades_are_declared_in_the_database(migrated_engine: Engine) -> None:
    inspector = inspect(migrated_engine)
    chat_fks = {fk["name"]: fk for fk in inspector.get_foreign_keys("chats")}
    message_fks = {fk["name"]: fk for fk in inspector.get_foreign_keys("messages")}

    assert chat_fks["fk_chats_note_id_notes"]["options"] == {"ondelete": "CASCADE"}
    assert message_fks["fk_messages_chat_id_chats"]["options"] == {"ondelete": "CASCADE"}
```

- [ ] **Step 13: Model tests**

`backend/tests/integration/test_models.py`:

```python
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Chat, Message, MessageRole, Note, User


def _user(db_session: Session, email: str = "ada@example.com") -> User:
    user = User(email=email, password_hash="not-a-real-hash")
    db_session.add(user)
    db_session.flush()
    return user


def _note(db_session: Session, author: User, title: str = "Plan") -> Note:
    note = Note(author_id=author.id, title=title, content="text")
    db_session.add(note)
    db_session.flush()
    return note


def _chat(db_session: Session, note: Note, user: User) -> Chat:
    chat = Chat(note_id=note.id, user_id=user.id, title="Questions")
    db_session.add(chat)
    db_session.flush()
    return chat


def _count(db_session: Session, model: type[Chat] | type[Message] | type[Note]) -> int:
    return db_session.scalar(select(func.count()).select_from(model)) or 0


def test_timestamps_are_set_by_the_database_in_utc(db_session: Session) -> None:
    user = _user(db_session)
    db_session.refresh(user)

    assert user.created_at.tzinfo is not None
    assert user.created_at.utcoffset() is not None


def test_email_must_be_unique(db_session: Session) -> None:
    _user(db_session, "same@example.com")

    with pytest.raises(IntegrityError):
        _user(db_session, "same@example.com")


def test_note_content_defaults_to_empty(db_session: Session) -> None:
    author = _user(db_session)
    note = Note(author_id=author.id, title="Untitled")
    db_session.add(note)
    db_session.flush()
    db_session.refresh(note)

    assert note.content == ""


def test_updated_at_moves_when_a_note_changes(db_session: Session) -> None:
    author = _user(db_session)
    note = _note(db_session, author)
    long_ago = datetime(2000, 1, 1, tzinfo=UTC)
    db_session.execute(update(Note).where(Note.id == note.id).values(updated_at=long_ago))
    db_session.refresh(note)
    assert note.updated_at == long_ago

    note.title = "Renamed"
    db_session.flush()
    db_session.refresh(note)

    assert note.updated_at > long_ago


def test_deleting_a_note_removes_its_chats_and_messages(db_session: Session) -> None:
    user = _user(db_session)
    note = _note(db_session, user)
    chat = _chat(db_session, note, user)
    db_session.add(Message(chat_id=chat.id, role=MessageRole.USER, content="hi"))
    db_session.flush()

    db_session.execute(delete(Note).where(Note.id == note.id))

    assert _count(db_session, Chat) == 0
    assert _count(db_session, Message) == 0


def test_deleting_a_chat_removes_its_messages_but_not_the_note(db_session: Session) -> None:
    user = _user(db_session)
    note = _note(db_session, user)
    chat = _chat(db_session, note, user)
    db_session.add(Message(chat_id=chat.id, role=MessageRole.ASSISTANT, content="hello"))
    db_session.flush()

    db_session.execute(delete(Chat).where(Chat.id == chat.id))

    assert _count(db_session, Message) == 0
    assert _count(db_session, Note) == 1


def test_a_message_role_outside_user_and_assistant_is_rejected(db_session: Session) -> None:
    user = _user(db_session)
    chat = _chat(db_session, _note(db_session, user), user)
    db_session.add(Message(chat_id=chat.id, role="bot", content="beep"))

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_a_note_needs_an_existing_author(db_session: Session) -> None:
    db_session.add(Note(author_id=999_999, title="Orphan"))

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_each_test_starts_with_an_empty_database(db_session: Session) -> None:
    """Depends on the rollback in the db_session fixture; fails if a previous test leaked rows."""
    assert _count(db_session, Note) == 0
    assert db_session.scalar(select(func.count()).select_from(User)) == 0
```

- [ ] **Step 14: Run everything**

From `backend/`, with `docker compose up -d db` running and the root `.env` loaded:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest
uv run alembic upgrade head
uv run alembic check
```

Expected: all tests pass, including the three migration tests and nine model tests; the manual
`upgrade head` migrates the development database; `alembic check` prints
"No new upgrade operations detected."

---

### Task 3: README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Migration step and how to add one**

Replace the "Running the backend locally" section with:

````markdown
## Running the backend locally

```bash
cd backend
uv run alembic upgrade head    # create or update the tables
uv run fastapi dev
```

The API is at http://localhost:8000 and the OpenAPI docs at http://localhost:8000/docs.

### Changing the schema

Edit the models under `backend/app/models/`, then:

```bash
cd backend
uv run alembic revision --autogenerate -m "what changed"
```

Read the generated file under `backend/alembic/versions/`, check the names and `ondelete` rules,
and make sure `downgrade()` reverses `upgrade()`. Then `uv run alembic upgrade head`. The test
suite runs `alembic check`, so a model change without a migration fails CI.
````

And in "Running the tests", replace the integration line with:

```markdown
uv run pytest tests/integration          # needs `docker compose up -d db`; rebuilds taskmind_test from the migrations
```

---

## Documentation Notes

- Migration commands (`uv run alembic upgrade head`, `uv run alembic revision --autogenerate -m`) → **AGENTS.md** Key Commands, new: no migration tooling existed before this plan.
- The integration suite downgrades `taskmind_test` to base and re-upgrades at the start of every run; a schema created by hand, without an `alembic_version` row, breaks that → **AGENTS.md** Quirks & Gotchas, new, with the fix `docker compose down -v && docker compose up -d db`.
- `app/models/__init__.py` must import every model so Alembic sees it → **code** `app/models/__init__.py` docstring (written in Task 2).
- Constraint and index names come from the naming convention on `Base.metadata`; a migration uses those names → **code** `app/database.py` docstring (written in Task 1).
- `updated_at` is the transaction's `now()`, so it changes per request, not per statement → **code** docstring on `Note.updated_at` is not possible on a column; recorded in this plan's Policy answers and in **AGENTS.md** Quirks & Gotchas, new.
