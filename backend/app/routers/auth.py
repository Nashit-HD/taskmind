"""Register, log in, and who am I."""

import logging

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.auth import CurrentUserDep, unauthorised
from app.config import SettingsDep
from app.database import SessionDep
from app.models import User
from app.schemas.user import Token, UserLogin, UserRead, UserRegister
from app.security import create_access_token, hash_password, verify_password

logger = logging.getLogger("taskmind.auth")

router = APIRouter(prefix="/auth", tags=["auth"])

# Verified against when the email is unknown, so a login attempt takes the same time whether or
# not the address exists. Computed once at import.
_DUMMY_HASH = hash_password("not-a-real-password")


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(body: UserRegister, db: SessionDep) -> UserRead:
    user = User(email=body.email, password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # The unique constraint on email is the race-safe check; a second registration of the
        # same address lands here whatever the timing.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        ) from None
    db.refresh(user)
    logger.info("user registered", extra={"fields": {"user_id": user.id}})
    return UserRead.model_validate(user)


@router.post("/login")
def login(body: UserLogin, db: SessionDep, settings: SettingsDep) -> Token:
    user = db.scalar(select(User).where(User.email == body.email))
    password_ok = verify_password(body.password, user.password_hash if user else _DUMMY_HASH)
    if user is None or not password_ok:
        logger.warning("login failed", extra={"fields": {"reason": "bad credentials"}})
        raise unauthorised("Incorrect email or password")
    return Token(access_token=create_access_token(user.id, settings))


@router.get("/me")
def me(user: CurrentUserDep) -> UserRead:
    return UserRead.model_validate(user)
