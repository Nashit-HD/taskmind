# OpenAI Assistant Implementation Plan

> **For agentic workers:** Use `/explain-plan` to preview all tasks, then `/execute-plan` to implement task-by-task.

**Goal:** Replace the echo with an assistant that answers from the note's content through OpenAI, with a timeout, bounded retries, call-site logging, and the echo kept as the fallback when no key is configured.

**Spec:** `docs/plans/2026-10-20-backend-design.md` § Decisions (Assistant down, Assistant grounding), § Configuration (`OPENAI_API_KEY`, `OPENAI_MODEL`), § Policy answers (Dependency failure, Observability), § Testing design (`test_assistant.py`). PR 5 built the seam this fills.

**Affected components:** backend — `backend/`; `docker-compose.yml`, `.env.example`, README and `AGENTS.md` at the repo root

**Change class:** structural — a new dependency (`openai`), a new outbound call, two new settings. Elevated per `review.md` § Overrides: crosses a process boundary (reliability and observability lenses), secrets handling (security), config variables and a manifest (devops).

**Branch:** `feat/openai-assistant`, cut from `feat/docker-backend`; the PR targets `feat/docker-backend` until PR 6 (#7) merges.

---

## Policy answers, checked

- **Model.** `gpt-6-luna`, the model OpenAI's models page (read 2026-10-29) recommends for
  cost-sensitive, high-volume work. It is the default of `OPENAI_MODEL`, so it changes without a
  code change. SDK `openai` 3.41.0, added to `pyproject.toml` and `uv.lock`.
- **Secret.** `OPENAI_API_KEY` arrives from the environment as a `SecretStr | None`; an empty
  value means unset, so Compose can pass `${OPENAI_API_KEY:-}` without breaking. It is read in one
  place, when the client is built, and never logged (`security.md` rules 14, 15).
- **Fallback when unset.** No key means the `EchoAssistant` answers, with one warning line at
  first use. A reviewer without a key can still run the whole app; the README says what they will
  see. Tests unset the key in `tests/conftest.py`, so a developer's real key is never called by a
  test (`testing.md` rule 10: the boundary is the dependency, overridden or defaulted).
- **Outbound call.** One `responses.create` per message. Timeout 30 s, at most 2 retries, both
  passed explicitly to the client; the SDK retries connection errors, 408, 409, 429 and 5xx only,
  and only requests it can resend, which this one is (`reliability.md` rules 5, 6). Every SDK
  error inherits `openai.APIError`, which the assistant turns into `AssistantError`; the router
  already answers 502 with nothing written (`reliability.md` rule 7; the failure breaks only
  `POST /chats/{id}/messages`). An empty reply is also an `AssistantError`: the chat must never
  store an empty assistant message.
- **Grounding.** The instructions carry the note's title and content and say: answer only from
  the note, say plainly when it does not cover the question, no outside knowledge. The input is the
  last 20 messages (bounded by the router in PR 5) plus the question. Roles are mapped to the
  SDK's literal roles, never passed through from storage (`security.md` rule 12 in spirit: typed
  at the boundary).
- **Observability.** Each call logs on `taskmind.assistant`: `model`, `latency_ms`,
  `input_tokens`, `output_tokens` on success; `model`, `latency_ms`, the error class and the
  exception on failure. Never the prompt, the note or the reply (`observability.md` rules 3, 13,
  14). OpenInference tracing to Phoenix stays the recorded gap (rule 11).
- **Selection is cached.** `build_assistant()` is `lru_cache`d like `get_settings()`, so one
  client per process; a test that changes the environment clears both caches.
- **Testing.** Unit, no network: instructions and input building; a real `OpenAI` client with
  `responses.create` monkeypatched to return a stub or raise `APIConnectionError`; selection with
  and without a key; the empty-key-is-None setting. Integration tests keep the echo.
- **No live call in this PR's evidence.** The developer's `.env` has no key, so the SDK path is
  proven against the patched client only; the shape of the call matches the SDK README read today.

## Files

| File | Job |
|---|---|
| `backend/pyproject.toml`, `backend/uv.lock` | `openai` dependency (already added with `uv add openai`) |
| `backend/app/config.py` | `openai_api_key`, `openai_model` |
| `backend/app/assistant.py` | Prompt building, `OpenAIAssistant`, `build_assistant`, the switch in `get_assistant` |
| `backend/tests/conftest.py` | Unset `OPENAI_API_KEY` for the test process |
| `backend/tests/unit/test_assistant.py` | The new tests |
| `backend/tests/unit/test_settings.py` | Empty key is None |
| `.env.example`, `docker-compose.yml` | The two variables |
| `README.md`, `AGENTS.md` | How to turn the real assistant on; the cache quirk |

