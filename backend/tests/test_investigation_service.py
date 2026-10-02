import pytest
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

from app.models.investigation import Investigation, InvestigationAuditLog
from app.schemas.investigation import (
    InvestigationStatus,
    InvestigationReviewStatus,
    ReviewStatus,
    ReviewDecision,
    InvestigationSummary,
    InvestigationReviewCreate,
    InvestigationDetail,
    InvestigationDetailResponse,
)
from app.schemas.ai import AskResponse, ToolCallRecord
from app.schemas.evidence import EvidenceItem, EvidenceType, ClaimEvidence, EvidenceSource
from app.schemas.decision import DecisionAnalysis, RobustnessCheck, RobustnessScenario, Recommendation
from app.schemas.sql_tool import SQLQueryResult, QueryMetadata
from app.services.investigation_service import (
    InvestigationService,
    InvestigationNotFoundError,
    InvestigationValidationError,
    _sanitize_error_text
)
from app.services.robustness import (
    ROBUSTNESS_STATUS_STABLE,
    ROBUSTNESS_STATUS_SENSITIVE,
    ROBUSTNESS_STATUS_INSUFFICIENT_EVIDENCE
)


def test_create_investigation(test_db_session):
    """
    Verifies create_investigation creates an IN_PROGRESS record with valid ID and timestamp.
    """
    inv = InvestigationService.create_investigation(
        db=test_db_session,
        question="What is our gross revenue by region?"
    )

    assert inv is not None
    assert inv.investigation_id.startswith("inv_")
    assert inv.question == "What is our gross revenue by region?"
    assert inv.status == InvestigationStatus.IN_PROGRESS.value
    assert inv.created_at is not None
    assert inv.completed_at is None


def test_update_investigation_success_stable(test_db_session):
    """
    Verifies update_investigation_success maps STABLE robustness status to COMPLETED.
    """
    inv = InvestigationService.create_investigation(
        db=test_db_session,
        question="Stable robustness query"
    )

    robustness = RobustnessCheck(
        check_id="rob_1",
        status=ROBUSTNESS_STATUS_STABLE,
        baseline_scenario={"scenario_name": "baseline"},
        explanation="Findings remain stable"
    )
    analysis = DecisionAnalysis(
        analysis_id="anal_1",
        summary="Decision analysis",
        robustness=robustness
    )
    response = AskResponse(
        success=True,
        question=inv.question,
        answer="Stable answer text",
        claims=[],
        evidence=[],
        analysis=analysis,
        metadata={"total_turns": 1}
    )

    updated = InvestigationService.update_investigation_success(
        db=test_db_session,
        investigation_id=inv.investigation_id,
        response=response,
        execution_time_ms=25.4
    )

    assert updated is not None
    assert updated.status == InvestigationStatus.COMPLETED.value
    assert updated.robustness_status == "STABLE"
    assert updated.execution_time_ms == 25.4
    assert updated.completed_at is not None
    assert "Stable answer text" in updated.result_json


def test_update_investigation_success_insufficient_evidence(test_db_session):
    """
    Verifies update_investigation_success maps INSUFFICIENT_EVIDENCE robustness status to COMPLETED.
    """
    inv = InvestigationService.create_investigation(
        db=test_db_session,
        question="Insufficient evidence query"
    )

    robustness = RobustnessCheck(
        check_id="rob_2",
        status=ROBUSTNESS_STATUS_INSUFFICIENT_EVIDENCE,
        baseline_scenario={"scenario_name": "baseline"},
        explanation="Insufficient data"
    )
    analysis = DecisionAnalysis(
        analysis_id="anal_2",
        summary="Analysis",
        robustness=robustness
    )
    response = AskResponse(
        success=True,
        question=inv.question,
        answer="Insufficient evidence text",
        claims=[],
        evidence=[],
        analysis=analysis
    )

    updated = InvestigationService.update_investigation_success(
        db=test_db_session,
        investigation_id=inv.investigation_id,
        response=response,
        execution_time_ms=12.1
    )

    assert updated is not None
    assert updated.status == InvestigationStatus.COMPLETED.value
    assert updated.robustness_status == "INSUFFICIENT_EVIDENCE"


