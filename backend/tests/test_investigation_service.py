import pytest
import time
from unittest.mock import MagicMock
from app.services.investigation_service import InvestigationService, _sanitize_error_text
from app.schemas.investigation import InvestigationStatus, InvestigationReviewCreate, InvestigationDetail
from app.schemas.ai import AskResponse
from app.schemas.decision import DecisionAnalysis, RobustnessCheck
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

    # Verify newest first
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

    # 1. Create a completed stable investigation with execution time 100ms
    inv1 = InvestigationService.create_investigation(test_db_session, question="Metrics Delta Q1")
    rob1 = RobustnessCheck(check_id="r1", status=ROBUSTNESS_STATUS_STABLE, baseline_scenario={"scenario_name": "base"}, explanation="Stable explanation")
    resp1 = AskResponse(success=True, question="Metrics Delta Q1", answer="A1", claims=[], evidence=[], analysis=DecisionAnalysis(analysis_id="a1", summary="s", robustness=rob1))
    InvestigationService.update_investigation_success(test_db_session, inv1.investigation_id, resp1, execution_time_ms=100.0)

    # 2. Create a sensitive investigation requiring review with execution time 200ms
    inv2 = InvestigationService.create_investigation(test_db_session, question="Metrics Delta Q2")
    rob2 = RobustnessCheck(check_id="r2", status=ROBUSTNESS_STATUS_SENSITIVE, baseline_scenario={"scenario_name": "base"}, explanation="Sensitive explanation")
    resp2 = AskResponse(success=True, question="Metrics Delta Q2", answer="A2", claims=[], evidence=[], analysis=DecisionAnalysis(analysis_id="a2", summary="s", robustness=rob2))
    InvestigationService.update_investigation_success(test_db_session, inv2.investigation_id, resp2, execution_time_ms=200.0)

    # Add reviews to inv2
    rev_data1 = InvestigationReviewCreate(review_status="FLAGGED", reviewer_id="user1", review_notes="Needs check")
    InvestigationService.create_review(test_db_session, inv2.investigation_id, rev_data1)

    rev_data2 = InvestigationReviewCreate(review_status="APPROVED", reviewer_id="user2", review_notes="Approved now")
    InvestigationService.create_review(test_db_session, inv2.investigation_id, rev_data2)

    # 3. Create a failed investigation with execution time 300ms
    inv3 = InvestigationService.create_investigation(test_db_session, question="Metrics Delta Q3")
    InvestigationService.update_investigation_failure(test_db_session, inv3.investigation_id, "Error", execution_time_ms=300.0)

    # Fetch updated summary
    updated_metrics = InvestigationService.get_metrics_summary(test_db_session)

    assert updated_metrics.total_investigations == initial_total_inv + 3
    assert updated_metrics.total_reviews == initial_total_rev + 2
    assert updated_metrics.status_counts["COMPLETED"] == initial_metrics.status_counts["COMPLETED"] + 1
    assert updated_metrics.status_counts["REQUIRES_REVIEW"] == initial_metrics.status_counts["REQUIRES_REVIEW"] + 1
    assert updated_metrics.status_counts["FAILED"] == initial_metrics.status_counts["FAILED"] + 1

    assert updated_metrics.review_counts["APPROVED"] == initial_metrics.review_counts["APPROVED"] + 1
    assert updated_metrics.review_counts["FLAGGED"] == initial_metrics.review_counts["FLAGGED"] + 1

    assert updated_metrics.robustness_counts["STABLE"] == initial_metrics.robustness_counts["STABLE"] + 1
    assert updated_metrics.robustness_counts["SENSITIVE"] == initial_metrics.robustness_counts["SENSITIVE"] + 1

    assert updated_metrics.average_execution_time_ms is not None


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

    # Verify list retrieval ordering
    turns = InvestigationService.list_turns_for_investigation(test_db_session, inv.investigation_id)
    assert len(turns) == 2
    assert turns[0].turn_number == 1
    assert turns[1].turn_number == 2
    assert turns[0].user_question == "Turn Test Q1"
    assert turns[1].user_question == "Why did North outperform South?"