---

### Task 1: Settings and the OpenAI assistant

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/app/assistant.py`
- Modify: `backend/tests/conftest.py`
- Modify: `backend/tests/unit/test_settings.py`
- Modify: `backend/tests/unit/test_assistant.py`

- [ ] **Step 1: Settings**

In `backend/app/config.py`, after `jwt_expire_minutes: int = 60` add:

```python
    # Empty means unset: the echo assistant answers. Read once, when the client is built.
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-6-luna"
```

and after the `cors_origin_list` property add:

```python
    @field_validator("openai_api_key", mode="before")
    @classmethod
    def _empty_key_is_none(cls, value: object) -> object:
        return None if value == "" else value
```

- [ ] **Step 2: The assistant module**

`backend/app/assistant.py` becomes:

```python
"""The assistant, behind one seam.

The assistant is the one thing in the backend that leaves the process. Routers never call a
provider directly: they declare ``AssistantDep`` and call ``reply``. Tests override
``get_assistant`` with a fake.

``build_assistant`` picks the implementation once per process: ``OpenAIAssistant`` when
``OPENAI_API_KEY`` is set, otherwise ``EchoAssistant``, which quotes the question back so the
whole chat flow works with no network and no key.
"""

import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated, Protocol

from fastapi import Depends
from openai import APIError, OpenAI
from openai.types.responses import ResponseInputParam

from app.config import get_settings

logger = logging.getLogger("taskmind.assistant")

# How many earlier messages the assistant is shown. Bounds the payload per the spec.
HISTORY_LIMIT = 20
# One call per message; the user is waiting on it, so it is bounded. The SDK retries connection
# errors, 408, 409, 429 and 5xx only, and only requests it can safely resend.
OPENAI_TIMEOUT_SECONDS = 30.0
OPENAI_MAX_RETRIES = 2


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


def build_instructions(note: NoteContext) -> str:
    """The system instructions: the grounding rule and the one note."""
    return (
        "You are the assistant in TaskMind, a shared notebook. Answer the user's questions using "
        "only the note below. Do not use outside knowledge. If the note does not cover the "
        "question, say so plainly instead of guessing. Keep answers short.\n\n"
        f"Note title: {note.title}\n\nNote content:\n{note.content}"
    )


def build_input(history: Sequence[Turn], question: str) -> ResponseInputParam:
    """The conversation so far plus the new question, in the SDK's input shape.

    Roles are mapped, not passed through: anything that is not the assistant is the user.
    """
    turns: ResponseInputParam = [
        {"role": "assistant" if turn.role == "assistant" else "user", "content": turn.content}
        for turn in history
    ]
    turns.append({"role": "user", "content": question})
    return turns


class OpenAIAssistant:
    """Answers through the OpenAI Responses API. One call per message, logged at the call site."""

    def __init__(self, client: OpenAI, model: str) -> None:
        self._client = client
        self._model = model

    def reply(self, note: NoteContext, history: Sequence[Turn], question: str) -> str:
        started = time.perf_counter()
        try:
            response = self._client.responses.create(
                model=self._model,
                instructions=build_instructions(note),
                input=build_input(history, question),
            )
        except APIError as exc:
            logger.error(
                "openai call failed",
                extra={
                    "fields": {
                        "model": self._model,
                        "latency_ms": _elapsed_ms(started),
                        "error": type(exc).__name__,
                    }
                },
                exc_info=exc,
            )
            raise AssistantError(type(exc).__name__) from exc
        usage = response.usage
        logger.info(
            "openai call",
            extra={
                "fields": {
                    "model": self._model,
                    "latency_ms": _elapsed_ms(started),
                    "input_tokens": usage.input_tokens if usage else None,
                    "output_tokens": usage.output_tokens if usage else None,
                }
            },
        )
        text = response.output_text.strip()
        if not text:
            logger.error("openai returned no text", extra={"fields": {"model": self._model}})
            raise AssistantError("empty reply")
        return text


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 1)


@lru_cache
def build_assistant() -> Assistant:
    """One assistant per process, chosen by configuration. Tests clear this cache too."""
    settings = get_settings()
    if settings.openai_api_key is None:
        logger.warning("OPENAI_API_KEY is not set; the echo assistant answers instead of OpenAI")
        return EchoAssistant()
    client = OpenAI(
        api_key=settings.openai_api_key.get_secret_value(),
        timeout=OPENAI_TIMEOUT_SECONDS,
        max_retries=OPENAI_MAX_RETRIES,
    )
    return OpenAIAssistant(client, settings.openai_model)


