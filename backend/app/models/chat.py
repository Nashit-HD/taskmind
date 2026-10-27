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
