import pytest
from pydantic import ValidationError

from app.config import JWT_SECRET_PLACEHOLDER, Settings, get_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()


def test_cors_origins_are_split_on_commas(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://a.example, http://b.example,")

    assert Settings().cors_origin_list == ["http://a.example", "http://b.example"]


def test_the_placeholder_jwt_secret_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET_PLACEHOLDER)

    with pytest.raises(ValidationError, match="JWT_SECRET must be at least"):
        Settings()


def test_a_short_jwt_secret_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", "x" * 31)

    with pytest.raises(ValidationError, match="JWT_SECRET must be at least"):
        Settings()


def test_the_jwt_secret_does_not_appear_in_the_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", "a-perfectly-good-secret-of-thirty-two-plus")

    assert "perfectly" not in repr(Settings())


def test_jwt_expiry_defaults_to_sixty_minutes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JWT_EXPIRE_MINUTES", raising=False)

    assert Settings().jwt_expire_minutes == 60


def test_an_empty_openai_key_means_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")

    assert Settings().openai_api_key is None


def test_the_openai_key_does_not_appear_in_the_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-very-secret")

    assert "very-secret" not in repr(Settings())
