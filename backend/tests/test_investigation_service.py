import pytest
import time
from unittest.mock import MagicMock
from app.services.investigation_service import InvestigationService, _sanitize_error_text
from app.schemas.investigation import InvestigationStatus
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
