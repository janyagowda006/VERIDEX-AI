import pytest
import json
from datetime import datetime, timezone
from app.models.business_data import Base
from app.models.investigation import Investigation, utcnow
from app.schemas.investigation import (
    InvestigationStatus,
    InvestigationCreate,
    InvestigationSummary,
    InvestigationDetail
)


def test_investigation_model_import_and_metadata():
    """
    Verifies that Investigation model is discoverable through Base.metadata.tables.
    """
    assert "investigations" in Base.metadata.tables
    table = Base.metadata.tables["investigations"]
    assert "investigation_id" in table.columns
    assert "status" in table.columns
    assert "result_json" in table.columns


def test_persist_in_progress_investigation(test_db_session):
    """
    Verifies persisting an IN_PROGRESS investigation record.
    """
    inv = Investigation(
        investigation_id="inv_test_01",
        question="What is our gross revenue by region?",
        status=InvestigationStatus.IN_PROGRESS.value
    )
    test_db_session.add(inv)
    test_db_session.commit()

    queried = test_db_session.query(Investigation).filter_by(investigation_id="inv_test_01").first()
    assert queried is not None
    assert queried.question == "What is our gross revenue by region?"
    assert queried.status == "IN_PROGRESS"
    assert queried.created_at is not None
    assert queried.completed_at is None


def test_persist_completed_investigation(test_db_session):
    """
    Verifies updating an investigation to COMPLETED status with result_json.
    """
    inv = Investigation(
        investigation_id="inv_test_02",
        question="What is our profit margin by category?",
        status=InvestigationStatus.IN_PROGRESS.value
    )
    test_db_session.add(inv)
    test_db_session.commit()

    # Update to COMPLETED
    mock_payload = {"success": True, "answer": "Electronics has 35% margin."}
    inv.status = InvestigationStatus.COMPLETED.value
    inv.completed_at = utcnow()
    inv.execution_time_ms = 45.2
    inv.turns_used = 2
    inv.tool_calls_count = 1
    inv.evidence_count = 2
    inv.claims_count = 2
    inv.robustness_status = "STABLE"
    inv.result_json = json.dumps(mock_payload)

    test_db_session.commit()

    queried = test_db_session.query(Investigation).filter_by(investigation_id="inv_test_02").first()
    assert queried.status == "COMPLETED"
    assert queried.completed_at is not None
    assert queried.execution_time_ms == 45.2
    assert queried.robustness_status == "STABLE"
    assert "Electronics" in queried.result_json


def test_persist_failed_investigation(test_db_session):
    """
    Verifies persisting a FAILED investigation record with error_message.
    """
    inv = Investigation(
        investigation_id="inv_test_03",
        question="Query resulting in database failure",
        status=InvestigationStatus.FAILED.value,
        completed_at=utcnow(),
        error_message="Database session connection timeout."
    )
    test_db_session.add(inv)
    test_db_session.commit()

    queried = test_db_session.query(Investigation).filter_by(investigation_id="inv_test_03").first()
    assert queried.status == "FAILED"
    assert queried.error_message == "Database session connection timeout."


def test_persist_requires_review_investigation(test_db_session):
    """
    Verifies persisting a REQUIRES_REVIEW status for sensitive findings.
    """
    inv = Investigation(
        investigation_id="inv_test_04",
        question="What is our revenue sensitivity?",
        status=InvestigationStatus.REQUIRES_REVIEW.value,
        robustness_status="SENSITIVE",
        completed_at=utcnow()
    )
    test_db_session.add(inv)
    test_db_session.commit()

    queried = test_db_session.query(Investigation).filter_by(investigation_id="inv_test_04").first()
    assert queried.status == "REQUIRES_REVIEW"
    assert queried.robustness_status == "SENSITIVE"


def test_pydantic_investigation_summary_validation(test_db_session):
    """
    Verifies Pydantic InvestigationSummary validation from ORM instance.
    """
    inv = test_db_session.query(Investigation).filter_by(investigation_id="inv_test_02").first()
    summary = InvestigationSummary.model_validate(inv)

    assert summary.investigation_id == "inv_test_02"
    assert summary.question == "What is our profit margin by category?"
    assert summary.status == "COMPLETED"
    assert summary.robustness_status == "STABLE"
    assert summary.turns_used == 2
    assert summary.evidence_count == 2


def test_pydantic_investigation_detail_validation(test_db_session):
    """
    Verifies Pydantic InvestigationDetail validation including result_json.
    """
    inv = test_db_session.query(Investigation).filter_by(investigation_id="inv_test_02").first()
    detail = InvestigationDetail.model_validate(inv)

    assert detail.investigation_id == "inv_test_02"
    assert detail.result_json is not None
    assert "Electronics" in detail.result_json
