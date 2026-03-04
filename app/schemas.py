from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

ProviderName = Literal["openai", "anthropic", "google"]
ReasoningEffort = Literal["none", "minimal", "low", "medium", "high", "xhigh"]
QuestionRunStatus = Literal["queued", "running", "completed", "failed"]
AnalyzeJobStatus = Literal["queued", "running", "completed", "completed_with_errors"]


class AnalyzeRequest(BaseModel):
    story_sketch: str = Field(min_length=1)
    questions: list[str] = Field(min_length=1)
    provider: ProviderName = "openai"
    model: str | None = None
    reasoning_effort: ReasoningEffort | None = "medium"

    @field_validator("story_sketch")
    @classmethod
    def validate_story_sketch(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("story_sketch cannot be empty")
        return cleaned

    @field_validator("questions")
    @classmethod
    def validate_questions(cls, values: list[str]) -> list[str]:
        cleaned = [item.strip() for item in values if item.strip()]
        if not cleaned:
            raise ValueError("questions must include at least one non-empty value")
        return cleaned

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


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
