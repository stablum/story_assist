import asyncio

import pytest

from app.providers import ProviderConfigurationError
from app.service import analyze_story, answer_single_question, build_question_block, load_template
from tests.utils import make_settings


@pytest.fixture(autouse=True)
def clear_template_cache():
    load_template.cache_clear()
    yield
    load_template.cache_clear()


def test_load_template_rejects_path_traversal():
    with pytest.raises(ValueError, match="Invalid template path"):
        load_template("..\\README.md")


def test_build_question_block_without_preamble_returns_plain_question():
    assert build_question_block("Where is this set?", None) == "Where is this set?"


@pytest.mark.asyncio
async def test_answer_single_question_builds_prompt_and_calls_provider(monkeypatch):
    settings = make_settings()
    captured = {}

    async def fake_run_provider_prompt(*, provider, settings, prompt, model, reasoning_effort):
        captured["provider"] = provider
        captured["prompt"] = prompt
        captured["model"] = model
        captured["reasoning_effort"] = reasoning_effort
        return "resolved-model", "final answer"

    monkeypatch.setattr("app.service.run_provider_prompt", fake_run_provider_prompt)

    question, model, answer = await answer_single_question(
        story_sketch="A town election story",
        question="Who won and why?",
        question_preamble="Use official election data.",
        provider="openai",
        model="gpt-5.2",
        reasoning_effort="high",
        settings=settings,
    )

    assert question == "Who won and why?"
    assert model == "resolved-model"
    assert answer == "final answer"
    assert captured["provider"] == "openai"
    assert captured["model"] == "gpt-5.2"
    assert captured["reasoning_effort"] == "high"
    assert "A town election story" in captured["prompt"]
    assert "Use official election data." in captured["prompt"]
    assert "Who won and why?" in captured["prompt"]


@pytest.mark.asyncio
async def test_analyze_story_preserves_question_order(monkeypatch):
    settings = make_settings()

    async def fake_answer_single_question(**kwargs):
        question = kwargs["question"]
        if question == "Q1":
            await asyncio.sleep(0.01)
        return question, "model-a", f"answer-{question}"

    monkeypatch.setattr("app.service.answer_single_question", fake_answer_single_question)

    model, results = await analyze_story(
        story_sketch="sketch",
        question_preamble=None,
        questions=["Q1", "Q2"],
        provider="openai",
        model=None,
        reasoning_effort="medium",
        settings=settings,
    )

    assert model == "model-a"
    assert [item.question for item in results] == ["Q1", "Q2"]
    assert [item.answer for item in results] == ["answer-Q1", "answer-Q2"]


@pytest.mark.asyncio
async def test_analyze_story_maps_provider_configuration_errors(monkeypatch):
    settings = make_settings()

    async def fake_answer_single_question(**kwargs):
        question = kwargs["question"]
        if question == "Q2":
            raise ProviderConfigurationError("OPENAI_API_KEY is not configured")
        return question, "model-a", "ok"

    monkeypatch.setattr("app.service.answer_single_question", fake_answer_single_question)

    model, results = await analyze_story(
        story_sketch="sketch",
        question_preamble=None,
        questions=["Q1", "Q2"],
        provider="openai",
        model="gpt-custom",
        reasoning_effort="medium",
        settings=settings,
    )

    assert model == "model-a"
    assert results[0].error is None
    assert results[1].error == "OPENAI_API_KEY is not configured"


@pytest.mark.asyncio
async def test_analyze_story_maps_timeouts_to_safe_error(monkeypatch):
    settings = make_settings()

    async def fake_answer_single_question(**kwargs):
        raise TimeoutError()

    monkeypatch.setattr("app.service.answer_single_question", fake_answer_single_question)

    model, results = await analyze_story(
        story_sketch="sketch",
        question_preamble=None,
        questions=["Q1", "Q2"],
        provider="openai",
        model="gpt-custom",
        reasoning_effort="medium",
        settings=settings,
    )

    assert model == "gpt-custom"
    assert [item.error for item in results] == [
        "Provider request timed out",
        "Provider request timed out",
    ]


@pytest.mark.asyncio
async def test_analyze_story_uses_empty_model_when_all_fail_and_no_model_requested(monkeypatch):
    settings = make_settings()

    async def fake_answer_single_question(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("app.service.answer_single_question", fake_answer_single_question)

    model, results = await analyze_story(
        story_sketch="sketch",
        question_preamble=None,
        questions=["Q1"],
        provider="openai",
        model=None,
        reasoning_effort="medium",
        settings=settings,
    )

    assert model == ""
    assert results[0].error == "Provider request failed"
