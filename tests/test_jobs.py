import asyncio
import time

import pytest

from app.jobs import JobCapacityError, JobItem, JobManager, JobRecord
from app.schemas import AnalyzeRequest
from tests.utils import make_settings


def make_request(**overrides):
    payload = {
        "story_sketch": "A story sketch",
        "questions": ["Q1", "Q2"],
        "provider": "openai",
        "reasoning_effort": "medium",
    }
    payload.update(overrides)
    return AnalyzeRequest(**payload)


@pytest.mark.asyncio
async def test_create_job_stores_owner_and_enqueues_background_task(monkeypatch):
    manager = JobManager()
    settings = make_settings()
    request = make_request()
    created_tasks = []

    def fake_create_task(coro):
        created_tasks.append(coro)
        coro.close()
        return object()

    monkeypatch.setattr("app.jobs.asyncio.create_task", fake_create_task)

    response = await manager.create_job(request, settings, owner_id="owner-1")

    assert response.status == "queued"
    assert response.job_id in manager._jobs
    assert len(created_tasks) == 1

    record = manager._jobs[response.job_id]
    assert record.owner_id == "owner-1"
    assert record.provider == "openai"
    assert record.model == "gpt-5.2"
    assert [item.question for item in record.items] == ["Q1", "Q2"]


@pytest.mark.asyncio
async def test_create_job_enforces_active_job_limit(monkeypatch):
    manager = JobManager(max_active_jobs=1)
    settings = make_settings()
    request = make_request()

    def fake_create_task(coro):
        coro.close()
        return object()

    monkeypatch.setattr("app.jobs.asyncio.create_task", fake_create_task)

    await manager.create_job(request, settings, owner_id="owner-1")

    with pytest.raises(JobCapacityError, match="Too many active jobs"):
        await manager.create_job(request, settings, owner_id="owner-2")


@pytest.mark.asyncio
async def test_get_job_progress_is_owner_scoped(monkeypatch):
    manager = JobManager()
    settings = make_settings()
    request = make_request(questions=["Q1"])

    def fake_create_task(coro):
        coro.close()
        return object()

    monkeypatch.setattr("app.jobs.asyncio.create_task", fake_create_task)

    response = await manager.create_job(request, settings, owner_id="owner-1")

    assert await manager.get_job_progress(response.job_id, owner_id="owner-2") is None

    progress = await manager.get_job_progress(response.job_id, owner_id="owner-1")
    assert progress is not None
    assert progress.job_id == response.job_id
    assert progress.total_questions == 1


@pytest.mark.asyncio
async def test_run_question_marks_item_completed_and_updates_model(monkeypatch):
    manager = JobManager()
    settings = make_settings()
    request = make_request(questions=["Q1"])
    record = JobRecord(
        job_id="job1",
        owner_id="owner-1",
        status="running",
        provider="openai",
        model="gpt-5.2",
        reasoning_effort="medium",
        started_at=time.time(),
        finished_at=None,
        items=[JobItem(index=0, question="Q1")],
    )
    manager._jobs[record.job_id] = record

    async def fake_answer_single_question(**kwargs):
        return "Q1", "gpt-updated", "final answer"

    monkeypatch.setattr("app.jobs.answer_single_question", fake_answer_single_question)

    await manager._run_question(
        job_id="job1",
        index=0,
        question="Q1",
        request=request,
        settings=settings,
        per_job_semaphore=asyncio.Semaphore(1),
    )

    item = record.items[0]
    assert item.status == "completed"
    assert item.answer == "final answer"
    assert item.error is None
    assert record.model == "gpt-updated"


@pytest.mark.asyncio
async def test_run_question_marks_item_failed_on_provider_error(monkeypatch):
    manager = JobManager()
    settings = make_settings()
    request = make_request(questions=["Q1"])
    record = JobRecord(
        job_id="job1",
        owner_id="owner-1",
        status="running",
        provider="openai",
        model="gpt-5.2",
        reasoning_effort="medium",
        started_at=time.time(),
        finished_at=None,
        items=[JobItem(index=0, question="Q1")],
    )
    manager._jobs[record.job_id] = record

    async def fake_answer_single_question(**kwargs):
        raise TimeoutError()

    monkeypatch.setattr("app.jobs.answer_single_question", fake_answer_single_question)

    await manager._run_question(
        job_id="job1",
        index=0,
        question="Q1",
        request=request,
        settings=settings,
        per_job_semaphore=asyncio.Semaphore(1),
    )

    item = record.items[0]
    assert item.status == "failed"
    assert item.error == "Provider request timed out"
    assert item.finished_at is not None


