import hashlib

import pytest
from fastapi import HTTPException
from fastapi.security.http import HTTPAuthorizationCredentials

from app.providers import ProviderConfigurationError
from app.security import (
    RateLimitExceededError,
    SlidingWindowRateLimiter,
    require_principal,
    safe_error_message,
)


def test_rate_limiter_allows_requests_within_limit(monkeypatch):
    limiter = SlidingWindowRateLimiter(limit=3, window_seconds=60)
    timestamps = iter([0.0, 1.0, 2.0])
    monkeypatch.setattr("app.security.time.time", lambda: next(timestamps))

    limiter.check("user")
    limiter.check("user")
    limiter.check("user")


def test_rate_limiter_rejects_when_limit_is_exceeded(monkeypatch):
    limiter = SlidingWindowRateLimiter(limit=2, window_seconds=60)
    timestamps = iter([0.0, 1.0, 2.0])
    monkeypatch.setattr("app.security.time.time", lambda: next(timestamps))

    limiter.check("user")
    limiter.check("user")
    with pytest.raises(RateLimitExceededError, match="Rate limit exceeded"):
        limiter.check("user")


def test_rate_limiter_expires_old_events(monkeypatch):
    limiter = SlidingWindowRateLimiter(limit=2, window_seconds=10)
    timestamps = iter([0.0, 5.0, 11.0])
    monkeypatch.setattr("app.security.time.time", lambda: next(timestamps))

    limiter.check("user")
    limiter.check("user")
    limiter.check("user")


@pytest.mark.asyncio
async def test_require_principal_missing_token_is_rejected(monkeypatch):
    monkeypatch.setenv("APP_API_TOKEN", "secret")

    with pytest.raises(HTTPException, match="Missing Bearer token") as exc_info:
        await require_principal(None)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_require_principal_non_bearer_scheme_is_rejected(monkeypatch):
    monkeypatch.setenv("APP_API_TOKEN", "secret")
    credentials = HTTPAuthorizationCredentials(scheme="Basic", credentials="secret")

    with pytest.raises(HTTPException, match="Missing Bearer token"):
        await require_principal(credentials)


@pytest.mark.asyncio
async def test_require_principal_blank_bearer_token_is_rejected(monkeypatch):
    monkeypatch.setenv("APP_API_TOKEN", "secret")
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="   ")

    with pytest.raises(HTTPException, match="Missing Bearer token"):
        await require_principal(credentials)


@pytest.mark.asyncio
async def test_require_principal_invalid_token_is_rejected(monkeypatch):
    monkeypatch.setenv("APP_API_TOKEN", "secret")
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="wrong")

    with pytest.raises(HTTPException, match="Invalid token") as exc_info:
        await require_principal(credentials)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_require_principal_valid_token_returns_hashed_principal(monkeypatch):
    token = "secret"
    monkeypatch.setenv("APP_API_TOKEN", token)
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    principal = await require_principal(credentials)

    assert principal.principal_id == hashlib.sha256(token.encode("utf-8")).hexdigest()


def test_safe_error_message_for_provider_configuration_error():
    exc = ProviderConfigurationError("OPENAI_API_KEY is not configured")
    assert safe_error_message(exc) == "OPENAI_API_KEY is not configured"


def test_safe_error_message_for_timeout_error():
    assert safe_error_message(TimeoutError()) == "Provider request timed out"


def test_safe_error_message_for_unknown_error():
    assert safe_error_message(RuntimeError("boom")) == "Provider request failed"
