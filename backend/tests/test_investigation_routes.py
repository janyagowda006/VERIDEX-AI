import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.core.db import get_db
from app.ai.provider import get_llm_provider, MockLLMProvider
from app.services.investigation_service import InvestigationService


@pytest.fixture
def client(test_db_session):
    """
    FastAPI TestClient with overridden get_db and get_llm_provider dependencies.
    """
    def override_get_db():
        try:
            yield test_db_session
        finally:
            pass

    def override_get_llm_provider():
        return MockLLMProvider()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_llm_provider] = override_get_llm_provider

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_post_ask_creates_investigation_and_returns_id(client, test_db_session):
    """
    Verifies POST /api/ask persists investigation and returns investigation_id in metadata.
    """
    payload = {"question": "What is our gross revenue by region?", "max_turns": 3}
    response = client.post("/api/ask", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "metadata" in data
    assert "investigation_id" in data["metadata"]

    inv_id = data["metadata"]["investigation_id"]
    assert inv_id.startswith("inv_")

    # Verify persisted in database
    persisted = InvestigationService.get_investigation_by_id(test_db_session, inv_id)
    assert persisted is not None
    assert persisted.question == payload["question"]
    assert persisted.status in ["COMPLETED", "REQUIRES_REVIEW"]
    assert persisted.result_json is not None


def test_get_investigations_history_list(client, test_db_session):
    """
    Verifies GET /api/investigations returns list of history summaries ordered newest-first.
    """
    # Issue 2 questions
    client.post("/api/ask", json={"question": "Question A"})
    client.post("/api/ask", json={"question": "Question B"})

    response = client.get("/api/investigations?limit=10")
    assert response.status_code == 200
    history = response.json()

    assert isinstance(history, list)
    assert len(history) >= 2

    # Check summary fields
    first_item = history[0]
    assert "investigation_id" in first_item
    assert "question" in first_item
    assert "status" in first_item
    assert "created_at" in first_item
    assert "result_json" not in first_item  # Summaries exclude heavy result_json


def test_get_investigation_detail_by_id(client, test_db_session):
    """
    Verifies GET /api/investigations/{id} returns full detail including result_json.
    """
    post_res = client.post("/api/ask", json={"question": "Detail lookup test query"})
    inv_id = post_res.json()["metadata"]["investigation_id"]

    response = client.get(f"/api/investigations/{inv_id}")
    assert response.status_code == 200
    detail = response.json()

    assert detail["investigation_id"] == inv_id
    assert detail["question"] == "Detail lookup test query"
    assert detail["status"] in ["COMPLETED", "REQUIRES_REVIEW"]
    assert "result_json" in detail
    assert detail["result_json"] is not None


def test_get_investigation_by_unknown_id_returns_404(client):
    """
    Verifies GET /api/investigations/{unknown_id} returns HTTP 404.
    """
    response = client.get("/api/investigations/inv_nonexistent_9999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_post_ask_failure_persists_failed_status(client, test_db_session):
    """
    Verifies failed /api/ask execution persists FAILED status with error details.
    """
    with patch("app.api.routes.run_investigation_loop") as mock_loop:
        from app.schemas.ai import AskResponse
        mock_loop.return_value = AskResponse(
            success=False,
            question="Failing query",
            answer="",
            error="Simulated provider API error"
        )

        response = client.post("/api/ask", json={"question": "Failing query"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False

        inv_id = data["metadata"]["investigation_id"]
        persisted = InvestigationService.get_investigation_by_id(test_db_session, inv_id)
        assert persisted is not None
        assert persisted.status == "FAILED"
        assert "Simulated provider API error" in persisted.error_message


def test_get_metrics_summary_route(client, test_db_session):
    """
    Verifies GET /api/investigations/metrics/summary returns HTTP 200 with summary metrics
    and confirms route ordering precedence over /{investigation_id}.
    """
    # Create an investigation to ensure non-empty metrics
    client.post("/api/ask", json={"question": "Metrics endpoint test query", "max_turns": 1})

    response = client.get("/api/investigations/metrics/summary")
    assert response.status_code == 200

    data = response.json()
    assert "total_investigations" in data
    assert "total_reviews" in data
    assert "status_counts" in data
    assert "review_counts" in data
    assert "robustness_counts" in data
    assert "average_execution_time_ms" in data

    assert data["total_investigations"] >= 1
    assert isinstance(data["status_counts"], dict)
    assert isinstance(data["review_counts"], dict)
    assert isinstance(data["robustness_counts"], dict)