def test_update_investigation_success_sensitive(test_db_session):
    """
    Verifies update_investigation_success maps SENSITIVE robustness status to REQUIRES_REVIEW.
    """
    inv = InvestigationService.create_investigation(
        db=test_db_session,
        question="Sensitive robustness query"
    )

    robustness = RobustnessCheck(
        check_id="rob_3",
        status=ROBUSTNESS_STATUS_SENSITIVE,
        baseline_scenario={"scenario_name": "baseline"},
        explanation="Sensitivity detected under alternate scenario filters"
    )
    analysis = DecisionAnalysis(
        analysis_id="anal_3",
        summary="Analysis",
        robustness=robustness
    )
    response = AskResponse(
        success=True,
        question=inv.question,
        answer="Sensitive answer text",
        claims=[],
        evidence=[],
        analysis=analysis
    )

    updated = InvestigationService.update_investigation_success(
        db=test_db_session,
        investigation_id=inv.investigation_id,
        response=response,
        execution_time_ms=30.0
    )

    assert updated is not None
    assert updated.status == InvestigationStatus.REQUIRES_REVIEW.value
    assert updated.robustness_status == "SENSITIVE"


def test_update_investigation_failure_sanitizes_error(test_db_session):
    """
    Verifies update_investigation_failure updates status to FAILED and sanitizes API keys in error messages.
    """
    inv = InvestigationService.create_investigation(
        db=test_db_session,
        question="Failed query with secret"
    )

    raw_error = "Gemini API error: api_key=AIzaSySecretKey12345 Bearer eyJhbGciOiJIUzI1NiIn"
    updated = InvestigationService.update_investigation_failure(
        db=test_db_session,
        investigation_id=inv.investigation_id,
        error_message=raw_error,
        execution_time_ms=10.5
    )

    assert updated is not None
    assert updated.status == InvestigationStatus.FAILED.value
    assert "AIzaSySecretKey12345" not in updated.error_message
    assert "api_key=***" in updated.error_message
    assert updated.execution_time_ms == 10.5


def test_list_investigations_ordering(test_db_session):
    """
    Verifies list_investigations returns records ordered by created_at DESC (newest first).
    """
    inv1 = InvestigationService.create_investigation(db=test_db_session, question="First query")
    time.sleep(0.01)
    inv2 = InvestigationService.create_investigation(db=test_db_session, question="Second query")

    investigations = InvestigationService.list_investigations(db=test_db_session, limit=10)
    assert len(investigations) >= 2

    ids = [i.investigation_id for i in investigations]
    assert ids.index(inv2.investigation_id) < ids.index(inv1.investigation_id)


def test_get_investigation_by_id(test_db_session):
    """
    Verifies get_investigation_by_id retrieves specific record or returns None if missing.
    """
    inv = InvestigationService.create_investigation(db=test_db_session, question="Query by ID test")

    found = InvestigationService.get_investigation_by_id(test_db_session, inv.investigation_id)
    assert found is not None
    assert found.investigation_id == inv.investigation_id

    missing = InvestigationService.get_investigation_by_id(test_db_session, "inv_nonexistent_999")
    assert missing is None


def test_update_missing_investigation_id_returns_none(test_db_session):
    """
    Verifies updating non-existent investigation ID returns None.
    """
    response = AskResponse(success=True, question="Q", answer="A")
    res_success = InvestigationService.update_investigation_success(test_db_session, "inv_missing", response, 10.0)
    assert res_success is None

    res_fail = InvestigationService.update_investigation_failure(test_db_session, "inv_missing", "Error")
    assert res_fail is None


def test_transaction_rollback_on_error():
    """
    Verifies database transaction rollback when database operation fails.
    """
    mock_db = MagicMock()
    mock_db.commit.side_effect = Exception("DB Commit Failed")

    with pytest.raises(Exception, match="DB Commit Failed"):
        InvestigationService.create_investigation(mock_db, question="Rollback test")

    mock_db.rollback.assert_called_once()


