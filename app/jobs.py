from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import time
from uuid import uuid4

from app.config import Settings
from app.providers import resolve_model
from app.schemas import (
    AnalyzeJobCreateResponse,
    AnalyzeJobProgressResponse,
    AnalyzeJobQuestionProgress,
    AnalyzeJobStatus,
    AnalyzeRequest,
    ProviderName,
    QuestionRunStatus,
    ReasoningEffort,
)
from app.service import answer_single_question


@dataclass
class JobItem:
    index: int
    question: str
    status: QuestionRunStatus = "queued"
    started_at: float | None = None
    finished_at: float | None = None
    answer: str = ""
    error: str | None = None


@dataclass
class JobRecord:
    job_id: str
    status: AnalyzeJobStatus
    provider: ProviderName
    model: str
    reasoning_effort: ReasoningEffort | None
    started_at: float
    finished_at: float | None
    items: list[JobItem] = field(default_factory=list)


class JobManager:
    def __init__(self, *, max_jobs: int = 100) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._max_jobs = max_jobs
        self._lock = asyncio.Lock()

    async def create_job(
        self,
        request: AnalyzeRequest,
        settings: Settings,
    ) -> AnalyzeJobCreateResponse:
        job_id = uuid4().hex
        record = JobRecord(
            job_id=job_id,
            status="queued",
            provider=request.provider,
            model=resolve_model(request.provider, request.model),
            reasoning_effort=request.reasoning_effort,
            started_at=time.time(),
            finished_at=None,
            items=[
                JobItem(index=index, question=question)
                for index, question in enumerate(request.questions)
            ],
        )

        async with self._lock:
            self._prune_jobs_unlocked()
            self._jobs[job_id] = record

        asyncio.create_task(self._run_job(job_id, request, settings))
        return AnalyzeJobCreateResponse(job_id=job_id, status=record.status)

    async def get_job_progress(self, job_id: str) -> AnalyzeJobProgressResponse | None:
        async with self._lock:
            record = self._jobs.get(job_id)
            if not record:
                return None
            return self._to_progress_response(record)

    async def _run_job(self, job_id: str, request: AnalyzeRequest, settings: Settings) -> None:
        await self._set_job_status(job_id, "running")

        try:
            tasks = [
                self._run_question(
                    job_id=job_id,
                    index=index,
                    question=question,
                    request=request,
                    settings=settings,
                )
                for index, question in enumerate(request.questions)
            ]
            await asyncio.gather(*tasks)

            async with self._lock:
                record = self._jobs.get(job_id)
                if not record:
                    return

                failed = sum(1 for item in record.items if item.status == "failed")
                record.finished_at = time.time()
                record.status = "completed_with_errors" if failed else "completed"
        except Exception as exc:
            async with self._lock:
                record = self._jobs.get(job_id)
                if not record:
                    return
                record.finished_at = time.time()
                record.status = "completed_with_errors"
                for item in record.items:
                    if item.status in ("queued", "running"):
                        item.status = "failed"
                        item.error = str(exc)
                        if item.finished_at is None:
                            item.finished_at = time.time()

    async def _run_question(
        self,
        *,
        job_id: str,
        index: int,
        question: str,
        request: AnalyzeRequest,
        settings: Settings,
    ) -> None:
        await self._mark_item_running(job_id, index)

        try:
            _, resolved_model, answer = await answer_single_question(
                story_sketch=request.story_sketch,
                question=question,
                provider=request.provider,
                model=request.model,
                reasoning_effort=request.reasoning_effort,
                settings=settings,
            )
        except Exception as exc:
            await self._mark_item_failed(job_id, index, str(exc))
            return

        await self._mark_item_completed(job_id, index, answer, resolved_model)

    async def _set_job_status(self, job_id: str, status: AnalyzeJobStatus) -> None:
        async with self._lock:
            record = self._jobs.get(job_id)
            if record:
                record.status = status

    async def _mark_item_running(self, job_id: str, index: int) -> None:
        async with self._lock:
            record = self._jobs.get(job_id)
            if not record:
                return
            item = record.items[index]
            item.status = "running"
            item.started_at = time.time()

    async def _mark_item_failed(self, job_id: str, index: int, error: str) -> None:
        async with self._lock:
            record = self._jobs.get(job_id)
            if not record:
                return
            item = record.items[index]
            item.status = "failed"
            item.error = error
            if item.started_at is None:
                item.started_at = time.time()
            item.finished_at = time.time()

    async def _mark_item_completed(
        self,
        job_id: str,
        index: int,
        answer: str,
        resolved_model: str,
    ) -> None:
        async with self._lock:
            record = self._jobs.get(job_id)
            if not record:
                return
            item = record.items[index]
            item.status = "completed"
            item.answer = answer
            if item.started_at is None:
                item.started_at = time.time()
            item.finished_at = time.time()
            record.model = resolved_model

    def _to_progress_response(self, record: JobRecord) -> AnalyzeJobProgressResponse:
        completed_count = sum(1 for item in record.items if item.status == "completed")
        failed_count = sum(1 for item in record.items if item.status == "failed")
        done_count = completed_count + failed_count
        total = len(record.items)
        progress_percent = int((done_count / total) * 100) if total else 100

        response_items = [
            AnalyzeJobQuestionProgress(
                index=item.index,
                question=item.question,
                status=item.status,
                started_at=item.started_at,
                finished_at=item.finished_at,
                elapsed_seconds=self._elapsed_seconds(item),
                answer=item.answer,
                error=item.error,
            )
            for item in sorted(record.items, key=lambda value: value.index)
        ]

        return AnalyzeJobProgressResponse(
            job_id=record.job_id,
            status=record.status,
            provider=record.provider,
            model=record.model,
            reasoning_effort=record.reasoning_effort,
            started_at=record.started_at,
            finished_at=record.finished_at,
            total_questions=total,
            completed_questions=completed_count,
            failed_questions=failed_count,
            progress_percent=progress_percent,
            items=response_items,
        )

    def _elapsed_seconds(self, item: JobItem) -> float | None:
        if item.started_at is None:
            return None
        end_time = item.finished_at or time.time()
        return round(max(0.0, end_time - item.started_at), 2)

    def _prune_jobs_unlocked(self) -> None:
        overflow = len(self._jobs) - self._max_jobs + 1
        if overflow <= 0:
            return

        for job_id in sorted(self._jobs, key=lambda key: self._jobs[key].started_at)[:overflow]:
            del self._jobs[job_id]
