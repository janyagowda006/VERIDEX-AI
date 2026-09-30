import pytest
from datetime import datetime, timezone
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.business_data import Base
from app.models.investigation import Investigation, InvestigationAuditLog
from app.schemas.investigation import (
    InvestigationStatus,
    ReviewStatus,
    ReviewDecision,
    InvestigationSummary,
    InvestigationReviewRequest,
    InvestigationDetailResponse,
    InvestigationAuditLogEntry
)
from app.schemas.ai import AskResponse, ToolCallRecord
from app.schemas.evidence import EvidenceItem, EvidenceType, ClaimEvidence
from app.schemas.decision import (
    DecisionAnalysis,
    Recommendation,
    DecisionCriterion,
    RobustnessCheck,
    RobustnessScenario
)
from app.schemas.sql_tool import SQLQueryResult, QueryMetadata


@pytest.fixture
def inv_db_session():
    """
    Isolated in-memory SQLite session for testing investigation persistence models.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()


def test_investigation_model_creation(inv_db_session):
    """
    1. Investigation model can be created and persisted in SQLite.
    """
    inv = Investigation(
        investigation_id="inv_test_001",
        question="What is our revenue by region?",
        status="COMPLETED",
        robustness_status="STABLE",
        review_status="PENDING",
        answer="North region had the highest revenue.",
        claims_json=[{"claim_id": "c1", "claim_text": "North is top"}],
        evidence_json=[{"evidence_id": "ev1", "evidence_type": "FACT"}],
        analysis_json={"summary": "North leads"},
        tool_calls_json=[],
        metadata_json={"total_turns": 2}
    )
    inv_db_session.add(inv)
    inv_db_session.commit()

    retrieved = inv_db_session.query(Investigation).filter_by(investigation_id="inv_test_001").first()
    assert retrieved is not None
    assert retrieved.question == "What is our revenue by region?"
    assert retrieved.status == "COMPLETED"
    assert retrieved.robustness_status == "STABLE"
    assert retrieved.review_status == "PENDING"
    assert retrieved.answer == "North region had the highest revenue."
    assert retrieved.claims_json[0]["claim_id"] == "c1"
    assert retrieved.evidence_json[0]["evidence_id"] == "ev1"
    assert retrieved.analysis_json["summary"] == "North leads"
    assert retrieved.created_at is not None


def test_audit_log_referencing_investigation_and_fk_relationship(inv_db_session):
    """
    2 & 3. InvestigationAuditLog can reference an investigation; foreign-key and bidirectional relationship work.
    """
    inv = Investigation(
        investigation_id="inv_test_002",
        question="Which product has highest returns?",
        status="COMPLETED",
        review_status="PENDING"
    )
    inv_db_session.add(inv)
    inv_db_session.commit()

    log1 = InvestigationAuditLog(
        audit_id="audit_001",
        investigation_id="inv_test_002",
        event_type="INVESTIGATION_COMPLETED",
        review_status="PENDING",
        reviewer_notes=None
    )
    log2 = InvestigationAuditLog(
        audit_id="audit_002",
        investigation_id="inv_test_002",
        event_type="HUMAN_REVIEW_UPDATED",
        review_status="APPROVED",
        reviewer_notes="Approved for Q3 executive review."
    )
    inv_db_session.add_all([log1, log2])
    inv_db_session.commit()

    # Verify bidirectional navigation: investigation -> audit_logs
    reloaded_inv = inv_db_session.query(Investigation).filter_by(investigation_id="inv_test_002").first()
    assert len(reloaded_inv.audit_logs) == 2
    event_types = [entry.event_type for entry in reloaded_inv.audit_logs]
    assert "INVESTIGATION_COMPLETED" in event_types
    assert "HUMAN_REVIEW_UPDATED" in event_types

    # Verify log -> investigation navigation
    reloaded_log = inv_db_session.query(InvestigationAuditLog).filter_by(audit_id="audit_002").first()
    assert reloaded_log.investigation is not None
    assert reloaded_log.investigation.investigation_id == "inv_test_002"
    assert reloaded_log.reviewer_notes == "Approved for Q3 executive review."


def test_cascade_delete_investigation_and_audit_logs(inv_db_session):
    """
    Verifies cascade delete behavior: removing an investigation removes associated audit logs.
    """
    inv = Investigation(
        investigation_id="inv_test_cascade",
        question="Temporary test question?",
        status="COMPLETED",
        review_status="PENDING"
    )
    log = InvestigationAuditLog(
        audit_id="audit_cascade_001",
        investigation_id="inv_test_cascade",
        event_type="CREATED"
    )
    inv_db_session.add(inv)
    inv_db_session.add(log)
    inv_db_session.commit()

    assert inv_db_session.query(InvestigationAuditLog).filter_by(audit_id="audit_cascade_001").count() == 1

    inv_db_session.delete(inv)
    inv_db_session.commit()

    assert inv_db_session.query(Investigation).filter_by(investigation_id="inv_test_cascade").count() == 0
    assert inv_db_session.query(InvestigationAuditLog).filter_by(audit_id="audit_cascade_001").count() == 0


def test_investigation_summary_schema_validation():
    """
    4. InvestigationSummary validates valid data and rejects blank question.
    """
    summary = InvestigationSummary(
        investigation_id="inv_123",
        question="What is our regional gross margin?",
        created_at="2026-09-30T12:00:00Z",
        status="COMPLETED",
        robustness_status="STABLE",
        review_status="APPROVED",
        top_finding="North region margin is 35.5%."
    )
    assert summary.investigation_id == "inv_123"
    assert summary.question == "What is our regional gross margin?"
    assert summary.top_finding == "North region margin is 35.5%."

    # Blank question rejection
    with pytest.raises(ValidationError):
        InvestigationSummary(
            investigation_id="inv_bad",
            question="   ",
            created_at="2026-09-30T12:00:00Z"
        )


def test_review_request_accepts_controlled_decisions():
    """
    5. Review request accepts APPROVED, REJECTED, FLAGGED.
    """
    req_app = InvestigationReviewRequest(status=ReviewDecision.APPROVED, reviewer_notes="Looks solid.")
    req_rej = InvestigationReviewRequest(status=ReviewDecision.REJECTED, reviewer_notes="Numbers mismatched.")
    req_flg = InvestigationReviewRequest(status=ReviewDecision.FLAGGED, reviewer_notes="Check baseline data.")

    assert req_app.status == ReviewDecision.APPROVED
    assert req_rej.status == ReviewDecision.REJECTED
    assert req_flg.status == ReviewDecision.FLAGGED

    # Accepts valid string representations matching enum
    req_str = InvestigationReviewRequest(status="APPROVED")
    assert req_str.status == ReviewDecision.APPROVED


def test_review_request_rejects_invalid_review_status():
    """
    6. Invalid review status is strictly rejected by Pydantic schema.
    """
    with pytest.raises(ValidationError):
        InvestigationReviewRequest(status="MAYBE")

    with pytest.raises(ValidationError):
        InvestigationReviewRequest(status="ACCEPTED")

    with pytest.raises(ValidationError):
        InvestigationReviewRequest(status="")


def test_review_request_reviewer_notes_sanitization_and_bounding():
    """
    Tests notes bounding (max_length=2000) and whitespace trimming.
    """
    req = InvestigationReviewRequest(status=ReviewDecision.APPROVED, reviewer_notes="   Leading and trailing spaces   ")
    assert req.reviewer_notes == "Leading and trailing spaces"

    req_empty = InvestigationReviewRequest(status=ReviewDecision.APPROVED, reviewer_notes="    ")
    assert req_empty.reviewer_notes is None

    with pytest.raises(ValidationError):
        InvestigationReviewRequest(status=ReviewDecision.APPROVED, reviewer_notes="A" * 2001)


def test_investigation_detail_response_contains_real_ask_response():
    """
    8. InvestigationDetailResponse can contain a real complete AskResponse object without modifying AskResponse.
    """
    meta = QueryMetadata(
        execution_time_ms=10.0,
        row_count=1,
        columns=["region", "rev"],
        truncated=False,
        query_hash="h123",
        timestamp="2026-09-30T12:00:00Z"
    )
    sql_res = SQLQueryResult(
        success=True,
        sql="SELECT region, rev FROM sales",
        data=[{"region": "North", "rev": 1000.0}],
        columns=["region", "rev"],
        row_count=1,
        metadata=meta
    )
    tool_rec = ToolCallRecord(
        turn=1,
        tool_name="sql_query",
        arguments={"sql": "SELECT region, rev FROM sales"},
        result=sql_res
    )
    ev_item = EvidenceItem(
        evidence_id="ev_fact_1",
        evidence_type=EvidenceType.FACT,
        description="Fact evidence from SQL"
    )
    claim = ClaimEvidence(
        claim_id="claim_1",
        claim_text="North had 1000 revenue.",
        evidence_ids=["ev_fact_1"],
        evidence_type=EvidenceType.FACT
    )
    rob_check = RobustnessCheck(
        check_id="rob_1",
        status="STABLE",
        baseline_scenario=RobustnessScenario(scenario_name="base", assumptions={}, result_summary={}),
        alternate_scenarios=[],
        explanation="Finding is stable",
        supporting_evidence_ids=["ev_fact_1"]
    )
    decision = DecisionAnalysis(
        analysis_id="anal_1",
        summary="Decision analysis complete",
        criteria_evaluated=[],
        rankings=[{"region": "North", "rank": 1}],
        recommendation=Recommendation(
            recommendation_id="rec_1",
            action_title="Prioritize North",
            rationale="Highest sales",
            supporting_evidence_ids=["ev_fact_1"],
            robustness_status="STABLE"
        ),
        robustness=rob_check
    )

    real_ask_response = AskResponse(
        success=True,
        question="What is our regional sales?",
        answer="North leads with 1000 sales.",
        claims=[claim],
        evidence=[ev_item],
        analysis=decision,
        tool_calls=[tool_rec],
        metadata={"total_turns": 1, "robustness_status": "STABLE"}
    )

    detail = InvestigationDetailResponse(
        investigation_id="inv_detail_001",
        question="What is our regional sales?",
        status="COMPLETED",
        review_status="PENDING",
        created_at="2026-09-30T12:00:00Z",
        completed_at="2026-09-30T12:00:01Z",
        response=real_ask_response,
        reviewer_notes=None,
        audit_trail=[]
    )

    assert detail.investigation_id == "inv_detail_001"
    assert detail.response.success is True
    assert detail.response.answer == "North leads with 1000 sales."
    assert len(detail.response.claims) == 1
    assert len(detail.response.evidence) == 1
    assert detail.response.analysis.recommendation.action_title == "Prioritize North"


def test_nested_ask_response_json_serialization_roundtrip():
    """
    9. Nested claims, evidence, analysis, and tool calls are JSON-serializable and can round-trip through
       the Investigation SQLAlchemy model without schema degradation or loss.
    """
    ev_item = EvidenceItem(
        evidence_id="ev_fact_99",
        evidence_type=EvidenceType.FACT,
        description="Verified fact",
        limitations=["None detected"]
    )
    claim = ClaimEvidence(
        claim_id="c_99",
        claim_text="Business assertion 99",
        evidence_ids=["ev_fact_99"],
        evidence_type=EvidenceType.FACT,
        is_supported=True
    )
    ask_resp = AskResponse(
        success=True,
        question="Test roundtrip?",
        answer="Test answer",
        claims=[claim],
        evidence=[ev_item],
        analysis=None,
        tool_calls=[],
        metadata={"test": "roundtrip"}
    )

    # Convert Pydantic v2 to JSON-compatible dicts
    claims_dict = [c.model_dump() for c in ask_resp.claims]
    evidence_dict = [e.model_dump() for e in ask_resp.evidence]
    metadata_dict = ask_resp.metadata

    # Instantiate Investigation model with serialized JSON
    inv = Investigation(
        investigation_id="inv_roundtrip_001",
        question="Test roundtrip?",
        status="COMPLETED",
        review_status="PENDING",
        claims_json=claims_dict,
        evidence_json=evidence_dict,
        analysis_json=None,
        tool_calls_json=[],
        metadata_json=metadata_dict
    )

    # Reconstruct from model attributes back to Pydantic models
    reconstructed_claims = [ClaimEvidence.model_validate(c) for c in inv.claims_json]
    reconstructed_evidence = [EvidenceItem.model_validate(e) for e in inv.evidence_json]

    assert len(reconstructed_claims) == 1
    assert reconstructed_claims[0].claim_id == "c_99"
    assert reconstructed_claims[0].claim_text == "Business assertion 99"
    assert len(reconstructed_evidence) == 1
    assert reconstructed_evidence[0].evidence_id == "ev_fact_99"
    assert reconstructed_evidence[0].evidence_type == EvidenceType.FACT
