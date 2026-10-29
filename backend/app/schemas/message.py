"""Request and response schemas for messages.

A message is written once and never changes, so there is no update schema. Posting one returns
both halves of the exchange: the user's message and the assistant's reply.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.text import strip_text

CONTENT_MAX_LENGTH = 4000


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=CONTENT_MAX_LENGTH)

    @field_validator("content", mode="before")
    @classmethod
    def _strip_content(cls, value: object) -> object:
        return strip_text(value)


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    chat_id: int
    role: str
    content: str
    created_at: datetime


class MessageExchange(BaseModel):
    user_message: MessageRead
    assistant_message: MessageRead
