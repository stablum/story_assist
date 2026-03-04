from __future__ import annotations

import asyncio
from functools import lru_cache
from pathlib import Path

from app.config import Settings
from app.providers import run_provider_prompt
from app.schemas import AnswerItem, ProviderName, ReasoningEffort

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


@lru_cache(maxsize=16)
def load_template(template_name: str) -> str:
    template_path = TEMPLATES_DIR / template_name
    return template_path.read_text(encoding="utf-8").strip()


def build_question_block(question: str, question_preamble: str | None) -> str:
    if not question_preamble:
        return load_template("question_block_plain.txt").format(question=question)
    return load_template("question_block_with_preamble.txt").format(
        question_preamble=question_preamble,
        question=question,
    )


async def answer_single_question(
    *,
    story_sketch: str,
    question: str,
    question_preamble: str | None,
    provider: ProviderName,
    model: str | None,
    reasoning_effort: ReasoningEffort | None,
    settings: Settings,
) -> tuple[str, str, str]:
    prompt = load_template("research_prompt.txt").format(
        story_sketch=story_sketch,
        question_block=build_question_block(question, question_preamble),
    )
    resolved_model, answer = await run_provider_prompt(
        provider=provider,
        settings=settings,
        prompt=prompt,
        model=model,
        reasoning_effort=reasoning_effort,
    )
    return question, resolved_model, answer


async def analyze_story(
    *,
    story_sketch: str,
    question_preamble: str | None,
    questions: list[str],
    provider: ProviderName,
    model: str | None,
    reasoning_effort: ReasoningEffort | None,
    settings: Settings,
) -> tuple[str, list[AnswerItem]]:
    tasks = [
        answer_single_question(
            story_sketch=story_sketch,
            question=question,
            question_preamble=question_preamble,
            provider=provider,
            model=model,
            reasoning_effort=reasoning_effort,
            settings=settings,
        )
        for question in questions
    ]

    results: list[AnswerItem] = []
    resolved_model = model or ""

    task_outputs = await asyncio.gather(*tasks, return_exceptions=True)
    for question, output in zip(questions, task_outputs):
        if isinstance(output, Exception):
            results.append(
                AnswerItem(
                    question=question,
                    answer="",
                    error=str(output),
                )
            )
            continue

        _, answer_model, answer_text = output
        resolved_model = answer_model
        results.append(AnswerItem(question=question, answer=answer_text, error=None))

    if not resolved_model:
        resolved_model = model or ""

    return resolved_model, results
