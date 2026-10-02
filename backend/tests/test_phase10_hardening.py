"""
VERIDEX Phase 10 System Hardening Regression Tests.
Covers Security, SQL Safety, Tool Registry isolation, Claim Verification edge cases,
Insufficient Evidence handling, Review Lifecycle, Reassessment, and Audit Logging.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.db import get_db
from app.tools.sql_tool import validate_sql_safety, execute_read_only_sql
from app.schemas.sql_tool import SQLQueryRequest
from app.tools.registry import ToolRegistry
from app.services.claim_checker import verify_answer
from app.schemas.evidence import EvidenceItem, EvidenceSource, DerivedFactCalculation
from app.schemas.ai import AskResponse
from app.services.campaign_impact import campaign_impact
from app.services.driver_decomposition import decompose_change
from app.services.investigation_service import InvestigationService
from app.services.audit_logger import AuditLogger
from app.schemas.investigation import InvestigationReviewCreate


client = TestClient(app)


# -------------------------------------------------------------------
# Phase 10.B — SQL Safety Tests
# -------------------------------------------------------------------

def test_sql_safety_select_allowed():
    is_valid, err_type, err_msg = validate_sql_safety("SELECT * FROM orders WHERE quarter = 'Q1'")
    assert is_valid is True
    assert err_type is None


def test_sql_safety_insert_rejected():
    is_valid, err_type, err_msg = validate_sql_safety("INSERT INTO orders (order_id) VALUES (999)")
    assert is_valid is False
    assert err_type == "UNSAFE_SQL"
    assert "Prohibited modification" in err_msg or "Only SELECT" in err_msg


def test_sql_safety_update_rejected():
    is_valid, err_type, err_msg = validate_sql_safety("UPDATE orders SET revenue = 0 WHERE order_id = 1")
    assert is_valid is False
    assert err_type == "UNSAFE_SQL"


def test_sql_safety_delete_rejected():
    is_valid, err_type, err_msg = validate_sql_safety("DELETE FROM orders")
    assert is_valid is False
    assert err_type == "UNSAFE_SQL"


def test_sql_safety_drop_rejected():
    is_valid, err_type, err_msg = validate_sql_safety("DROP TABLE orders")
    assert is_valid is False
    assert err_type == "UNSAFE_SQL"


def test_sql_safety_alter_rejected():
    is_valid, err_type, err_msg = validate_sql_safety("ALTER TABLE orders ADD COLUMN hack text")
    assert is_valid is False
    assert err_type == "UNSAFE_SQL"


def test_sql_safety_multi_statement_rejected():
    is_valid, err_type, err_msg = validate_sql_safety("SELECT * FROM orders; DROP TABLE orders;")
    assert is_valid is False
    assert err_type == "UNSAFE_SQL"
    assert "Multi-statement" in err_msg


def test_sql_safety_malformed_syntax():
    is_valid, err_type, err_msg = validate_sql_safety("SELECT FROM WHERE WHERE")
    assert is_valid is False
    assert err_type == "SYNTAX_ERROR"


# -------------------------------------------------------------------
# Phase 10.C — Tool Registry Hardening Tests
# -------------------------------------------------------------------

def test_tool_registry_unknown_tool(test_db_session):
    registry = ToolRegistry()
    res = registry.execute_tool("non_existent_tool", test_db_session, {})
    assert res.success is False
    assert res.error_type == "UNSUPPORTED_TOOL"
    assert "Unsupported tool requested" in res.error_message


def test_tool_registry_tool_execution_error_isolation(test_db_session):
    registry = ToolRegistry()
    # Execute driver decomposition with missing period parameters to test argument validation isolation
    res = registry.execute_tool("driver_decomposition", test_db_session, {"metric": "invalid_metric"})
    assert res.success is False
    assert res.error_type in ("MALFORMED_ARGUMENT", "TOOL_EXECUTION_ERROR", "DRIVER_DECOMPOSITION_ERROR")


# -------------------------------------------------------------------
# Phase 10.D — Claim Verification Edge Cases
# -------------------------------------------------------------------

def test_claim_checker_percentages_and_currency():
    evidence = [
        EvidenceItem(
            evidence_id="E-01",
            evidence_type="FACT",
            description="Revenue and margin figures",
            source=EvidenceSource(
                source_type="sql_query",
                sql="SELECT revenue, margin FROM stats",
                query_hash="hash_1",
                timestamp="2026-10-02T12:00:00Z",
                columns=["revenue", "margin"],
                relevant_rows=[{"revenue": 4820000.0, "margin": 31.4}]
            )
        )
    ]
    answer_text = "North revenue reached $4.82M with a margin of 31.4%."
    res = verify_answer(answer_text, evidence)
    assert res.status == "PASS"
    assert len(res.verified) >= 1
    assert res.unverified_count == 0


def test_claim_checker_entity_ids_not_parsed_as_claims():
    evidence = [
        EvidenceItem(
            evidence_id="E-01",
            evidence_type="FACT",
            description="Order record ORD-101 for customer CUST-202",
            source=EvidenceSource(
                source_type="sql_query",
                sql="SELECT order_id FROM orders",
                query_hash="hash_2",
                timestamp="2026-10-02T12:00:00Z",
                columns=["order_id"],
                relevant_rows=[{"order_id": "ORD-101"}]
            )
        )
    ]
    answer_text = "Order ORD-101 was shipped for customer CUST-202 on PRD-303."
    res = verify_answer(answer_text, evidence)
    assert res.status == "PASS"
    assert res.total_claims == 0  # Entity IDs skipped from numerical parsing


def test_claim_checker_unsupported_claim_rejection():
    evidence = [
        EvidenceItem(
            evidence_id="E-01",
            evidence_type="FACT",
            description="Actual revenue data",
            source=EvidenceSource(
                source_type="sql_query",
                sql="SELECT revenue FROM stats",
                query_hash="hash_3",
                timestamp="2026-10-02T12:00:00Z",
                columns=["revenue"],
                relevant_rows=[{"revenue": 100.0}]
            )
        )
    ]
    answer_text = "Revenue was 999.0 for the quarter."
    res = verify_answer(answer_text, evidence)
    assert res.status == "FAIL"
    assert res.unverified_count == 1
    assert res.unverified[0].normalized_value == 999.0


# -------------------------------------------------------------------
# Phase 10.E — Insufficient Evidence Handling
# -------------------------------------------------------------------

def test_campaign_impact_insufficient_sample_size(test_db_session):
    res = campaign_impact(test_db_session, campaign_id="CMP-2025-Q3-SOUTH", min_sample_size=100000)
    assert res.status in ("INSUFFICIENT_DATA", "INSUFFICIENT_EVIDENCE")


# -------------------------------------------------------------------
# Phase 10.G & H — Review Lifecycle, Self-Review, and Reassessment
# -------------------------------------------------------------------

def test_owner_self_review_prevention(test_db_session):
    service = InvestigationService(test_db_session)
    ask_resp = AskResponse(
        success=True,
        question="Can owner review own investigation?",
        answer="Answer text",
        summary="Summary text",
        evidence=[],
        claims=[]
    )
    inv = service.create_investigation(
        db=test_db_session,
        question="Can owner review own investigation?",
        response=ask_resp,
        owner_id="usr_analyst_01"
    )

    with pytest.raises(ValueError) as exc_info:
        service.update_review(
            investigation_id=inv.investigation_id,
            review_decision="APPROVED",
            reviewer_notes="Self review attempt",
            reviewer_user_id="usr_analyst_01"  # Same as owner_id
        )
    assert "self-review" in str(exc_info.value).lower()


def test_valid_reviewer_approval_lifecycle(test_db_session):
    service = InvestigationService(test_db_session)
    ask_resp = AskResponse(
        success=True,
        question="Test review lifecycle?",
        answer="Answer text",
        summary="Summary text",
        evidence=[],
        claims=[]
    )
    inv = service.create_investigation(
        db=test_db_session,
        question="Test review lifecycle?",
        response=ask_resp,
        owner_id="usr_analyst_01"
    )

    # Valid review by reviewer_01
    updated_inv = service.update_review(
        investigation_id=inv.investigation_id,
        review_decision="APPROVED",
        reviewer_notes="Verified by lead reviewer.",
        reviewer_user_id="usr_reviewer_01"
    )
    assert updated_inv.review_status == "APPROVED"
    assert len(updated_inv.reviews) >= 1
    review_rec = updated_inv.reviews[0]
    reviewer_id_val = getattr(review_rec, "reviewer_id", None) or getattr(review_rec, "user_id", None)
    assert reviewer_id_val == "usr_reviewer_01"
    assert review_rec.review_notes == "Verified by lead reviewer."


# -------------------------------------------------------------------
# Phase 10.K — Audit Logging
# -------------------------------------------------------------------

def test_audit_logger_recording(test_db_session):
    AuditLogger.record_event(
        db=test_db_session,
        action_type="TEST_HARDENING_EVENT",
        user_id="usr_analyst_01",
        user_role="ANALYST",
        resource_id="inv_test_10",
        status="SUCCESS",
        details="Phase 10 system hardening verification."
    )

    logs = AuditLogger.list_audit_logs(db=test_db_session, action_type="TEST_HARDENING_EVENT")
    assert len(logs) >= 1
    assert logs[0].user_id == "usr_analyst_01"
    assert logs[0].action_type == "TEST_HARDENING_EVENT"
    assert logs[0].status == "SUCCESS"
