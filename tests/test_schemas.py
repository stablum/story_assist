import pytest
from pydantic import ValidationError

from app.schemas import (
    AnalyzeRequest,
    MAX_MODEL_NAME_CHARS,
    MAX_QUESTION_CHARS,
    MAX_QUESTIONS,
)


def make_payload(**overrides):
    payload = {
        "story_sketch": "A draft story about local politics.",
        "questions": ["What happened?"],
        "provider": "openai",
    }
    payload.update(overrides)
    return payload


def test_analyze_request_trims_story_and_model():
    req = AnalyzeRequest(
        **make_payload(
            story_sketch="   A sketch with spaces.   ",
            model="  gpt-5.2  ",
        )
    )

    assert req.story_sketch == "A sketch with spaces."
    assert req.model == "gpt-5.2"


def test_analyze_request_blank_story_is_rejected():
    with pytest.raises(ValidationError, match="story_sketch"):
        AnalyzeRequest(**make_payload(story_sketch="   "))


def test_analyze_request_blank_preamble_becomes_none():
    req = AnalyzeRequest(**make_payload(question_preamble="   "))
    assert req.question_preamble is None


def test_analyze_request_questions_are_trimmed_and_filtered():
    req = AnalyzeRequest(
        **make_payload(
            questions=["  First?  ", "", "   ", "Second?"],
        )
    )

    assert req.questions == ["First?", "Second?"]


def test_analyze_request_requires_at_least_one_non_empty_question():
    with pytest.raises(ValidationError, match="questions"):
        AnalyzeRequest(**make_payload(questions=["   ", ""]))


def test_analyze_request_rejects_too_many_questions():
    with pytest.raises(ValidationError, match="questions"):
        AnalyzeRequest(
            **make_payload(
                questions=[f"Q{i}" for i in range(MAX_QUESTIONS + 1)],
            )
        )


def test_analyze_request_rejects_question_over_max_length():
    too_long = "x" * (MAX_QUESTION_CHARS + 1)

    with pytest.raises(ValidationError, match="question"):
        AnalyzeRequest(**make_payload(questions=[too_long]))


def test_analyze_request_blank_model_becomes_none():
    req = AnalyzeRequest(**make_payload(model="   "))
    assert req.model is None


def test_analyze_request_rejects_model_over_max_length():
    too_long = "m" * (MAX_MODEL_NAME_CHARS + 1)

    with pytest.raises(ValidationError, match="model"):
        AnalyzeRequest(**make_payload(model=too_long))


def test_analyze_request_default_reasoning_effort_is_medium():
    req = AnalyzeRequest(**make_payload())
    assert req.reasoning_effort == "medium"
