"""Request and response schemas for chats.

``ChatDetail`` is a chat with its most recent messages, oldest first; the list and create routes
return ``ChatRead`` without them.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.message import MessageRead
from app.schemas.text import strip_text

TITLE_MAX_LENGTH = 100


class ChatCreate(BaseModel):
    title: str = Field(min_length=1, max_length=TITLE_MAX_LENGTH)

    @field_validator("title", mode="before")
    @classmethod
    def _strip_title(cls, value: object) -> object:
        return strip_text(value)


class ChatUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=TITLE_MAX_LENGTH)

    @field_validator("title", mode="before")
    @classmethod
    def _strip_title(cls, value: object) -> object:
        return strip_text(value)


class ChatRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    note_id: int
    user_id: int
    title: str
    created_at: datetime
    updated_at: datetime


class ChatDetail(ChatRead):
    messages: list[MessageRead]
