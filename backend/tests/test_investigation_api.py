import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.main import app
from app.core.db import get_db
from app.ai.provider import get_llm_provider, MockLLMProvider
from app.models.investigation import Investigation, InvestigationAuditLog
from app.schemas.investigation import ReviewDecision


@pytest.fixture
def client(test_db_session):
    """
    TestClient with overridden database session and mock LLM provider.
    """
    app.dependency_overrides[get_db] = lambda: test_db_session
    app.dependency_overrides[get_llm_provider] = lambda: MockLLMProvider()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ==============================================================================
# 1, 2, 3 & 15. POST /api/ask persistence, backward compatibility, metadata
# ==============================================================================
def test_ask_endpoint_persists_investigation_and_preserves_contract(client, test_db_session):
    """
    1. POST /api/ask persists a successful investigation.
    2. Returned AskResponse remains 100% backward compatible with existing schema.
    3. investigation_id is exposed cleanly in response.metadata.
    15. Existing reasoning & tool execution behavior remains intact.
    """
    response = client.post(
        "/api/ask",
        json={"question": "What is our highest revenue region?", "max_turns": 3}
    )
    assert response.status_code == 200
    data = response.json()

    # Contract validation: all standard fields exist
    assert data["success"] is True
    assert data["question"] == "What is our highest revenue region?"
    assert "answer" in data and len(data["answer"]) > 0
    assert "claims" in data and isinstance(data["claims"], list)
    assert "evidence" in data and isinstance(data["evidence"], list)
    assert "tool_calls" in data and len(data["tool_calls"]) > 0
    assert "metadata" in data and isinstance(data["metadata"], dict)

    # investigation_id available in metadata
    inv_id = data["metadata"].get("investigation_id")
    assert inv_id is not None
    assert inv_id.startswith("inv_")

    # DB persistence verified
    db_inv = test_db_session.query(Investigation).filter_by(investigation_id=inv_id).first()
    assert db_inv is not None
    assert db_inv.question == "What is our highest revenue region?"
    assert db_inv.status == "COMPLETED"
    assert db_inv.review_status == "PENDING"
    assert len(db_inv.tool_calls_json) == len(data["tool_calls"])


# ==============================================================================
# 4 & 5. GET /api/investigations history and pagination
# ==============================================================================
def test_get_investigations_history_and_pagination(client):
    """
    4. GET /api/investigations returns lightweight summaries without raw evidence payloads.
    5. Pagination works as expected; bounds are enforced.
    """
    # Create 3 distinct queries to ensure history exists
    for i in range(3):
        client.post("/api/ask", json={"question": f"Regional query {i}?", "max_turns": 3})

    # Fetch list
    resp = client.get("/api/investigations?limit=2&offset=0")
    assert resp.status_code == 200
    summaries = resp.json()
    assert len(summaries) == 2

    first = summaries[0]
    assert "investigation_id" in first
    assert "question" in first
    assert "status" in first
    assert "review_status" in first
    assert "created_at" in first
    # Raw evidence payload must not be in summary
    assert "evidence" not in first
    assert "claims" not in first
    assert "tool_calls" not in first

    # Offset pagination
    resp_page2 = client.get("/api/investigations?limit=2&offset=2")
    assert resp_page2.status_code == 200
    summaries_page2 = resp_page2.json()
    assert len(summaries_page2) >= 1
    assert summaries[0]["investigation_id"] != summaries_page2[0]["investigation_id"]

    # Bounds validation
    bad_limit = client.get("/api/investigations?limit=101")
    assert bad_limit.status_code == 400

    bad_offset = client.get("/api/investigations?offset=-1")
    assert bad_offset.status_code == 400