def test_get_metrics_summary_aggregation_and_deltas(test_db_session):
    """
    Verifies get_metrics_summary correctly aggregates status, reviews, robustness, and execution time deltas.
    """
    initial_metrics = InvestigationService.get_metrics_summary(test_db_session)
    initial_total_inv = initial_metrics.total_investigations
    initial_total_rev = initial_metrics.total_reviews

    inv1 = InvestigationService.create_investigation(test_db_session, question="Metrics Delta Q1")
    rob1 = RobustnessCheck(check_id="r1", status=ROBUSTNESS_STATUS_STABLE, baseline_scenario={"scenario_name": "base"}, explanation="Stable explanation")
    resp1 = AskResponse(success=True, question="Metrics Delta Q1", answer="A1", claims=[], evidence=[], analysis=DecisionAnalysis(analysis_id="a1", summary="s", robustness=rob1))
    InvestigationService.update_investigation_success(test_db_session, inv1.investigation_id, resp1, execution_time_ms=100.0)

    inv2 = InvestigationService.create_investigation(test_db_session, question="Metrics Delta Q2")
    rob2 = RobustnessCheck(check_id="r2", status=ROBUSTNESS_STATUS_SENSITIVE, baseline_scenario={"scenario_name": "base"}, explanation="Sensitive explanation")
    resp2 = AskResponse(success=True, question="Metrics Delta Q2", answer="A2", claims=[], evidence=[], analysis=DecisionAnalysis(analysis_id="a2", summary="s", robustness=rob2))
    InvestigationService.update_investigation_success(test_db_session, inv2.investigation_id, resp2, execution_time_ms=200.0)

    rev_data1 = InvestigationReviewCreate(review_status=InvestigationReviewStatus.FLAGGED, reviewer_id="user1", review_notes="Needs check")
    InvestigationService.create_review(test_db_session, inv2.investigation_id, rev_data1)

    rev_data2 = InvestigationReviewCreate(review_status=InvestigationReviewStatus.APPROVED, reviewer_id="user2", review_notes="Approved now")
    InvestigationService.create_review(test_db_session, inv2.investigation_id, rev_data2)

    inv3 = InvestigationService.create_investigation(test_db_session, question="Metrics Delta Q3")
    InvestigationService.update_investigation_failure(test_db_session, inv3.investigation_id, "Error", execution_time_ms=300.0)

    updated_metrics = InvestigationService.get_metrics_summary(test_db_session)

    assert updated_metrics.total_investigations == initial_total_inv + 3
    assert updated_metrics.total_reviews == initial_total_rev + 2
    assert updated_metrics.status_counts["COMPLETED"] == initial_metrics.status_counts["COMPLETED"] + 1
    assert updated_metrics.status_counts["REQUIRES_REVIEW"] == initial_metrics.status_counts["REQUIRES_REVIEW"] + 1
    assert updated_metrics.status_counts["FAILED"] == initial_metrics.status_counts["FAILED"] + 1


def test_create_turn_first_and_second_turn_deterministic_ordering(test_db_session):
    """
    Verifies create_turn creates sequential turn 1 and turn 2 with deterministic ordering.
    """
    inv = InvestigationService.create_investigation(test_db_session, question="Turn Test Q1")

    resp1 = AskResponse(success=True, question="Turn Test Q1", answer="Answer 1", claims=[], evidence=[])
    turn1 = InvestigationService.create_turn(
        db=test_db_session,
        investigation_id=inv.investigation_id,
        user_question="Turn Test Q1",
        response=resp1,
        execution_time_ms=120.0
    )

    assert turn1 is not None
    assert turn1.turn_id.startswith("turn_")
    assert turn1.investigation_id == inv.investigation_id
    assert turn1.turn_number == 1
    assert turn1.user_question == "Turn Test Q1"
    assert turn1.execution_time_ms == 120.0

    resp2 = AskResponse(success=True, question="Why did North outperform South?", answer="Answer 2", claims=[], evidence=[])
    turn2 = InvestigationService.create_turn(
        db=test_db_session,
        investigation_id=inv.investigation_id,
        user_question="Why did North outperform South?",
        response=resp2,
        execution_time_ms=180.0
    )

    assert turn2 is not None
    assert turn2.turn_number == 2

    turns = InvestigationService.list_turns_for_investigation(test_db_session, inv.investigation_id)
    assert len(turns) == 2
    assert turns[0].turn_number == 1
    assert turns[1].turn_number == 2


def test_create_investigation_from_valid_ask_response(test_db_session):
    service = InvestigationService(test_db_session)
    ask_resp = AskResponse(
        success=True,
        question="What is our highest performing region?",
        answer="North region generated highest revenue.",
        claims=[],
        evidence=[]
    )
    inv = service.create_investigation(
        db=test_db_session,
        question=ask_resp.question,
        response=ask_resp
    )
    assert inv is not None
    assert inv.investigation_id.startswith("inv_")
    assert inv.status == InvestigationStatus.COMPLETED.value


def test_reconstruct_ask_response(test_db_session):
    service = InvestigationService(test_db_session)
    ask_resp = AskResponse(
        success=True,
        question="Roundtrip question?",
        answer="North region generated highest revenue.",
        claims=[],
        evidence=[]
    )
    inv = service.create_investigation(
        db=test_db_session,
        question=ask_resp.question,
        response=ask_resp
    )
    reconstructed = service.reconstruct_ask_response(inv)
    assert reconstructed.question == ask_resp.question
    assert reconstructed.answer == ask_resp.answer


def test_review_approved(test_db_session):
    service = InvestigationService(test_db_session)
    ask_resp = AskResponse(
        success=True,
        question="Review target question",
        answer="Answer text",
        claims=[],
        evidence=[]
    )
    inv = service.create_investigation(
        db=test_db_session,
        question=ask_resp.question,
        response=ask_resp
    )
    updated = service.update_review(
        investigation_id=inv.investigation_id,
        review_decision=ReviewDecision.APPROVED,
        reviewer_notes="Approved by CFO",
        db=test_db_session
    )
    assert updated.review_status == "APPROVED"
