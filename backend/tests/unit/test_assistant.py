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
