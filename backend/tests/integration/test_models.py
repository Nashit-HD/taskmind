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
