from __future__ import annotations

import asyncio

from app.config import Settings
from app.providers import run_provider_prompt
from app.schemas import AnswerItem, ProviderName, ReasoningEffort

PROMPT_TEMPLATE = """
You are a research assistant for journalists and fiction/non-fiction story writers.
Use web search to verify facts before answering.

Story sketch:
{story_sketch}

Question:
{question}

Instructions:
- Answer in 2-5 concise paragraphs.
- Include concrete names, places, dates, and useful context.
- If facts are uncertain, say what needs verification.
- Add a short source list with direct URLs when possible.
""".strip()


async def answer_single_question(
    *,
    story_sketch: str,
    question: str,
    provider: ProviderName,
    model: str | None,
    reasoning_effort: ReasoningEffort | None,
    settings: Settings,
) -> tuple[str, str, str]:
    prompt = PROMPT_TEMPLATE.format(story_sketch=story_sketch, question=question)
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
