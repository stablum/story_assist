# Story Assist

Story Assist expands short story sketches into researched outputs by asking configurable questions against web-enabled LLM providers.

## Install

1. Install prerequisites (Windows + Scoop):
   - `scoop install git uv python`
2. Create virtual environment:
   - `uv venv .venv`
3. Sync dependencies:
   - `.\.venv\Scripts\activate`
   - `uv sync --all-groups`
4. Configure API keys:
   - `Copy-Item .env.example .env`
   - Fill one or more of `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`

## Run

```powershell
uv run uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

Default provider models:
- OpenAI: `gpt-5`
- Anthropic: `claude-sonnet-4-5`
- Google: `gemini-2.5-pro`

## Test

```powershell
uv run pytest
```
