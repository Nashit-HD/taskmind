import pytest
from pydantic import ValidationError

from app.schemas.chat import TITLE_MAX_LENGTH as CHAT_TITLE_MAX_LENGTH
from app.schemas.chat import ChatCreate, ChatUpdate
from app.schemas.message import CONTENT_MAX_LENGTH as MESSAGE_MAX_LENGTH
from app.schemas.message import MessageCreate
from app.schemas.note import CONTENT_MAX_LENGTH, TITLE_MAX_LENGTH, NoteCreate, NoteUpdate
from app.schemas.user import Token, UserLogin, UserRegister


def test_register_lower_cases_and_trims_the_email() -> None:
    body = UserRegister(email="  Ada@Example.COM ", password="correct horse battery")

    assert body.email == "ada@example.com"


def test_login_lower_cases_and_trims_the_email() -> None:
    body = UserLogin(email=" ADA@example.com", password="x")

    assert body.email == "ada@example.com"


def test_register_rejects_an_invalid_email() -> None:
    with pytest.raises(ValidationError):
        UserRegister(email="not-an-email", password="correct horse battery")


@pytest.mark.parametrize("password", ["short7!", "x" * 129])
def test_register_rejects_a_password_outside_the_length_bounds(password: str) -> None:
    with pytest.raises(ValidationError):
        UserRegister(email="ada@example.com", password=password)


def test_login_rejects_an_empty_password() -> None:
    with pytest.raises(ValidationError):
        UserLogin(email="ada@example.com", password="")


def test_token_type_is_bearer() -> None:
    assert Token(access_token="abc").model_dump() == {"access_token": "abc", "token_type": "bearer"}


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