# ==============================================================================
# 6 & 7. GET /api/investigations/{id} detail and 404
# ==============================================================================
def test_get_investigation_detail_and_404(client):
    """
    6. GET /api/investigations/{id} returns full investigation detail.
    7. Unknown investigation returns 404.
    """
    ask_resp = client.post("/api/ask", json={"question": "Detail check question?", "max_turns": 3})
    inv_id = ask_resp.json()["metadata"]["investigation_id"]

    # Valid ID
    detail_resp = client.get(f"/api/investigations/{inv_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["investigation_id"] == inv_id
    assert detail["question"] == "Detail check question?"
    assert detail["status"] == "COMPLETED"
    assert detail["review_status"] == "PENDING"
    assert "response" in detail
    assert detail["response"]["question"] == "Detail check question?"
    assert "audit_trail" in detail
    assert len(detail["audit_trail"]) >= 1

    # 404 for unknown ID
    unknown_resp = client.get("/api/investigations/inv_ghost_not_found_99999")
    assert unknown_resp.status_code == 404
    assert "not found" in unknown_resp.json()["detail"].lower()


# ==============================================================================
# 8, 9, 10, 11, 12, 13. POST /api/investigations/{id}/review
# ==============================================================================
def test_investigation_review_lifecycle(client):
    """
    8. Review accepts APPROVED.
    9. Review accepts REJECTED.
    10. Review accepts FLAGGED.
    11. Invalid review decision is rejected (400 or 422).
    12. Review creates audit history.
    13. Multiple reviews preserve complete audit history.
    """
    ask_resp = client.post("/api/ask", json={"question": "Review lifecycle check?", "max_turns": 3})
    inv_id = ask_resp.json()["metadata"]["investigation_id"]

    # 8 & 12: APPROVED
    rev1 = client.post(
        f"/api/investigations/{inv_id}/review",
        json={"status": "APPROVED", "reviewer_notes": "First pass: approved by Lead Data Scientist."}
    )
    assert rev1.status_code == 200
    d1 = rev1.json()
    assert d1["review_status"] == "APPROVED"
    assert d1["reviewer_notes"] == "First pass: approved by Lead Data Scientist."
    assert len(d1["audit_trail"]) == 2  # initial creation + review 1

    # 10: FLAGGED
    rev2 = client.post(
        f"/api/investigations/{inv_id}/review",
        json={"status": "FLAGGED", "reviewer_notes": "Hold: check seasonal baseline."}
    )
    assert rev2.status_code == 200
    d2 = rev2.json()
    assert d2["review_status"] == "FLAGGED"
    assert d2["reviewer_notes"] == "Hold: check seasonal baseline."
    assert len(d2["audit_trail"]) == 3  # initial + rev 1 + rev 2

    # 9 & 13: REJECTED with multi-review audit history preserved
    rev3 = client.post(
        f"/api/investigations/{inv_id}/review",
        json={"status": "REJECTED", "reviewer_notes": "Rejected due to baseline discrepancy."}
    )
    assert rev3.status_code == 200
    d3 = rev3.json()
    assert d3["review_status"] == "REJECTED"
    assert len(d3["audit_trail"]) == 4

    decisions = [a["review_status"] for a in d3["audit_trail"] if a["event_type"] == "HUMAN_REVIEW_UPDATED"]
    assert decisions == ["APPROVED", "FLAGGED", "REJECTED"]

    # 11: Invalid review status rejection
    bad_rev = client.post(
        f"/api/investigations/{inv_id}/review",
        json={"status": "MAYBE"}
    )
    assert bad_rev.status_code in (400, 422)

    # Nonexistent investigation review rejection (404)
    ghost_rev = client.post(
        "/api/investigations/inv_ghost_id/review",
        json={"status": "APPROVED"}
    )
    assert ghost_rev.status_code == 404


# ==============================================================================
# 14. Persistence failure does not leave partial data & preserves AskResponse
# ==============================================================================
def test_persistence_failure_safe_handling(client, test_db_session):
    """
    14. If persistence fails during POST /api/ask, the orchestrator's AskResponse
    is still returned to the client safely, the persistence error is reported in metadata,
    and no partial investigation/audit records are committed.
    """
    with patch("app.services.investigation_service.InvestigationService.create_investigation", side_effect=SQLAlchemyError("Simulated DB Disk Full")):
        response = client.post(
            "/api/ask",
            json={"question": "Fail test question?", "max_turns": 3}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "investigation_id" not in data["metadata"]
        assert "persistence_error" in data["metadata"]
        assert "Simulated DB Disk Full" in data["metadata"]["persistence_error"]

        # Ensure no partial investigation was committed for this question
        count = test_db_session.query(Investigation).filter_by(question="Fail test question?").count()
        assert count == 0


# ==============================================================================
# 16. GET /api/investigations/{id}/report
# ==============================================================================
def test_investigation_report_endpoint(client):
    """
    Tests GET /api/investigations/{id}/report returns the structured investigation report
    and returns 404 for nonexistent IDs.
    """
    ask_resp = client.post("/api/ask", json={"question": "Report check question?", "max_turns": 3})
    inv_id = ask_resp.json()["metadata"]["investigation_id"]

    rep_resp = client.get(f"/api/investigations/{inv_id}/report")
    assert rep_resp.status_code == 200
    report = rep_resp.json()
    assert report["investigation_id"] == inv_id
    assert report["question"] == "Report check question?"
    assert "response" in report
    assert "audit_trail" in report

    # 404 for unknown ID
    unknown_rep = client.get("/api/investigations/inv_unknown_report_id/report")
    assert unknown_rep.status_code == 404
