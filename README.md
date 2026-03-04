# Story Assist

Story Assist expands short story sketches into researched outputs by asking configurable questions against web-enabled LLM providers.

## Security Defaults

- API routes require `Authorization: Bearer <APP_API_TOKEN>`.
- Job creation is rate-limited and concurrency-bounded.
- Request size and question-count limits are enforced.
- Security headers and restrictive default CORS are enabled.
- Prompt templates are stored in `app/templates/`.

## Install

1. Install prerequisites (Windows + Scoop):
   - `scoop install git uv python`
2. Create virtual environment:
   - `uv venv .venv`
3. Sync dependencies:
   - `.\.venv\Scripts\activate`
   - `uv sync --all-groups`
4. Configure API keys and token:
   - `Copy-Item .env.example .env`
   - Set `APP_API_TOKEN` to a long random value.
   - Fill one or more of `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`.

## Run

```powershell
uv run uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`, paste `APP_API_TOKEN` in the UI token field, then run analyses.

## Runtime Limits

Adjust in `.env` if needed:

- `ALLOWED_ORIGINS`
- `MAX_STORY_SKETCH_CHARS`
- `MAX_QUESTION_PREAMBLE_CHARS`
- `MAX_QUESTIONS`
- `MAX_QUESTION_CHARS`
- `MAX_ACTIVE_JOBS`
- `MAX_CONCURRENT_JOBS`
- `MAX_PARALLEL_QUESTIONS_PER_JOB`
- `MAX_GLOBAL_PARALLEL_QUESTIONS`
- `MAX_JOB_CREATIONS_PER_MINUTE`
- `PROVIDER_TIMEOUT_SECONDS`
- `MAX_OUTPUT_TOKENS`

## Defaults

- OpenAI: `gpt-5.2`
- Anthropic: `claude-sonnet-4-5`
- Google: `gemini-2.5-pro`

OpenAI requests support configurable `reasoning_effort` (`none`, `minimal`, `low`, `medium`, `high`, `xhigh`) from the UI.

## Test

```powershell
uv run pytest
```
