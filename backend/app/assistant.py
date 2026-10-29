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
