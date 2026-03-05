from fastapi.testclient import TestClient
import pytest

from app.jobs import JobCapacityError
from app.main import app, job_creation_limiter
from app.security import RateLimitExceededError

client = TestClient(app)
AUTH_HEADERS = {"Authorization": "Bearer test-token"}


@pytest.fixture(autouse=True)
def clear_rate_limiter_state():
    job_creation_limiter._events.clear()


def sample_request_body(**overrides):
    payload = {
        "story_sketch": "A sketch",
        "questions": ["What happened?"],
        "provider": "openai",
    }
    payload.update(overrides)
    return payload


def test_health_endpoint_is_public_and_returns_ok():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_security_headers_are_added_to_responses():
    response = client.get("/api/health")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["cross-origin-resource-policy"] == "same-origin"
    assert "default-src 'self'" in response.headers["content-security-policy"]


def test_model_options_requires_authentication():
    response = client.get("/api/model-options")
    assert response.status_code == 401


def test_endpoints_reject_invalid_bearer_token():
    response = client.get(
        "/api/model-options",
        headers={"Authorization": "Bearer wrong-token"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid token"


def test_model_options_rejects_invalid_provider_value():
    response = client.get(
        "/api/model-options",
        headers=AUTH_HEADERS,
        params={"provider": "invalid-provider"},
    )

    assert response.status_code == 422


def test_create_job_returns_429_when_rate_limited(monkeypatch):
    def fake_check(key):
        raise RateLimitExceededError("Too many requests")

    monkeypatch.setattr("app.main.job_creation_limiter.check", fake_check)

    response = client.post(
        "/api/analyze/jobs",
        headers=AUTH_HEADERS,
        json=sample_request_body(),
    )

    assert response.status_code == 429
    assert response.json()["detail"] == "Too many requests"


def test_create_job_returns_429_when_capacity_is_exceeded(monkeypatch):
    def fake_check(key):
        return None

    async def fake_create_job(request, settings, owner_id):
        raise JobCapacityError("Queue full")

    monkeypatch.setattr("app.main.job_creation_limiter.check", fake_check)
    monkeypatch.setattr("app.main.job_manager.create_job", fake_create_job)

    response = client.post(
        "/api/analyze/jobs",
        headers=AUTH_HEADERS,
        json=sample_request_body(),
    )

    assert response.status_code == 429
    assert response.json()["detail"] == "Queue full"


def test_job_progress_requires_authentication():
    response = client.get("/api/analyze/jobs/job123")
    assert response.status_code == 401
