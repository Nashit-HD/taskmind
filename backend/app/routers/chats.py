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
