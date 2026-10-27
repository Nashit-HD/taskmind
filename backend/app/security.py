"""Password hashing and access tokens.

Passwords are hashed with Argon2id, the library's recommended hasher. Access tokens are HS256
JSON Web Tokens carrying the user id as ``sub``, plus ``iat`` and ``exp``; decoding pins the
algorithm, requires all three claims and checks expiry. Nothing here touches the database or the
request: ``app/auth.py`` turns a token into a user.
"""

from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.config import Settings

ALGORITHM = "HS256"

_password_hash = PasswordHash.recommended()


class TokenError(Exception):
    """The token is missing, malformed, expired, tampered with or signed with another key."""


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _password_hash.verify(password, password_hash)


def create_access_token(user_id: int, settings: Settings, now: datetime | None = None) -> str:
    """A signed token for ``user_id`` that expires ``settings.jwt_expire_minutes`` after ``now``."""
    issued_at = now or datetime.now(UTC)
    claims = {
        "sub": str(user_id),
        "iat": issued_at,
        "exp": issued_at + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(claims, settings.jwt_secret.get_secret_value(), algorithm=ALGORITHM)


def decode_access_token(token: str, settings: Settings) -> int:
    """The user id a valid token names. Raises ``TokenError`` for anything else."""
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[ALGORITHM],
            options={"require": ["sub", "iat", "exp"]},
        )
    except jwt.InvalidTokenError as exc:
        raise TokenError(str(exc)) from exc
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject.isdigit():
        raise TokenError("subject is not a user id")
    return int(subject)
