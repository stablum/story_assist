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


def test_static_index_is_served():
    response = client.get("/")
    assert response.status_code == 200
    assert "Story Assist Desk" in response.text
