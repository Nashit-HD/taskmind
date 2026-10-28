"""Request and response schemas for sign-in.

Request and response classes are separate: a response never carries the password or its hash.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128


def _normalise_email(value: str) -> str:
    """One spelling per address: trimmed and lower-cased, so the unique constraint sees repeats."""
    return value.strip().lower()


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)

    @field_validator("email", mode="after")
    @classmethod
    def _lower_email(cls, value: str) -> str:
        return _normalise_email(value)


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)

    @field_validator("email", mode="after")
    @classmethod
    def _lower_email(cls, value: str) -> str:
        return _normalise_email(value)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
