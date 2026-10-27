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
