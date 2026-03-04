from __future__ import annotations

import asyncio
from typing import Any

from app.config import Settings
from app.schemas import ProviderName, ReasoningEffort

DEFAULT_MODELS: dict[ProviderName, str] = {
    "openai": "gpt-5.2",
    "anthropic": "claude-sonnet-4-5",
    "google": "gemini-2.5-pro",
}
FALLBACK_MODELS: dict[ProviderName, list[str]] = {
    "openai": [
        "gpt-5.2",
        "gpt-5.3-chat-latest",
        "gpt-5.1-chat-latest",
        "gpt-5",
        "gpt-5-mini",
        "gpt-4.1",
        "gpt-4.1-mini",
        "gpt-4o",
        "gpt-4o-mini",
    ],
    "anthropic": [
        "claude-sonnet-4-5",
        "claude-opus-4-1",
        "claude-sonnet-4",
    ],
    "google": [
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
    ],
}


class ProviderConfigurationError(RuntimeError):
    """Raised when provider configuration is missing or invalid."""


class ProviderExecutionError(RuntimeError):
    """Raised when a provider call fails to return a usable answer."""


def resolve_model(provider: ProviderName, requested_model: str | None) -> str:
    if requested_model:
        return requested_model
    return DEFAULT_MODELS[provider]


def _sort_and_deduplicate(models: list[str], *, default_model: str) -> list[str]:
    unique = sorted({model.strip() for model in models if model and model.strip()})
    if default_model in unique:
        unique.remove(default_model)
    return [default_model, *unique]


def _list_openai_models(api_key: str) -> list[str]:
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    response = client.models.list()
    return [item.id for item in getattr(response, "data", []) if getattr(item, "id", None)]


def _list_anthropic_models(api_key: str) -> list[str]:
    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)
    response = client.models.list()
    return [item.id for item in getattr(response, "data", []) if getattr(item, "id", None)]


def _list_google_models(api_key: str) -> list[str]:
    from google import genai

    client = genai.Client(api_key=api_key)
    names: list[str] = []
    for item in client.models.list():
        model_name = getattr(item, "name", "")
        if not model_name:
            continue
        names.append(model_name.split("/")[-1])
    return names


def _extract_openai_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if output_text:
        return output_text.strip()

    chunks: list[str] = []
    output_items = getattr(response, "output", None) or []
    for item in output_items:
        content_items = getattr(item, "content", None) or []
        for content in content_items:
            text = getattr(content, "text", None)
            if text:
                chunks.append(text)

    return "\n".join(chunks).strip()


def _extract_anthropic_text(response: Any) -> str:
    parts: list[str] = []
    for block in getattr(response, "content", []):
        if getattr(block, "type", None) == "text":
            text = getattr(block, "text", "").strip()
            if text:
                parts.append(text)

    return "\n".join(parts).strip()


def _extract_google_text(response: Any) -> str:
    text = getattr(response, "text", None)
    if text:
        return text.strip()

    parts: list[str] = []
    for candidate in getattr(response, "candidates", []) or []:
        content = getattr(candidate, "content", None)
        if not content:
            continue
        for block in getattr(content, "parts", []) or []:
            piece = getattr(block, "text", None)
            if piece:
                parts.append(piece)

    return "\n".join(parts).strip()


def _run_openai(
    api_key: str,
    model: str,
    prompt: str,
    reasoning_effort: ReasoningEffort | None,
    max_output_tokens: int,
) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    payload: dict[str, Any] = {
        "model": model,
        "input": prompt,
        "max_output_tokens": max_output_tokens,
        "tools": [{"type": "web_search_preview"}],
    }
    if reasoning_effort:
        payload["reasoning"] = {"effort": reasoning_effort}

    response = client.responses.create(**payload)

    text = _extract_openai_text(response)
    if not text:
        raise ProviderExecutionError("OpenAI returned an empty answer")
    return text


def _run_anthropic(api_key: str, model: str, prompt: str, max_output_tokens: int) -> str:
    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=max_output_tokens,
        temperature=0.2,
        tools=[
            {
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": 4,
            }
        ],
        messages=[{"role": "user", "content": prompt}],
    )

    text = _extract_anthropic_text(response)
    if not text:
        raise ProviderExecutionError("Anthropic returned an empty answer")
    return text


def _run_google(api_key: str, model: str, prompt: str, max_output_tokens: int) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=max_output_tokens,
            tools=[types.Tool(google_search=types.GoogleSearch())],
        ),
    )

    text = _extract_google_text(response)
    if not text:
        raise ProviderExecutionError("Google Gemini returned an empty answer")
    return text


async def run_provider_prompt(
    provider: ProviderName,
    settings: Settings,
    prompt: str,
    model: str | None = None,
    reasoning_effort: ReasoningEffort | None = None,
) -> tuple[str, str]:
    resolved_model = resolve_model(provider, model)
    timeout = settings.provider_timeout_seconds
    max_output_tokens = settings.max_output_tokens

    if provider == "openai":
        if not settings.openai_api_key:
            raise ProviderConfigurationError("OPENAI_API_KEY is not configured")
        answer = await asyncio.wait_for(
            asyncio.to_thread(
                _run_openai,
                settings.openai_api_key,
                resolved_model,
                prompt,
                reasoning_effort,
                max_output_tokens,
            ),
            timeout=timeout,
        )
        return resolved_model, answer

    if provider == "anthropic":
        if not settings.anthropic_api_key:
            raise ProviderConfigurationError("ANTHROPIC_API_KEY is not configured")
        answer = await asyncio.wait_for(
            asyncio.to_thread(
                _run_anthropic,
                settings.anthropic_api_key,
                resolved_model,
                prompt,
                max_output_tokens,
            ),
            timeout=timeout,
        )
        return resolved_model, answer

    if provider == "google":
        if not settings.google_api_key:
            raise ProviderConfigurationError("GOOGLE_API_KEY is not configured")
        answer = await asyncio.wait_for(
            asyncio.to_thread(
                _run_google,
                settings.google_api_key,
                resolved_model,
                prompt,
                max_output_tokens,
            ),
            timeout=timeout,
        )
        return resolved_model, answer

    raise ProviderConfigurationError(f"Unsupported provider: {provider}")


async def list_provider_models(provider: ProviderName, settings: Settings) -> list[str]:
    default_model = resolve_model(provider, None)
    fallback_models = FALLBACK_MODELS[provider]

    try:
        if provider == "openai":
            if not settings.openai_api_key:
                return _sort_and_deduplicate(fallback_models, default_model=default_model)
            models = await asyncio.wait_for(
                asyncio.to_thread(_list_openai_models, settings.openai_api_key),
                timeout=20,
            )
            return _sort_and_deduplicate(models, default_model=default_model)

        if provider == "anthropic":
            if not settings.anthropic_api_key:
                return _sort_and_deduplicate(fallback_models, default_model=default_model)
            models = await asyncio.wait_for(
                asyncio.to_thread(_list_anthropic_models, settings.anthropic_api_key),
                timeout=20,
            )
            return _sort_and_deduplicate(models, default_model=default_model)

        if provider == "google":
            if not settings.google_api_key:
                return _sort_and_deduplicate(fallback_models, default_model=default_model)
            models = await asyncio.wait_for(
                asyncio.to_thread(_list_google_models, settings.google_api_key),
                timeout=20,
            )
            return _sort_and_deduplicate(models, default_model=default_model)
    except Exception:
        return _sort_and_deduplicate(fallback_models, default_model=default_model)

    return _sort_and_deduplicate(fallback_models, default_model=default_model)
