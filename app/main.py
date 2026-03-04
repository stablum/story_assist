from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.jobs import JobCapacityError, JobManager
from app.providers import list_provider_models, resolve_model
from app.schemas import (
    AnalyzeJobCreateResponse,
    AnalyzeJobProgressResponse,
    AnalyzeRequest,
    AnalyzeResponse,
    ModelOptionsResponse,
    ProviderName,
)
from app.security import (
    Principal,
    RateLimitExceededError,
    SlidingWindowRateLimiter,
    require_principal,
)
from app.service import analyze_story

settings = get_settings()

app = FastAPI(title="Story Assist", version="0.1.0")
job_manager = JobManager(
    max_jobs=settings.max_jobs_kept,
    max_active_jobs=settings.max_active_jobs,
    max_concurrent_jobs=settings.max_concurrent_jobs,
    max_parallel_questions_per_job=settings.max_parallel_questions_per_job,
    max_global_parallel_questions=settings.max_global_parallel_questions,
)
job_creation_limiter = SlidingWindowRateLimiter(
    limit=settings.max_job_creations_per_minute,
    window_seconds=60,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )
    return response


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze(
    request: AnalyzeRequest,
    _: Principal = Depends(require_principal),
) -> AnalyzeResponse:
    if not request.questions:
        raise HTTPException(status_code=400, detail="At least one question is required")

    settings = get_settings()
    resolved_model, results = await analyze_story(
        story_sketch=request.story_sketch,
        question_preamble=request.question_preamble,
        questions=request.questions,
        provider=request.provider,
        model=request.model,
        reasoning_effort=request.reasoning_effort,
        settings=settings,
    )

    return AnalyzeResponse(
        provider=request.provider,
        model=resolved_model,
        results=results,
    )


@app.get("/api/model-options", response_model=ModelOptionsResponse)
async def model_options(
    provider: ProviderName = "openai",
    _: Principal = Depends(require_principal),
) -> ModelOptionsResponse:
    settings = get_settings()
    models = await list_provider_models(provider, settings)

    return ModelOptionsResponse(
        provider=provider,
        default_model=resolve_model(provider, None),
        models=models,
    )


@app.post("/api/analyze/jobs", response_model=AnalyzeJobCreateResponse)
async def create_analyze_job(
    request: AnalyzeRequest,
    principal: Principal = Depends(require_principal),
) -> AnalyzeJobCreateResponse:
    settings = get_settings()

    try:
        job_creation_limiter.check(principal.principal_id)
        return await job_manager.create_job(request, settings, owner_id=principal.principal_id)
    except RateLimitExceededError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except JobCapacityError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc


@app.get("/api/analyze/jobs/{job_id}", response_model=AnalyzeJobProgressResponse)
async def analyze_job_progress(
    job_id: str,
    principal: Principal = Depends(require_principal),
) -> AnalyzeJobProgressResponse:
    progress = await job_manager.get_job_progress(job_id, owner_id=principal.principal_id)
    if progress is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return progress


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


static_dir = Path(__file__).resolve().parent.parent / "static"
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