def get_assistant() -> Assistant:
    return build_assistant()


AssistantDep = Annotated[Assistant, Depends(get_assistant)]
```

- [ ] **Step 3: The test process never calls OpenAI**

Append to `backend/tests/conftest.py`:

```python

# A developer's real key must never be called by a test: without one the echo answers, and the
# unit tests that cover the OpenAI path patch the client.
os.environ.pop("OPENAI_API_KEY", None)
```

- [ ] **Step 4: Settings test**

Append to `backend/tests/unit/test_settings.py`:

```python


def test_an_empty_openai_key_means_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")

    assert Settings().openai_api_key is None


def test_the_openai_key_does_not_appear_in_the_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-very-secret")

    assert "very-secret" not in repr(Settings())
```

- [ ] **Step 5: Assistant tests**

`backend/tests/unit/test_assistant.py` becomes:

```python
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import httpx2
import pytest
from openai import APIConnectionError, OpenAI

from app.assistant import (
    AssistantError,
    EchoAssistant,
    NoteContext,
    OpenAIAssistant,
    Turn,
    build_assistant,
    build_input,
    build_instructions,
    get_assistant,
)
from app.config import get_settings

NOTE = NoteContext(title="Plan", content="Ship it on Friday")


@pytest.fixture(autouse=True)
def _clear_caches() -> Iterator[None]:
    get_settings.cache_clear()
    build_assistant.cache_clear()
    yield
    get_settings.cache_clear()
    build_assistant.cache_clear()


# The echo


def test_the_echo_quotes_the_question_and_names_the_note() -> None:
    reply = EchoAssistant().reply(NOTE, [Turn("user", "earlier")], "When?")

    assert "When?" in reply
    assert "Plan" in reply
    assert "Friday" not in reply


# Prompt building


def test_instructions_carry_the_note_and_the_grounding_rule() -> None:
    instructions = build_instructions(NOTE)

    assert "Plan" in instructions
    assert "Ship it on Friday" in instructions
    assert "only the note" in instructions
    assert "does not cover" in instructions


def test_input_is_the_history_then_the_question_with_mapped_roles() -> None:
    history = [Turn("user", "Q1"), Turn("assistant", "A1"), Turn("weird", "Q2")]

    turns = build_input(history, "Q3")

    assert turns == [
        {"role": "user", "content": "Q1"},
        {"role": "assistant", "content": "A1"},
        {"role": "user", "content": "Q2"},
        {"role": "user", "content": "Q3"},
    ]


# The OpenAI path, with the client's one call replaced


@dataclass
class _Usage:
    input_tokens: int
    output_tokens: int


@dataclass
class _Response:
    output_text: str
    usage: _Usage | None


def _client() -> OpenAI:
    return OpenAI(api_key="test-key", max_retries=0)


