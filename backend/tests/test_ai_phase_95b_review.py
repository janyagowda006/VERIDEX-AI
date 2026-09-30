import json
import pytest
import unittest.mock as mock
from fastapi.testclient import TestClient

from app.main import app
from app.core.db import get_db
from app.ai.provider import get_llm_provider, MockLLMProvider
from app.models.investigation import Investigation, InvestigationReview
from app.services.investigation_service import InvestigationService
from app.schemas.investigation import (
    InvestigationReviewCreate,
    InvestigationReviewResponse,
    InvestigationReviewStatus
)


@pytest.fixture
def client(test_db_session):
    """
    FastAPI TestClient fixture with overridden DB session and MockLLMProvider.
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


def create_sample_completed_investigation(db_session, question="Test question?", robustness_status="STABLE"):
    """
    Helper function to create a completed persistent investigation record.
    """
    inv = InvestigationService.create_investigation(db=db_session, question=question)
    from app.ai.orchestrator import run_investigation_loop
    provider = MockLLMProvider()
    resp = run_investigation_loop(question=question, db=db_session, provider=provider, max_turns=3)

    # Force specific robustness status for test determinism
    if resp.analysis and resp.analysis.robustness:
        resp.analysis.robustness.status = robustness_status
    if resp.metadata:
        resp.metadata["robustness_status"] = robustness_status

    inv = InvestigationService.update_investigation_success(
        db=db_session,
        investigation_id=inv.investigation_id,
        response=resp,
        execution_time_ms=25.0
    )
    return inv


def test_approved_review_succeeds(client, test_db_session):
    """Verifies valid APPROVED review submission via HTTP API."""
    inv = create_sample_completed_investigation(test_db_session, "What are sales by region?")

    resp = client.post(
        f"/api/investigations/{inv.investigation_id}/review",
        json={
            "review_status": "APPROVED",
            "reviewer_id": "analyst_gagan",
            "review_notes": "Verified regional revenue data and 10% sensitivity shift."
        }
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["investigation_id"] == inv.investigation_id
    assert data["review_status"] == "APPROVED"
    assert data["reviewer_id"] == "analyst_gagan"
    assert "rev_" in data["review_id"]


def test_rejected_review_succeeds(client, test_db_session):
    """Verifies valid REJECTED review submission via HTTP API."""
    inv = create_sample_completed_investigation(test_db_session, "What is our customer churn?")

    resp = client.post(
        f"/api/investigations/{inv.investigation_id}/review",
        json={
            "review_status": "REJECTED",
            "reviewer_id": "reviewer_john",
            "review_notes": "Data row count insufficient for conclusive business decision."
        }
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["review_status"] == "REJECTED"
    assert data["reviewer_id"] == "reviewer_john"


def test_flagged_review_succeeds(client, test_db_session):
    """Verifies valid FLAGGED review submission via HTTP API."""
    inv = create_sample_completed_investigation(test_db_session, "Which supplier has highest risk?")

    resp = client.post(
        f"/api/investigations/{inv.investigation_id}/review",
        json={
            "review_status": "FLAGGED",
            "reviewer_id": "auditor_mary",
            "review_notes": "Flagged for legal compliance verification."
        }
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["review_status"] == "FLAGGED"


def test_nonexistent_investigation_returns_404(client):
    """Verifies HTTP 404 when submitting review for non-existent investigation ID."""
    resp = client.post(
        "/api/investigations/inv_nonexistent_999/review",
        json={
            "review_status": "APPROVED",
            "reviewer_id": "analyst_1"
        }
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_invalid_review_status_returns_422(client, test_db_session):
    """Verifies HTTP 422 when review_status is not APPROVED/REJECTED/FLAGGED."""
    inv = create_sample_completed_investigation(test_db_session)

    resp = client.post(
        f"/api/investigations/{inv.investigation_id}/review",
        json={
            "review_status": "INVALID_STATUS",
            "reviewer_id": "analyst_1"
        }
    )
    assert resp.status_code == 422


def test_empty_reviewer_id_returns_422(client, test_db_session):
    """Verifies HTTP 422 when reviewer_id is an empty string."""
    inv = create_sample_completed_investigation(test_db_session)

    resp = client.post(
        f"/api/investigations/{inv.investigation_id}/review",
        json={
            "review_status": "APPROVED",
            "reviewer_id": ""
        }
    )
    assert resp.status_code == 422


def test_whitespace_only_reviewer_id_returns_422(client, test_db_session):
    """Verifies HTTP 422 when reviewer_id is whitespace-only."""
    inv = create_sample_completed_investigation(test_db_session)

    resp = client.post(
        f"/api/investigations/{inv.investigation_id}/review",
        json={
            "review_status": "APPROVED",
            "reviewer_id": "   "
        }
    )
    assert resp.status_code == 422


def test_reviewer_id_exceeding_64_chars_returns_422(client, test_db_session):
    """Verifies HTTP 422 when reviewer_id exceeds 64 characters."""
    inv = create_sample_completed_investigation(test_db_session)
    long_reviewer_id = "a" * 65

    resp = client.post(
        f"/api/investigations/{inv.investigation_id}/review",
        json={
            "review_status": "APPROVED",
            "reviewer_id": long_reviewer_id
        }
    )
    assert resp.status_code == 422


def test_review_notes_exceeding_2000_chars_returns_422(client, test_db_session):
    """Verifies HTTP 422 when review_notes exceeds 2000 characters."""
    inv = create_sample_completed_investigation(test_db_session)
    long_notes = "x" * 2001

    resp = client.post(
        f"/api/investigations/{inv.investigation_id}/review",
        json={
            "review_status": "APPROVED",
            "reviewer_id": "analyst_1",
            "review_notes": long_notes
        }
    )
    assert resp.status_code == 422


def test_in_progress_investigation_cannot_be_reviewed(client, test_db_session):
    """Verifies HTTP 400 when attempting to submit a review for an IN_PROGRESS investigation."""
    inv_in_progress = InvestigationService.create_investigation(
        db=test_db_session,
        question="Unfinished investigation question?"
    )

    resp = client.post(
        f"/api/investigations/{inv_in_progress.investigation_id}/review",
        json={
            "review_status": "APPROVED",
            "reviewer_id": "analyst_1"
        }
    )
    assert resp.status_code == 400
    assert "in_progress" in resp.json()["detail"].lower()


def test_multiple_reviews_are_append_only(client, test_db_session):
    """Verifies that submitting multiple reviews creates multiple append-only records."""
    inv = create_sample_completed_investigation(test_db_session)

    # First review: FLAGGED
    resp1 = client.post(
        f"/api/investigations/{inv.investigation_id}/review",
        json={
            "review_status": "FLAGGED",
            "reviewer_id": "junior_analyst",
            "review_notes": "Needs senior verification."
        }
    )
    assert resp1.status_code == 200

    # Second review: APPROVED
    resp2 = client.post(
        f"/api/investigations/{inv.investigation_id}/review",
        json={
            "review_status": "APPROVED",
            "reviewer_id": "senior_analyst",
            "review_notes": "Verified and approved after review."
        }
    )
    assert resp2.status_code == 200

    reviews = InvestigationService.list_reviews_for_investigation(test_db_session, inv.investigation_id)
    assert len(reviews) == 2
    assert reviews[0].review_status == "APPROVED"  # Most recent
    assert reviews[1].review_status == "FLAGGED"


def test_latest_review_returned_correctly(test_db_session):
    """Verifies InvestigationService.get_latest_review returns the most recent review record."""
    inv = create_sample_completed_investigation(test_db_session)

    req1 = InvestigationReviewCreate(review_status=InvestigationReviewStatus.FLAGGED, reviewer_id="rev_1")
    InvestigationService.create_review(test_db_session, inv.investigation_id, req1)

    req2 = InvestigationReviewCreate(review_status=InvestigationReviewStatus.APPROVED, reviewer_id="rev_2")
    latest = InvestigationService.create_review(test_db_session, inv.investigation_id, req2)

    retrieved_latest = InvestigationService.get_latest_review(test_db_session, inv.investigation_id)
    assert retrieved_latest is not None
    assert retrieved_latest.review_id == latest.review_id
    assert retrieved_latest.review_status == "APPROVED"


def test_review_count_is_correct(test_db_session):
    """Verifies list_reviews_for_investigation length correctly tracks total reviews."""
    inv = create_sample_completed_investigation(test_db_session)
    assert len(InvestigationService.list_reviews_for_investigation(test_db_session, inv.investigation_id)) == 0

    req = InvestigationReviewCreate(review_status=InvestigationReviewStatus.APPROVED, reviewer_id="rev_1")
    InvestigationService.create_review(test_db_session, inv.investigation_id, req)
    assert len(InvestigationService.list_reviews_for_investigation(test_db_session, inv.investigation_id)) == 1


def test_get_investigation_detail_exposes_review_info(client, test_db_session):
    """Verifies GET /api/investigations/{id} exposes latest_review and review_count."""
    inv = create_sample_completed_investigation(test_db_session)

    # Submit review
    client.post(
        f"/api/investigations/{inv.investigation_id}/review",
        json={
            "review_status": "APPROVED",
            "reviewer_id": "auditor_jane",
            "review_notes": "Audit complete."
        }
    )

    detail_resp = client.get(f"/api/investigations/{inv.investigation_id}")
    assert detail_resp.status_code == 200
    data = detail_resp.json()
    assert data["review_count"] == 1
    assert data["latest_review"] is not None
    assert data["latest_review"]["review_status"] == "APPROVED"
    assert data["latest_review"]["reviewer_id"] == "auditor_jane"


def test_original_result_json_remains_unchanged(test_db_session):
    """IMMUTABILITY TEST: Proves result_json is byte-for-byte identical after submitting reviews."""
    inv = create_sample_completed_investigation(test_db_session)
    orig_json = inv.result_json

    req = InvestigationReviewCreate(
        review_status=InvestigationReviewStatus.REJECTED,
        reviewer_id="reviewer_1",
        review_notes="Notes"
    )
    InvestigationService.create_review(test_db_session, inv.investigation_id, req)

    updated_inv = InvestigationService.get_investigation_by_id(test_db_session, inv.investigation_id)
    assert updated_inv.result_json == orig_json


def test_original_robustness_status_remains_unchanged(test_db_session):
    """IMMUTABILITY TEST: Proves robustness_status is completely unchanged after submitting reviews."""
    inv = create_sample_completed_investigation(test_db_session, robustness_status="SENSITIVE")
    orig_rob = inv.robustness_status
    assert orig_rob == "SENSITIVE"

    req = InvestigationReviewCreate(
        review_status=InvestigationReviewStatus.APPROVED,
        reviewer_id="reviewer_1"
    )
    InvestigationService.create_review(test_db_session, inv.investigation_id, req)

    updated_inv = InvestigationService.get_investigation_by_id(test_db_session, inv.investigation_id)
    assert updated_inv.robustness_status == "SENSITIVE"


def test_review_transaction_rollback_works(test_db_session):
    """Verifies database rollback on transaction error during review creation."""
    inv = create_sample_completed_investigation(test_db_session)

    req = InvestigationReviewCreate(
        review_status=InvestigationReviewStatus.APPROVED,
        reviewer_id="analyst_1"
    )

    with mock.patch.object(test_db_session, "commit", side_effect=RuntimeError("DB Commit Failure")):
        with pytest.raises(RuntimeError):
            InvestigationService.create_review(test_db_session, inv.investigation_id, req)

    # Confirm no review persisted
    reviews = InvestigationService.list_reviews_for_investigation(test_db_session, inv.investigation_id)
    assert len(reviews) == 0


def test_review_submission_never_invokes_llm(test_db_session):
    """
    CRITICAL ARCHITECTURAL BOUNDARY TEST:
    Proves submitting a review NEVER invokes LLM provider generation.
    """
    inv = create_sample_completed_investigation(test_db_session)
    req = InvestigationReviewCreate(review_status=InvestigationReviewStatus.APPROVED, reviewer_id="analyst_1")

    with mock.patch("app.ai.provider.BaseLLMProvider.generate_turn") as mock_llm_gen:
        InvestigationService.create_review(test_db_session, inv.investigation_id, req)
        mock_llm_gen.assert_not_called()


def test_review_submission_never_executes_analytical_sql(test_db_session):
    """
    CRITICAL ARCHITECTURAL BOUNDARY TEST:
    Proves submitting a review NEVER executes business analytical SQL tool queries.
    """
    inv = create_sample_completed_investigation(test_db_session)
    req = InvestigationReviewCreate(review_status=InvestigationReviewStatus.APPROVED, reviewer_id="analyst_1")

    with mock.patch("app.tools.sql_tool.execute_read_only_sql") as mock_sql_exec:
        InvestigationService.create_review(test_db_session, inv.investigation_id, req)
        mock_sql_exec.assert_not_called()


def test_existing_investigation_behavior_remains_compatible(client, test_db_session):
    """Verifies existing API endpoints remain 100% backward compatible."""
    inv = create_sample_completed_investigation(test_db_session)

    # List history
    hist_resp = client.get("/api/investigations")
    assert hist_resp.status_code == 200
    assert len(hist_resp.json()) > 0

    # Get detail before review
    detail_resp = client.get(f"/api/investigations/{inv.investigation_id}")
    assert detail_resp.status_code == 200
    data = detail_resp.json()
    assert data["review_count"] == 0
    assert data["latest_review"] is None
