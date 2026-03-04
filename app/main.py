from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.schemas import AnalyzeRequest, AnalyzeResponse
from app.service import analyze_story

app = FastAPI(title="Story Assist", version="0.1.0")

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
        settings=settings,
    )

    return AnalyzeResponse(
        provider=request.provider,
        model=resolved_model,
        results=results,
    )


static_dir = Path(__file__).resolve().parent.parent / "static"
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")