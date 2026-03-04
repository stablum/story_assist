from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_analyze_valid_request(monkeypatch):
    captured_kwargs = {}

    async def fake_analyze_story(**kwargs):
        captured_kwargs.update(kwargs)
        questions = kwargs["questions"]
        return "fake-model", [
            {
                "question": question,
                "answer": f"Answer for: {question}",
                "error": None,
            }
            for question in questions
        ]

    monkeypatch.setattr("app.main.analyze_story", fake_analyze_story)

    response = client.post(
        "/api/analyze",
        json={
            "story_sketch": "A factory reopens in a small town.",
            "question_preamble": "Use an investigative tone and cite official sources.",
            "questions": ["What are economic risks?", "Who benefits politically?"],
            "provider": "openai",
            "reasoning_effort": "high",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "openai"
    assert payload["model"] == "fake-model"
    assert len(payload["results"]) == 2
    assert payload["results"][0]["error"] is None
    assert captured_kwargs["reasoning_effort"] == "high"
    assert captured_kwargs["question_preamble"] == "Use an investigative tone and cite official sources."


def test_analyze_rejects_empty_question_list():
    response = client.post(
        "/api/analyze",
        json={
            "story_sketch": "A sketch",
            "questions": [],
            "provider": "openai",
        },
    )

    assert response.status_code == 422


def test_analyze_rejects_invalid_reasoning_effort():
    response = client.post(
        "/api/analyze",
        json={
            "story_sketch": "A sketch",
            "questions": ["What next?"],
            "provider": "openai",
            "reasoning_effort": "turbo",
        },
    )

    assert response.status_code == 422


def test_model_options_route(monkeypatch):
    async def fake_list_provider_models(provider, settings):
        assert provider == "openai"
        return ["gpt-5.2", "gpt-5.3-chat-latest"]

    monkeypatch.setattr("app.main.list_provider_models", fake_list_provider_models)

    response = client.get("/api/model-options", params={"provider": "openai"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "openai"
    assert payload["default_model"] == "gpt-5.2"
    assert payload["models"] == ["gpt-5.2", "gpt-5.3-chat-latest"]


def test_create_analyze_job_route(monkeypatch):
    async def fake_create_job(request, settings):
        assert request.provider == "openai"
        assert request.question_preamble == "Prioritize policy and labor impact."
        return {"job_id": "job123", "status": "queued"}

    monkeypatch.setattr("app.main.job_manager.create_job", fake_create_job)

    response = client.post(
        "/api/analyze/jobs",
        json={
            "story_sketch": "A factory reopens in a small town.",
            "question_preamble": "Prioritize policy and labor impact.",
            "questions": ["What are economic risks?"],
            "provider": "openai",
            "reasoning_effort": "medium",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_id"] == "job123"
    assert payload["status"] == "queued"


def test_analyze_job_progress_route(monkeypatch):
    async def fake_get_job_progress(job_id):
        assert job_id == "job123"
        return {
            "job_id": "job123",
            "status": "running",
            "provider": "openai",
            "model": "gpt-5.2",
            "reasoning_effort": "high",
            "started_at": 1000.0,
            "finished_at": None,
            "total_questions": 2,
            "completed_questions": 1,
            "failed_questions": 0,
            "progress_percent": 50,
            "items": [
                {
                    "index": 0,
                    "question": "Q1",
                    "status": "completed",
                    "started_at": 1000.0,
                    "finished_at": 1001.2,
                    "elapsed_seconds": 1.2,
                    "answer": "A1",
                    "error": None,
                },
                {
                    "index": 1,
                    "question": "Q2",
                    "status": "running",
                    "started_at": 1000.1,
                    "finished_at": None,
                    "elapsed_seconds": 0.7,
                    "answer": "",
                    "error": None,
                },
            ],
        }

    monkeypatch.setattr("app.main.job_manager.get_job_progress", fake_get_job_progress)

    response = client.get("/api/analyze/jobs/job123")
    assert response.status_code == 200
    payload = response.json()
    assert payload["job_id"] == "job123"
    assert payload["progress_percent"] == 50
    assert len(payload["items"]) == 2


def test_analyze_job_progress_not_found(monkeypatch):
    async def fake_get_job_progress(job_id):
        return None

    monkeypatch.setattr("app.main.job_manager.get_job_progress", fake_get_job_progress)

    response = client.get("/api/analyze/jobs/missing")
    assert response.status_code == 404


def test_static_index_is_served():
    response = client.get("/")
    assert response.status_code == 200
    assert "Story Assist Desk" in response.text




