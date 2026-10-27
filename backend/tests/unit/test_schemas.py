import pytest
from pydantic import ValidationError

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
