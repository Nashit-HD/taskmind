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
