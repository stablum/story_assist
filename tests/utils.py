from app.config import Settings


def make_settings(**overrides):
    defaults = {
        "openai_api_key": "openai-key",
        "anthropic_api_key": "anthropic-key",
        "google_api_key": "google-key",
        "app_api_token": "test-token",
        "allowed_origins": ("http://127.0.0.1:8000",),
        "max_story_sketch_chars": 20000,
        "max_question_preamble_chars": 4000,
        "max_questions": 12,
        "max_question_chars": 600,
        "max_jobs_kept": 200,
        "max_active_jobs": 30,
        "max_concurrent_jobs": 4,
        "max_parallel_questions_per_job": 4,
        "max_global_parallel_questions": 16,
        "max_job_creations_per_minute": 20,
        "provider_timeout_seconds": 90,
        "max_output_tokens": 1600,
    }
    defaults.update(overrides)
    return Settings(**defaults)
