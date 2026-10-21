"""Application settings, read from the environment.

Values come from the process environment first, then from the repository-root ``.env`` file when
it exists. Inside Docker there is no ``.env``: Compose injects the variables.
"""

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    database_url: str
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        """``CORS_ORIGINS`` as a list: comma-separated in the environment, blanks dropped."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """One ``Settings`` per process. Tests clear the cache after changing the environment."""
    return Settings()


SettingsDep = Annotated[Settings, Depends(get_settings)]
