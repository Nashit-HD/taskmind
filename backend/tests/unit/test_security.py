from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.config import Settings, get_settings
from app.security import (
    ALGORITHM,
    TokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


@pytest.fixture
def settings() -> Settings:
    return get_settings()


def test_a_hash_verifies_its_own_password_and_rejects_another() -> None:
    hashed = hash_password("correct horse battery")

    assert hashed.startswith("$argon2id$")
    assert verify_password("correct horse battery", hashed)
    assert not verify_password("wrong horse", hashed)


def test_two_hashes_of_one_password_differ() -> None:
    assert hash_password("same") != hash_password("same")


def test_a_token_round_trips_the_user_id(settings: Settings) -> None:
    token = create_access_token(42, settings)

    assert decode_access_token(token, settings) == 42


def test_an_expired_token_is_rejected(settings: Settings) -> None:
    long_ago = datetime.now(UTC) - timedelta(minutes=settings.jwt_expire_minutes + 1)
    token = create_access_token(42, settings, now=long_ago)

    with pytest.raises(TokenError, match="expired"):
        decode_access_token(token, settings)


def test_a_token_signed_with_another_secret_is_rejected(settings: Settings) -> None:
    other = Settings(jwt_secret="another-secret-that-is-also-long-enough-123")
    token = create_access_token(42, other)

    with pytest.raises(TokenError, match="Signature"):
        decode_access_token(token, settings)


def test_a_tampered_token_is_rejected(settings: Settings) -> None:
    token = create_access_token(42, settings)
    header, payload, signature = token.split(".")
    tampered = ".".join(
        [header, payload[:-2] + ("AA" if payload[-2:] != "AA" else "BB"), signature]
    )

    with pytest.raises(TokenError):
        decode_access_token(tampered, settings)


def test_a_token_without_an_expiry_is_rejected(settings: Settings) -> None:
    token = jwt.encode(
        {"sub": "42", "iat": datetime.now(UTC)},
        settings.jwt_secret.get_secret_value(),
        algorithm=ALGORITHM,
    )

    with pytest.raises(TokenError, match="exp"):
        decode_access_token(token, settings)


def test_a_token_whose_subject_is_not_a_user_id_is_rejected(settings: Settings) -> None:
    now = datetime.now(UTC)
    token = jwt.encode(
        {"sub": "admin", "iat": now, "exp": now + timedelta(minutes=5)},
        settings.jwt_secret.get_secret_value(),
        algorithm=ALGORITHM,
    )

    with pytest.raises(TokenError, match="user id"):
        decode_access_token(token, settings)


def test_garbage_is_rejected(settings: Settings) -> None:
    with pytest.raises(TokenError):
        decode_access_token("not.a.token", settings)
