"""Who is making this request.

``get_current_user`` is the one place a bearer token becomes a user. Every router that needs a
signed-in user declares ``CurrentUserDep``; nothing else reads the token (ADR 0002 keeps auth
behind this seam so another identity provider can replace it later).

Every failure is 401 with ``WWW-Authenticate: Bearer`` and the same body, and is logged with a
reason but never with the token or an email.
"""

import logging
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import SettingsDep
from app.database import SessionDep
from app.models import User
from app.security import TokenError, decode_access_token

logger = logging.getLogger("taskmind.auth")

_bearer = HTTPBearer(auto_error=False)
BearerDep = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]


def unauthorised(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    request: Request, credentials: BearerDep, db: SessionDep, settings: SettingsDep
) -> User:
    if credentials is None:
        logger.warning("authentication failed", extra={"fields": {"reason": "no token"}})
        raise unauthorised()
    try:
        user_id = decode_access_token(credentials.credentials, settings)
    except TokenError as exc:
        logger.warning(
            "authentication failed",
            extra={"fields": {"reason": "invalid token", "detail": str(exc)}},
        )
        raise unauthorised() from exc
    user = db.get(User, user_id)
    if user is None:
        logger.warning(
            "authentication failed",
            extra={"fields": {"reason": "unknown user", "user_id": user_id}},
        )
        raise unauthorised()
    request.state.user_id = user.id
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]
