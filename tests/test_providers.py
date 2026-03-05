from types import SimpleNamespace
from typing import Any, cast

import pytest

from app.providers import (
    FALLBACK_MODELS,
    _extract_anthropic_text,
    _extract_google_text,
    _extract_openai_text,
    _sort_and_deduplicate,
    list_provider_models,
    resolve_model,
    run_provider_prompt,
)
from tests.utils import make_settings


def test_resolve_model_uses_default_and_override():
    assert resolve_model("openai", None) == "gpt-5.2"
    assert resolve_model("openai", "custom-model") == "custom-model"


def test_sort_and_deduplicate_keeps_default_first():
    models = _sort_and_deduplicate(
        ["gpt-5.2", "gpt-5-mini", "gpt-5.2", "  ", "gpt-4.1"],
        default_model="gpt-5.2",
    )
    assert models == ["gpt-5.2", "gpt-4.1", "gpt-5-mini"]


def test_extract_openai_text_prefers_output_text():
    response = SimpleNamespace(output_text="  direct output  ", output=[])
    assert _extract_openai_text(response) == "direct output"


def test_extract_openai_text_falls_back_to_output_chunks():
    response = SimpleNamespace(
        output_text=None,
        output=[
            SimpleNamespace(content=[SimpleNamespace(text="Chunk 1"), SimpleNamespace(text="")]),
            SimpleNamespace(content=[SimpleNamespace(text="Chunk 2")]),
        ],
    )
    assert _extract_openai_text(response) == "Chunk 1\nChunk 2"


def test_extract_anthropic_text_reads_text_blocks_only():
    response = SimpleNamespace(
        content=[
            SimpleNamespace(type="tool_use", text="ignored"),
            SimpleNamespace(type="text", text="  First  "),
            SimpleNamespace(type="text", text="Second"),
        ]
    )
    assert _extract_anthropic_text(response) == "First\nSecond"


def test_extract_google_text_prefers_top_level_text():
    response = SimpleNamespace(text="  top level  ", candidates=[])
    assert _extract_google_text(response) == "top level"


def test_extract_google_text_falls_back_to_candidate_parts():
    response = SimpleNamespace(
        text=None,
        candidates=[
            SimpleNamespace(
                content=SimpleNamespace(parts=[SimpleNamespace(text="Part 1"), SimpleNamespace(text="Part 2")])
            )
        ],
    )
    assert _extract_google_text(response) == "Part 1\nPart 2"


@pytest.mark.asyncio
async def test_run_provider_prompt_requires_openai_key():
    settings = make_settings(openai_api_key=None)

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY is not configured"):
        await run_provider_prompt("openai", settings, "prompt")


@pytest.mark.asyncio
async def test_run_provider_prompt_openai_success_passes_expected_args(monkeypatch):
    settings = make_settings(openai_api_key="my-key", provider_timeout_seconds=33, max_output_tokens=777)
    captured: dict[str, Any] = {}

    def fake_run_openai(api_key, model, prompt, reasoning_effort, max_output_tokens):
        captured["api_key"] = api_key
        captured["model"] = model
        captured["prompt"] = prompt
        captured["reasoning_effort"] = reasoning_effort
        captured["max_output_tokens"] = max_output_tokens
        return "ok"

    async def fake_wait_for(awaitable, timeout):
        captured["timeout"] = timeout
        return await awaitable

    monkeypatch.setattr("app.providers._run_openai", fake_run_openai)
    monkeypatch.setattr("app.providers.asyncio.wait_for", fake_wait_for)

    model, answer = await run_provider_prompt(
        provider="openai",
        settings=settings,
        prompt="prompt text",
        model="gpt-custom",
        reasoning_effort="high",
    )

    assert model == "gpt-custom"
    assert answer == "ok"
    assert captured == {
        "api_key": "my-key",
        "model": "gpt-custom",
        "prompt": "prompt text",
        "reasoning_effort": "high",
        "max_output_tokens": 777,
        "timeout": 33,
    }


@pytest.mark.asyncio
async def test_run_provider_prompt_unsupported_provider_raises():
    settings = make_settings()

    with pytest.raises(KeyError, match="invalid"):
        await run_provider_prompt(cast(Any, "invalid"), settings, "prompt")


@pytest.mark.asyncio
async def test_list_provider_models_returns_fallback_without_api_key():
    settings = make_settings(openai_api_key=None)

    models = await list_provider_models("openai", settings)

    assert models[0] == "gpt-5.2"
    assert set(models) == set(_sort_and_deduplicate(FALLBACK_MODELS["openai"], default_model="gpt-5.2"))


@pytest.mark.asyncio
async def test_list_provider_models_uses_provider_listing_when_available(monkeypatch):
    settings = make_settings(openai_api_key="my-key")

    async def fake_wait_for(awaitable, timeout):
        assert timeout == 20
        return await awaitable

    monkeypatch.setattr("app.providers.asyncio.wait_for", fake_wait_for)
    monkeypatch.setattr(
        "app.providers._list_openai_models",
        lambda api_key: ["gpt-5.2", "z-model", "a-model", "z-model"],
    )

    models = await list_provider_models("openai", settings)

    assert models == ["gpt-5.2", "a-model", "z-model"]


@pytest.mark.asyncio
async def test_list_provider_models_falls_back_when_listing_errors(monkeypatch):
    settings = make_settings(openai_api_key="my-key")

    monkeypatch.setattr("app.providers._list_openai_models", lambda api_key: (_ for _ in ()).throw(RuntimeError("boom")))

    models = await list_provider_models("openai", settings)

    assert models[0] == "gpt-5.2"
    assert set(models) == set(FALLBACK_MODELS["openai"])

