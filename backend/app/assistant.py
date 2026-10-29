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
