from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.jobs import JobManager
from app.providers import list_provider_models, resolve_model
from app.schemas import (
    AnalyzeJobCreateResponse,
    AnalyzeJobProgressResponse,
    AnalyzeRequest,
    AnalyzeResponse,
    ModelOptionsResponse,
    ProviderName,
)
from app.service import analyze_story

app = FastAPI(title="Story Assist", version="0.1.0")
job_manager = JobManager()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    if not request.questions:
        raise HTTPException(status_code=400, detail="At least one question is required")

    settings = get_settings()
    resolved_model, results = await analyze_story(
        story_sketch=request.story_sketch,
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
async def model_options(provider: ProviderName = "openai") -> ModelOptionsResponse:
    settings = get_settings()
    models = await list_provider_models(provider, settings)
    return ModelOptionsResponse(
        provider=provider,
        default_model=resolve_model(provider, None),
        models=models,
    )


@app.post("/api/analyze/jobs", response_model=AnalyzeJobCreateResponse)
async def create_analyze_job(request: AnalyzeRequest) -> AnalyzeJobCreateResponse:
    settings = get_settings()
    return await job_manager.create_job(request, settings)


@app.get("/api/analyze/jobs/{job_id}", response_model=AnalyzeJobProgressResponse)
async def analyze_job_progress(job_id: str) -> AnalyzeJobProgressResponse:
    progress = await job_manager.get_job_progress(job_id)
    if progress is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return progress


static_dir = Path(__file__).resolve().parent.parent / "static"
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
