from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
import hashlib
import hmac
import time

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings

bearer_scheme = HTTPBearer(auto_error=False)


class RateLimitExceededError(RuntimeError):
    """Raised when an action exceeds the configured rate limit."""


@dataclass(frozen=True)
class Principal:
    principal_id: str


class SlidingWindowRateLimiter:
    def __init__(self, *, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = time.time()
        queue = self._events[key]
        cutoff = now - self.window_seconds

        while queue and queue[0] < cutoff:
            queue.popleft()

        if len(queue) >= self.limit:
            raise RateLimitExceededError(
                f"Rate limit exceeded: max {self.limit} operations per {self.window_seconds} seconds"
            )

        queue.append(now)


async def require_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> Principal:
    settings = get_settings()

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Missing Bearer token")

    provided_token = credentials.credentials.strip()
    if not provided_token:
        raise HTTPException(status_code=401, detail="Missing Bearer token")

    if not hmac.compare_digest(provided_token, settings.app_api_token):
        raise HTTPException(status_code=401, detail="Invalid token")

    token_hash = hashlib.sha256(provided_token.encode("utf-8")).hexdigest()
    return Principal(principal_id=token_hash)


def safe_error_message(exc: Exception) -> str:
    from app.providers import ProviderConfigurationError

    if isinstance(exc, ProviderConfigurationError):
        return str(exc)

    if isinstance(exc, TimeoutError):
        return "Provider request timed out"

    return "Provider request failed"
