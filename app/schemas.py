from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

ProviderName = Literal["openai", "anthropic", "google"]
ReasoningEffort = Literal["none", "minimal", "low", "medium", "high", "xhigh"]


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