def test_reply_sends_the_note_and_history_and_returns_the_text(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    client = _client()
    calls: list[dict[str, Any]] = []

    def fake_create(**kwargs: Any) -> _Response:
        calls.append(kwargs)
        return _Response(output_text="  Friday.  ", usage=_Usage(12, 3))

    monkeypatch.setattr(client.responses, "create", fake_create)
    assistant = OpenAIAssistant(client, "test-model")

    with caplog.at_level(logging.INFO, logger="taskmind.assistant"):
        reply = assistant.reply(NOTE, [Turn("user", "Hi"), Turn("assistant", "Hello")], "When?")

    assert reply == "Friday."
    assert calls[0]["model"] == "test-model"
    assert "Ship it on Friday" in calls[0]["instructions"]
    assert calls[0]["input"][-1] == {"role": "user", "content": "When?"}
    assert len(calls[0]["input"]) == 3
    fields = caplog.records[-1].__dict__["fields"]
    assert fields["model"] == "test-model"
    assert fields["input_tokens"] == 12
    assert fields["output_tokens"] == 3
    assert fields["latency_ms"] >= 0
    assert "Friday" not in str(fields)


def test_a_connection_error_becomes_an_assistant_error_and_is_logged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    client = _client()

    def fake_create(**kwargs: Any) -> _Response:
        request = httpx2.Request("POST", "https://api.openai.com/v1/responses")
        raise APIConnectionError(request=request)

    monkeypatch.setattr(client.responses, "create", fake_create)

    with (
        caplog.at_level(logging.ERROR, logger="taskmind.assistant"),
        pytest.raises(AssistantError),
    ):
        OpenAIAssistant(client, "test-model").reply(NOTE, [], "When?")

    errors = [r for r in caplog.records if r.name == "taskmind.assistant"]
    assert len(errors) == 1
    assert errors[0].__dict__["fields"]["error"] == "APIConnectionError"
    assert errors[0].exc_info is not None


def test_an_empty_reply_is_an_assistant_error(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    monkeypatch.setattr(
        client.responses, "create", lambda **kwargs: _Response(output_text="  ", usage=None)
    )

    with pytest.raises(AssistantError):
        OpenAIAssistant(client, "test-model").reply(NOTE, [], "When?")


# Selection


def test_without_a_key_the_echo_answers(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with caplog.at_level(logging.WARNING, logger="taskmind.assistant"):
        assistant = get_assistant()

    assert isinstance(assistant, EchoAssistant)
    assert any("OPENAI_API_KEY is not set" in r.getMessage() for r in caplog.records)


def test_with_a_key_openai_answers_with_the_configured_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_MODEL", "some-model")

    assistant = get_assistant()

    assert isinstance(assistant, OpenAIAssistant)
    assert assistant._model == "some-model"
    assert get_assistant() is assistant
```

Check: `cd backend && uv run pytest tests/unit` passes; the Validate command is clean; the
integration suite still passes with the echo.

---

### Task 2: Configuration and docs

**Files:**
- Modify: `.env.example`
- Modify: `docker-compose.yml`
- Modify: `README.md`
- Modify: `AGENTS.md`

- [ ] **Step 1: `.env.example`**

Append to `.env.example`:

```

# Assistant. Leave OPENAI_API_KEY empty and an echo answers instead of OpenAI, so the app runs
# without a key. The model is OpenAI's recommended cost-efficient one; change it here, not in code.
OPENAI_API_KEY=
OPENAI_MODEL=gpt-6-luna
```

- [ ] **Step 2: Compose**

In `docker-compose.yml`, in the `backend` service's `environment`, after the
`JWT_EXPIRE_MINUTES` line add:

```yaml
      OPENAI_API_KEY: ${OPENAI_API_KEY:-}
      OPENAI_MODEL: ${OPENAI_MODEL:-gpt-6-luna}
```

- [ ] **Step 3: README**

Insert after the Chats subsection (after the paragraph ending "the reply is a 502 and nothing
is stored.") and before "### Changing the schema":

````markdown
### The assistant

Set `OPENAI_API_KEY` in `.env` and the assistant answers through OpenAI, using only the note the
chat belongs to; `OPENAI_MODEL` picks the model. Leave the key empty and an echo answers instead,
so everything else can be tried without a key; the log says so once at the first message.

Each call has a 30-second timeout and at most two retries on transient errors. If it still fails,
the message post is a 502 and nothing is stored, so re-send it.
````

Also change the Chats subsection's sentence "Until PR 7 the assistant is an echo, so the flow can
be tried without an API key." to "Without an `OPENAI_API_KEY` the assistant is an echo, so the
flow can be tried without a key."

- [ ] **Step 4: AGENTS.md**

In "## Architecture & Structure", replace the `backend/app/assistant.py` line with:

```markdown
- `backend/app/assistant.py` — the `Assistant` protocol, `get_assistant` and `AssistantDep`; routers never call a provider directly. `build_assistant()` picks `OpenAIAssistant` when `OPENAI_API_KEY` is set, else `EchoAssistant`, once per process (cached); tests override the dependency or clear the cache
```

In "## Quirks & Gotchas", after the `get_settings()` line add:

```markdown
- ⚠️ **`build_assistant()` is cached like `get_settings()`** — a test that sets `OPENAI_API_KEY` must clear both caches; `tests/conftest.py` unsets the key so no test ever calls OpenAI.
```

Check: README renders; `AGENTS.md` keeps the required section above the divider.

---

## Gaps against HD policy, recorded on purpose

- Observability rule 11: no OpenInference tracing to Arize Phoenix. The call logs model, tokens
  and latency instead. Adding Phoenix is the first candidate after the assignment.
- No live call was made while building this: the developer's `.env` has no key. The call shape
  follows the SDK's README read on 2026-10-29 and is exercised against the patched client.

## Documentation Notes

- How the OpenAI call is observed → **PR**: `taskmind.assistant` lines with model, tokens and latency; failure is an `error` line with `exc_info` then a 502 on the request line.
- The model choice and where to change it → **README** (Task 2) and `.env.example`.
- Both caches to clear in tests → **AGENTS.md** Quirks (Task 2).
