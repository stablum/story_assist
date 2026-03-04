from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

ProviderName = Literal["openai", "anthropic", "google"]
ReasoningEffort = Literal["none", "minimal", "low", "medium", "high", "xhigh"]
QuestionRunStatus = Literal["queued", "running", "completed", "failed"]
AnalyzeJobStatus = Literal["queued", "running", "completed", "completed_with_errors"]

MAX_STORY_SKETCH_CHARS = 20_000
MAX_QUESTION_PREAMBLE_CHARS = 4_000
MAX_QUESTIONS = 12
MAX_QUESTION_CHARS = 600
MAX_MODEL_NAME_CHARS = 120


class AnalyzeRequest(BaseModel):
    story_sketch: str = Field(min_length=1, max_length=MAX_STORY_SKETCH_CHARS)
    question_preamble: str | None = Field(default=None, max_length=MAX_QUESTION_PREAMBLE_CHARS)
    questions: list[str] = Field(min_length=1, max_length=MAX_QUESTIONS)
    provider: ProviderName = "openai"
    model: str | None = Field(default=None, max_length=MAX_MODEL_NAME_CHARS)
    reasoning_effort: ReasoningEffort | None = "medium"

    @field_validator("story_sketch")
    @classmethod
    def validate_story_sketch(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("story_sketch cannot be empty")
        if len(cleaned) > MAX_STORY_SKETCH_CHARS:
            raise ValueError(f"story_sketch must be <= {MAX_STORY_SKETCH_CHARS} characters")
        return cleaned

    @field_validator("question_preamble")
    @classmethod
    def validate_question_preamble(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        if len(cleaned) > MAX_QUESTION_PREAMBLE_CHARS:
            raise ValueError(
                f"question_preamble must be <= {MAX_QUESTION_PREAMBLE_CHARS} characters"
            )
        return cleaned

    @field_validator("questions")
    @classmethod
    def validate_questions(cls, values: list[str]) -> list[str]:
        cleaned = [item.strip() for item in values if item.strip()]
        if not cleaned:
            raise ValueError("questions must include at least one non-empty value")
        if len(cleaned) > MAX_QUESTIONS:
            raise ValueError(f"questions must contain at most {MAX_QUESTIONS} items")

        for item in cleaned:
            if len(item) > MAX_QUESTION_CHARS:
                raise ValueError(f"each question must be <= {MAX_QUESTION_CHARS} characters")
        return cleaned

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        if len(cleaned) > MAX_MODEL_NAME_CHARS:
            raise ValueError(f"model must be <= {MAX_MODEL_NAME_CHARS} characters")
        return cleaned


class AnswerItem(BaseModel):
    question: str
    answer: str
    error: str | None = None


class AnalyzeResponse(BaseModel):
    provider: ProviderName
    model: str
    results: list[AnswerItem]


class ModelOptionsResponse(BaseModel):
    provider: ProviderName
    default_model: str
    models: list[str]


class AnalyzeJobCreateResponse(BaseModel):
    job_id: str
    status: AnalyzeJobStatus


class AnalyzeJobQuestionProgress(BaseModel):
    index: int
    question: str
    status: QuestionRunStatus
    started_at: float | None = None
    finished_at: float | None = None
    elapsed_seconds: float | None = None
    answer: str = ""
    error: str | None = None


class AnalyzeJobProgressResponse(BaseModel):
    job_id: str
    status: AnalyzeJobStatus
    provider: ProviderName
    model: str
    reasoning_effort: ReasoningEffort | None = None
    started_at: float
    finished_at: float | None = None
    total_questions: int
    completed_questions: int
    failed_questions: int
    progress_percent: int
    items: list[AnalyzeJobQuestionProgress]
