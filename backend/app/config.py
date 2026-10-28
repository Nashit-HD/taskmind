"""Application settings, read from the environment.

Values come from the process environment first, then from the repository-root ``.env`` file when
it exists. Inside Docker there is no ``.env``: Compose injects the variables.
"""

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends
from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

JWT_SECRET_PLACEHOLDER = "change-me-generate-a-real-secret-see-README"
MIN_JWT_SECRET_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    database_url: str
    cors_origins: str = "http://localhost:3000"
    jwt_secret: SecretStr
    jwt_expire_minutes: int = 60

    @property
    def cors_origin_list(self) -> list[str]:
        """``CORS_ORIGINS`` as a list: comma-separated in the environment, blanks dropped."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @field_validator("jwt_secret")
    @classmethod
    def _jwt_secret_is_real(cls, value: SecretStr) -> SecretStr:
        """Refuse the example placeholder and anything shorter than HS256's recommended key.

        A ``SecretStr`` keeps the value out of reprs and logs; this is the one place it is read.
        """
        secret = value.get_secret_value()
        if secret == JWT_SECRET_PLACEHOLDER or len(secret) < MIN_JWT_SECRET_LENGTH:
            raise ValueError(
                f"JWT_SECRET must be at least {MIN_JWT_SECRET_LENGTH} characters and not the "
                "placeholder from .env.example. Generate one with: "
                'python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )
        return value


@lru_cache
def get_settings() -> Settings:
    """One ``Settings`` per process. Tests clear the cache after changing the environment."""
    return Settings()


SettingsDep = Annotated[Settings, Depends(get_settings)]
