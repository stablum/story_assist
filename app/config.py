from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os

from dotenv import load_dotenv

load_dotenv()


def _split_csv(value: str | None, *, default: tuple[str, ...]) -> tuple[str, ...]:
    if not value:
        return default
    parsed = tuple(part.strip() for part in value.split(",") if part.strip())
    return parsed or default


def _int_env(name: str, default: int, *, minimum: int = 1, maximum: int = 1_000_000) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(minimum, min(maximum, value))


@dataclass(frozen=True)
class Settings:
    openai_api_key: str | None
    anthropic_api_key: str | None
    google_api_key: str | None
    app_api_token: str
    allowed_origins: tuple[str, ...]
    max_story_sketch_chars: int
    max_question_preamble_chars: int
    max_questions: int
    max_question_chars: int
    max_jobs_kept: int
    max_active_jobs: int
    max_concurrent_jobs: int
    max_parallel_questions_per_job: int
    max_global_parallel_questions: int
    max_job_creations_per_minute: int
    provider_timeout_seconds: int
    max_output_tokens: int


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    app_api_token = (os.getenv("APP_API_TOKEN") or "").strip()
    if not app_api_token:
        raise RuntimeError("APP_API_TOKEN must be set in environment or .env")

    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        app_api_token=app_api_token,
        allowed_origins=_split_csv(
            os.getenv("ALLOWED_ORIGINS"),
            default=("http://127.0.0.1:8000", "http://localhost:8000"),
        ),
        max_story_sketch_chars=_int_env("MAX_STORY_SKETCH_CHARS", 20000, minimum=500, maximum=500000),
        max_question_preamble_chars=_int_env(
            "MAX_QUESTION_PREAMBLE_CHARS",
            4000,
            minimum=0,
            maximum=50000,
        ),
        max_questions=_int_env("MAX_QUESTIONS", 12, minimum=1, maximum=100),
        max_question_chars=_int_env("MAX_QUESTION_CHARS", 600, minimum=20, maximum=20000),
        max_jobs_kept=_int_env("MAX_JOBS_KEPT", 200, minimum=20, maximum=10000),
        max_active_jobs=_int_env("MAX_ACTIVE_JOBS", 30, minimum=1, maximum=2000),
        max_concurrent_jobs=_int_env("MAX_CONCURRENT_JOBS", 4, minimum=1, maximum=500),
        max_parallel_questions_per_job=_int_env(
            "MAX_PARALLEL_QUESTIONS_PER_JOB",
            4,
            minimum=1,
            maximum=100,
        ),
        max_global_parallel_questions=_int_env(
            "MAX_GLOBAL_PARALLEL_QUESTIONS",
            16,
            minimum=1,
            maximum=2000,
        ),
        max_job_creations_per_minute=_int_env(
            "MAX_JOB_CREATIONS_PER_MINUTE",
            20,
            minimum=1,
            maximum=10000,
        ),
        provider_timeout_seconds=_int_env("PROVIDER_TIMEOUT_SECONDS", 90, minimum=5, maximum=600),
        max_output_tokens=_int_env("MAX_OUTPUT_TOKENS", 1600, minimum=200, maximum=8000),
    )
