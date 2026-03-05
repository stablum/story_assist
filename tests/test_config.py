import pytest

from app.config import _int_env, _split_csv, get_settings


def test_split_csv_uses_default_when_missing():
    assert _split_csv(None, default=("a", "b")) == ("a", "b")
    assert _split_csv("", default=("x",)) == ("x",)


def test_split_csv_trims_and_filters_empty_values():
    output = _split_csv(" https://a.example , , https://b.example ", default=("fallback",))
    assert output == ("https://a.example", "https://b.example")


def test_int_env_returns_default_when_missing_or_invalid(monkeypatch):
    monkeypatch.delenv("EXAMPLE_INT", raising=False)
    assert _int_env("EXAMPLE_INT", 9) == 9

    monkeypatch.setenv("EXAMPLE_INT", "not-a-number")
    assert _int_env("EXAMPLE_INT", 9) == 9


def test_int_env_clamps_between_min_and_max(monkeypatch):
    monkeypatch.setenv("EXAMPLE_INT", "-100")
    assert _int_env("EXAMPLE_INT", 5, minimum=2, maximum=10) == 2

    monkeypatch.setenv("EXAMPLE_INT", "500")
    assert _int_env("EXAMPLE_INT", 5, minimum=2, maximum=10) == 10


def test_get_settings_requires_app_api_token(monkeypatch):
    monkeypatch.delenv("APP_API_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="APP_API_TOKEN"):
        get_settings()


def test_get_settings_parses_values_and_applies_limits(monkeypatch):
    monkeypatch.setenv("APP_API_TOKEN", "  secret-token  ")
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://a.example, https://b.example")
    monkeypatch.setenv("MAX_QUESTIONS", "500")
    monkeypatch.setenv("MAX_QUESTION_PREAMBLE_CHARS", "-1")
    monkeypatch.setenv("MAX_OUTPUT_TOKENS", "invalid")

    settings = get_settings()

    assert settings.app_api_token == "secret-token"
    assert settings.allowed_origins == ("https://a.example", "https://b.example")
    assert settings.max_questions == 100
    assert settings.max_question_preamble_chars == 0
    assert settings.max_output_tokens == 1600


def test_get_settings_uses_default_origins_when_config_missing(monkeypatch):
    monkeypatch.setenv("APP_API_TOKEN", "secret-token")
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)

    settings = get_settings()

    assert settings.allowed_origins == (
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    )


def test_get_settings_cache_behavior(monkeypatch):
    monkeypatch.setenv("APP_API_TOKEN", "first-token")
    first = get_settings()

    monkeypatch.setenv("APP_API_TOKEN", "second-token")
    second = get_settings()
    assert second.app_api_token == first.app_api_token == "first-token"

    get_settings.cache_clear()
    refreshed = get_settings()
    assert refreshed.app_api_token == "second-token"