def test_turn_roundtrip_persistence_and_immutability(test_db_session):
    """
    Verifies result_json payload round-trips via AskResponse validation and prior turns remain immutable.
    """
    inv = InvestigationService.create_investigation(test_db_session, question="Roundtrip Q")
    resp = AskResponse(
        success=True,
        question="Roundtrip Q",
        answer="Detailed answer text",
        claims=[],
        evidence=[],
        metadata={"total_turns": 1}
    )

    turn = InvestigationService.create_turn(
        db=test_db_session,
        investigation_id=inv.investigation_id,
        user_question="Roundtrip Q",
        response=resp,
        execution_time_ms=50.0
    )

    # Verify AskResponse round-trip deserialization
    deserialized = AskResponse.model_validate_json(turn.result_json)
    assert deserialized.success is True
    assert deserialized.answer == "Detailed answer text"
    assert deserialized.metadata["total_turns"] == 1

    # Adding a second turn does NOT mutate turn 1
    resp2 = AskResponse(success=True, question="Followup Q", answer="Answer 2", claims=[], evidence=[])
    InvestigationService.create_turn(test_db_session, inv.investigation_id, "Followup Q", resp2, 60.0)

    turns = InvestigationService.list_turns_for_investigation(test_db_session, inv.investigation_id)
    assert len(turns) == 2
    assert turns[0].user_question == "Roundtrip Q"
    assert turns[0].execution_time_ms == 50.0
    assert AskResponse.model_validate_json(turns[0].result_json).answer == "Detailed answer text"


def test_legacy_investigation_empty_turns(test_db_session):
    """
    Verifies existing or legacy investigations without turn records return empty list without error.
    """
    inv = InvestigationService.create_investigation(test_db_session, question="Legacy investigation without turns")
    turns = InvestigationService.list_turns_for_investigation(test_db_session, inv.investigation_id)
    assert turns == []

    detail = InvestigationDetail.model_validate(inv)
    assert detail.turns == []


def test_create_turn_nonexistent_investigation_raises_value_error(test_db_session):
    """
    Verifies create_turn raises ValueError when referencing a non-existent investigation ID.
    """
    with pytest.raises(ValueError, match="Investigation with ID 'inv_nonexistent_999' not found"):
        InvestigationService.create_turn(
            db=test_db_session,
            investigation_id="inv_nonexistent_999",
            user_question="Orphan turn question"
        )


def test_list_investigations_search_and_filtering(test_db_session):
    """
    Verifies list_investigations search keyword, status, and robustness_status filtering.
    """
    inv1 = InvestigationService.create_investigation(test_db_session, question="Revenue by region in North")
    inv1.status = "COMPLETED"
    inv1.robustness_status = "STABLE"

    inv2 = InvestigationService.create_investigation(test_db_session, question="Product margin sensitivity analysis")
    inv2.status = "REQUIRES_REVIEW"
    inv2.robustness_status = "SENSITIVE"

    inv3 = InvestigationService.create_investigation(test_db_session, question="Cancellation rate breakdown")
    inv3.status = "FAILED"
    inv3.robustness_status = "INSUFFICIENT_EVIDENCE"

    test_db_session.commit()

    # 1. No filters (returns all)
    all_invs = InvestigationService.list_investigations(test_db_session)
    assert len(all_invs) >= 3

    # 2. Keyword search
    search_res = InvestigationService.list_investigations(test_db_session, search="North")
    assert len(search_res) == 1
    assert search_res[0].investigation_id == inv1.investigation_id

    # 3. Status filter
    status_res = InvestigationService.list_investigations(test_db_session, status="REQUIRES_REVIEW")
    assert any(i.investigation_id == inv2.investigation_id for i in status_res)
    assert not any(i.investigation_id == inv1.investigation_id for i in status_res)

    # 4. Robustness status filter
    rob_res = InvestigationService.list_investigations(test_db_session, robustness_status="SENSITIVE")
    assert any(i.investigation_id == inv2.investigation_id for i in rob_res)
    assert not any(i.investigation_id in (inv1.investigation_id, inv3.investigation_id) for i in rob_res)

    # 5. Combined filters
    combined_res = InvestigationService.list_investigations(
        test_db_session,
        search="margin",
        status="requires_review",
        robustness_status="sensitive"
    )
    assert len(combined_res) == 1
    assert combined_res[0].investigation_id == inv2.investigation_id

    # 6. Empty search result
    empty_res = InvestigationService.list_investigations(test_db_session, search="nonexistent_keyword_xyz")
    assert len(empty_res) == 0
