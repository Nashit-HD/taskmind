"""Request and response schemas for notes.

Request and response classes are separate. ``PUT`` replaces the note, so ``NoteUpdate`` requires
every field. Titles are stripped before the length check, so a whitespace-only title is empty and
rejected; the maximum is the column width.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

TITLE_MAX_LENGTH = 200
# Not in the spec, which caps only message content. The whole note goes to the assistant on every
# message, so its size needs a ceiling. Generous for a note; far below anything the database or
# the model would choke on.
CONTENT_MAX_LENGTH = 20_000


def _strip(value: object) -> object:
    """Trim a string before validation; leave anything else for Pydantic to reject."""
    return value.strip() if isinstance(value, str) else value


class NoteCreate(BaseModel):
    title: str = Field(min_length=1, max_length=TITLE_MAX_LENGTH)
    content: str = Field(default="", max_length=CONTENT_MAX_LENGTH)

    @field_validator("title", mode="before")
    @classmethod
    def _strip_title(cls, value: object) -> object:
        return _strip(value)


class NoteUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=TITLE_MAX_LENGTH)
    content: str = Field(max_length=CONTENT_MAX_LENGTH)

    @field_validator("title", mode="before")
    @classmethod
    def _strip_title(cls, value: object) -> object:
        return _strip(value)


class NoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    author_id: int
    title: str
    content: str
    created_at: datetime
    updated_at: datetime