@pytest.mark.asyncio
async def test_run_job_sets_completed_status_when_all_questions_complete(monkeypatch):
    manager = JobManager()
    settings = make_settings()
    request = make_request(questions=["Q1", "Q2"])
    record = JobRecord(
        job_id="job1",
        owner_id="owner-1",
        status="queued",
        provider="openai",
        model="gpt-5.2",
        reasoning_effort="medium",
        started_at=time.time(),
        finished_at=None,
        items=[JobItem(index=0, question="Q1"), JobItem(index=1, question="Q2")],
    )
    manager._jobs[record.job_id] = record

    async def fake_run_question(*, job_id, index, question, request, settings, per_job_semaphore):
        await manager._mark_item_running(job_id, index)
        await manager._mark_item_completed(job_id, index, f"answer-{question}", "gpt-updated")

    monkeypatch.setattr(manager, "_run_question", fake_run_question)

    await manager._run_job("job1", request, settings)

    assert record.status == "completed"
    assert record.finished_at is not None
    assert [item.status for item in record.items] == ["completed", "completed"]


@pytest.mark.asyncio
async def test_run_job_marks_remaining_items_failed_on_unhandled_error(monkeypatch):
    manager = JobManager()
    settings = make_settings()
    request = make_request(questions=["Q1", "Q2"])
    record = JobRecord(
        job_id="job1",
        owner_id="owner-1",
        status="queued",
        provider="openai",
        model="gpt-5.2",
        reasoning_effort="medium",
        started_at=time.time(),
        finished_at=None,
        items=[JobItem(index=0, question="Q1"), JobItem(index=1, question="Q2")],
    )
    manager._jobs[record.job_id] = record

    async def fake_run_question(*, job_id, index, question, request, settings, per_job_semaphore):
        raise RuntimeError("boom")

    monkeypatch.setattr(manager, "_run_question", fake_run_question)

    await manager._run_job("job1", request, settings)

    assert record.status == "completed_with_errors"
    assert record.finished_at is not None
    assert [item.status for item in record.items] == ["failed", "failed"]
    assert all(item.error == "Provider request failed" for item in record.items)


def test_prune_jobs_removes_oldest_entries():
    manager = JobManager(max_jobs=2)
    manager._jobs = {
        "oldest": JobRecord(
            job_id="oldest",
            owner_id="owner-1",
            status="completed",
            provider="openai",
            model="gpt-5.2",
            reasoning_effort="medium",
            started_at=1.0,
            finished_at=2.0,
            items=[],
        ),
        "newest": JobRecord(
            job_id="newest",
            owner_id="owner-1",
            status="completed",
            provider="openai",
            model="gpt-5.2",
            reasoning_effort="medium",
            started_at=2.0,
            finished_at=3.0,
            items=[],
        ),
    }

    manager._prune_jobs_unlocked()

    assert set(manager._jobs) == {"newest"}


def test_to_progress_response_computes_counts_and_percentages():
    manager = JobManager()
    record = JobRecord(
        job_id="job1",
        owner_id="owner-1",
        status="running",
        provider="openai",
        model="gpt-5.2",
        reasoning_effort="high",
        started_at=100.0,
        finished_at=None,
        items=[
            JobItem(index=0, question="Q1", status="completed", started_at=100.0, finished_at=101.0),
            JobItem(index=1, question="Q2", status="failed", started_at=100.5, finished_at=101.5, error="err"),
            JobItem(index=2, question="Q3", status="running", started_at=101.0),
        ],
    )

    progress = manager._to_progress_response(record)

    assert progress.total_questions == 3
    assert progress.completed_questions == 1
    assert progress.failed_questions == 1
    assert progress.progress_percent == 66
    assert [item.index for item in progress.items] == [0, 1, 2]

