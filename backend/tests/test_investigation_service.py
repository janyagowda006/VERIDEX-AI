import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.exc import SQLAlchemyError

from app.models.business_data import Base
from app.models.investigation import Investigation, InvestigationAuditLog
from app.schemas.investigation import (
    InvestigationStatus,
    ReviewStatus,
    ReviewDecision,
    InvestigationSummary,
    InvestigationDetailResponse,
)
from app.schemas.ai import AskResponse, ToolCallRecord
from app.schemas.evidence import EvidenceItem, EvidenceType, ClaimEvidence, EvidenceSource
from app.schemas.decision import (
    DecisionAnalysis,
    Recommendation,
    RobustnessCheck,
    RobustnessScenario
)
from app.schemas.sql_tool import SQLQueryResult, QueryMetadata
from app.services.investigation_service import (
    InvestigationService,
    InvestigationNotFoundError,
    InvestigationValidationError,
)


@pytest.fixture
def test_db():
    """
    Isolated in-memory SQLite database session for service layer tests.
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


@pytest.fixture
def service():
    return InvestigationService()


@pytest.fixture
def sample_ask_response():
    """
    Constructs a comprehensive, valid AskResponse containing nested claims,
    evidence items, decision analysis, and tool calls.
    """
    meta = QueryMetadata(
        execution_time_ms=12.5,
        row_count=1,
        columns=["region", "revenue"],
        truncated=False,
        query_hash="hash_abc123",
        timestamp="2026-09-30T12:00:00Z"
    )
    sql_res = SQLQueryResult(
        success=True,
        sql="SELECT region, revenue FROM regional_sales ORDER BY revenue DESC LIMIT 1;",
        data=[{"region": "North", "revenue": 150000.0}],
        columns=["region", "revenue"],
        row_count=1,
        metadata=meta
    )
    tool_rec = ToolCallRecord(
        turn=1,
        tool_name="sql_query",
        arguments={"sql": "SELECT region, revenue FROM regional_sales;"},
        result=sql_res
    )
    ev_source = EvidenceSource(
        source_type="sql_query",
        query_hash="hash_abc123",
        sql="SELECT region, revenue FROM regional_sales ORDER BY revenue DESC LIMIT 1;",
        timestamp="2026-09-30T12:00:00Z",
        columns=["region", "revenue"],
        relevant_rows=[{"region": "North", "revenue": 150000.0}],
        execution_metadata={"execution_time_ms": 12.5, "row_count": 1, "truncated": False}
    )
    ev_item = EvidenceItem(
        evidence_id="ev_fact_1",
        evidence_type=EvidenceType.FACT,
        description="North region revenue from verified database query.",
        source=ev_source,
        limitations=[]
    )
    claim = ClaimEvidence(
        claim_id="claim_1",
        claim_text="North region generated the highest revenue ($150,000).",
        evidence_ids=["ev_fact_1"],
        evidence_type=EvidenceType.FACT,
        is_supported=True
    )
    rob_check = RobustnessCheck(
        check_id="rob_chk_1",
        status="STABLE",
        baseline_scenario=RobustnessScenario(
            scenario_name="baseline",
            assumptions={"variance": 0.0},
            result_summary={"rank_1": "North"}
        ),
        alternate_scenarios=[],
        explanation="Outcome holds across outlier perturbations.",
        supporting_evidence_ids=["ev_fact_1"]
    )
    analysis = DecisionAnalysis(
        analysis_id="anal_dec_1",
        summary="North region is the strongest candidate for expansion.",
        criteria_evaluated=[],
        rankings=[{"region": "North", "score": 95.0, "rank": 1}],
        recommendation=Recommendation(
            recommendation_id="rec_1",
            action_title="Allocate marketing budget to North region",
            rationale="Highest verified revenue with stable performance under sensitivity testing.",
            supporting_evidence_ids=["ev_fact_1"],
            robustness_status="STABLE"
        ),
        robustness=rob_check
    )

    return AskResponse(
        success=True,
        question="What is our highest performing region?",
        answer="North region generated the highest revenue of $150,000.",
        claims=[claim],
        evidence=[ev_item],
        analysis=analysis,
        tool_calls=[tool_rec],
        metadata={"total_turns": 1, "model": "test-orchestrator"}
    )


# ==============================================================================
# 1. Create investigation from a valid AskResponse
# ==============================================================================
def test_create_investigation_from_valid_ask_response(test_db, service, sample_ask_response):
    inv = service.create_investigation(
        db=test_db,
        question=sample_ask_response.question,
        response=sample_ask_response
    )
    assert inv is not None
    assert inv.investigation_id is not None
    assert inv.investigation_id.startswith("inv_")
    assert inv.question == "What is our highest performing region?"
    assert inv.status == InvestigationStatus.COMPLETED.value
    assert inv.robustness_status == "STABLE"
    assert inv.review_status == ReviewStatus.PENDING.value
    assert inv.created_at is not None
    assert inv.completed_at is not None


# ==============================================================================
# 2. Persist claims/evidence/analysis/tool calls/metadata
# ==============================================================================
def test_persist_all_structured_components(test_db, service, sample_ask_response):
    inv = service.create_investigation(test_db, sample_ask_response.question, sample_ask_response)

    # Reload directly from DB to verify persistence in tables
    loaded = test_db.query(Investigation).filter_by(investigation_id=inv.investigation_id).first()
    assert loaded is not None

    # Claims
    assert len(loaded.claims_json) == 1
    assert loaded.claims_json[0]["claim_id"] == "claim_1"
    assert loaded.claims_json[0]["is_supported"] is True

    # Evidence
    assert len(loaded.evidence_json) == 1
    assert loaded.evidence_json[0]["evidence_id"] == "ev_fact_1"
    assert loaded.evidence_json[0]["evidence_type"] == "FACT"

    # Analysis
    assert loaded.analysis_json is not None
    assert loaded.analysis_json["analysis_id"] == "anal_dec_1"
    assert loaded.analysis_json["recommendation"]["action_title"] == "Allocate marketing budget to North region"
    assert loaded.analysis_json["robustness"]["status"] == "STABLE"

    # Tool calls
    assert len(loaded.tool_calls_json) == 1
    assert loaded.tool_calls_json[0]["tool_name"] == "sql_query"
    assert loaded.tool_calls_json[0]["result"]["success"] is True

    # Metadata
    assert loaded.metadata_json["total_turns"] == 1
    assert loaded.metadata_json["_response_state"]["success"] is True


# ==============================================================================
# 3. Retrieve investigation by ID
# ==============================================================================
def test_get_investigation_by_id(test_db, service, sample_ask_response):
    created = service.create_investigation(test_db, sample_ask_response.question, sample_ask_response)
    retrieved = service.get_investigation(test_db, created.investigation_id)

    assert retrieved is not None
    assert retrieved.investigation_id == created.investigation_id
    assert retrieved.question == created.question
    assert retrieved.answer == created.answer


# ==============================================================================
# 4. Return appropriate result for unknown ID
# ==============================================================================
def test_get_investigation_unknown_id(test_db, service):
    result = service.get_investigation(test_db, "inv_nonexistent_99999")
    assert result is None


# ==============================================================================
# 5. Reconstruct AskResponse exactly enough to preserve nested data
# ==============================================================================
def test_reconstruct_ask_response(test_db, service, sample_ask_response):
    inv = service.create_investigation(test_db, sample_ask_response.question, sample_ask_response)
    reconstructed = service.reconstruct_ask_response(inv)

    assert isinstance(reconstructed, AskResponse)
    assert reconstructed.success is True
    assert reconstructed.question == sample_ask_response.question
    assert reconstructed.answer == sample_ask_response.answer
    assert len(reconstructed.claims) == 1
    assert reconstructed.claims[0].claim_id == "claim_1"
    assert len(reconstructed.evidence) == 1
    assert reconstructed.evidence[0].evidence_id == "ev_fact_1"
    assert reconstructed.analysis is not None
    assert reconstructed.analysis.recommendation.action_title == "Allocate marketing budget to North region"
    assert len(reconstructed.tool_calls) == 1
    assert reconstructed.tool_calls[0].tool_name == "sql_query"
    assert reconstructed.metadata.get("total_turns") == 1
    # Verify response state is unpolluted in user metadata
    assert "_response_state" not in reconstructed.metadata


# ==============================================================================
# 6. List investigations newest-first
# ==============================================================================
def test_list_investigations_newest_first(test_db, service, sample_ask_response):
    base_time = datetime.now(timezone.utc)

    inv1 = service.create_investigation(test_db, "Question 1", sample_ask_response, investigation_id="inv_001")
    inv1.created_at = base_time - timedelta(minutes=10)

    inv2 = service.create_investigation(test_db, "Question 2", sample_ask_response, investigation_id="inv_002")
    inv2.created_at = base_time - timedelta(minutes=5)

    inv3 = service.create_investigation(test_db, "Question 3", sample_ask_response, investigation_id="inv_003")
    inv3.created_at = base_time

    test_db.commit()

    results = service.list_investigations(test_db, limit=10, offset=0)
    assert len(results) == 3
    # Newest first
    assert results[0].investigation_id == "inv_003"
    assert results[1].investigation_id == "inv_002"
    assert results[2].investigation_id == "inv_001"


# ==============================================================================
# 7. Pagination works
# ==============================================================================
def test_list_investigations_pagination(test_db, service, sample_ask_response):
    for i in range(5):
        service.create_investigation(test_db, f"Question {i}", sample_ask_response, investigation_id=f"inv_page_{i:02d}")

    page1 = service.list_investigations(test_db, limit=2, offset=0)
    page2 = service.list_investigations(test_db, limit=2, offset=2)
    page3 = service.list_investigations(test_db, limit=2, offset=4)

    assert len(page1) == 2
    assert len(page2) == 2
    assert len(page3) == 1

    ids_page1 = [inv.investigation_id for inv in page1]
    ids_page2 = [inv.investigation_id for inv in page2]
    ids_page3 = [inv.investigation_id for inv in page3]

    # No overlap
    assert set(ids_page1).isdisjoint(set(ids_page2))
    assert set(ids_page2).isdisjoint(set(ids_page3))


# ==============================================================================
# 8. Pagination bounds are enforced
# ==============================================================================
def test_pagination_bounds_enforced(test_db, service):
    with pytest.raises(ValueError) as exc:
        service.list_investigations(test_db, limit=10, offset=-1)
    assert "offset" in str(exc.value).lower()

    with pytest.raises(ValueError) as exc:
        service.list_investigations(test_db, limit=0, offset=0)
    assert "limit" in str(exc.value).lower()

    with pytest.raises(ValueError) as exc:
        service.list_investigations(test_db, limit=101, offset=0)
    assert "limit" in str(exc.value).lower()


# ==============================================================================
# 9. Summary does not expose full evidence payload unnecessarily
# ==============================================================================
def test_summary_mapping_does_not_expose_full_evidence(test_db, service, sample_ask_response):
    inv = service.create_investigation(test_db, sample_ask_response.question, sample_ask_response)
    summary = service.to_summary(inv)

    assert isinstance(summary, InvestigationSummary)
    assert summary.investigation_id == inv.investigation_id
    assert summary.question == inv.question
    assert summary.status == "COMPLETED"
    assert summary.robustness_status == "STABLE"
    assert summary.review_status == "PENDING"
    assert summary.top_finding == "Allocate marketing budget to North region"

    # Verify that raw evidence and claims payloads are not on the summary
    summary_dict = summary.model_dump()
    assert "evidence" not in summary_dict
    assert "claims" not in summary_dict
    assert "tool_calls" not in summary_dict
    assert "evidence_json" not in summary_dict


# ==============================================================================
# 10. Review APPROVED works
# ==============================================================================
def test_review_approved(test_db, service, sample_ask_response):
    inv = service.create_investigation(test_db, sample_ask_response.question, sample_ask_response)
    updated = service.update_review(
        test_db,
        inv.investigation_id,
        ReviewDecision.APPROVED,
        "Findings verified by CFO."
    )
    assert updated.review_status == ReviewStatus.APPROVED.value

    # Verify reload from DB
    reloaded = test_db.query(Investigation).filter_by(investigation_id=inv.investigation_id).first()
    assert reloaded.review_status == "APPROVED"


# ==============================================================================
# 11. Review REJECTED works
# ==============================================================================
def test_review_rejected(test_db, service, sample_ask_response):
    inv = service.create_investigation(test_db, sample_ask_response.question, sample_ask_response)
    updated = service.update_review(
        test_db,
        inv.investigation_id,
        ReviewDecision.REJECTED,
        "Underlying SQL excluded return discounts."
    )
    assert updated.review_status == ReviewStatus.REJECTED.value


# ==============================================================================
# 12. Review FLAGGED works
# ==============================================================================
def test_review_flagged(test_db, service, sample_ask_response):
    inv = service.create_investigation(test_db, sample_ask_response.question, sample_ask_response)
    updated = service.update_review(
        test_db,
        inv.investigation_id,
        ReviewDecision.FLAGGED,
        "Requires deep dive by data governance."
    )
    assert updated.review_status == ReviewStatus.FLAGGED.value


# ==============================================================================
# 13. Invalid review status is rejected
# ==============================================================================
def test_invalid_review_status_rejected(test_db, service, sample_ask_response):
    inv = service.create_investigation(test_db, sample_ask_response.question, sample_ask_response)

    with pytest.raises(ValueError):
        service.update_review(test_db, inv.investigation_id, "ACCEPTED", "Invalid status")

    with pytest.raises(ValueError):
        service.update_review(test_db, inv.investigation_id, "MAYBE", "Invalid status")

    with pytest.raises(ValueError):
        service.update_review(test_db, inv.investigation_id, "", "Blank status")


# ==============================================================================
# 14. Review of nonexistent investigation is rejected appropriately
# ==============================================================================
def test_review_nonexistent_investigation_rejected(test_db, service):
    with pytest.raises(InvestigationNotFoundError):
        service.update_review(test_db, "inv_ghost_id", ReviewDecision.APPROVED, "No one home")


# ==============================================================================
# 15. Audit log is created for each review action
# ==============================================================================
def test_audit_log_created_for_review_action(test_db, service, sample_ask_response):
    inv = service.create_investigation(test_db, sample_ask_response.question, sample_ask_response)
    service.update_review(test_db, inv.investigation_id, ReviewDecision.APPROVED, "Verified")

    logs = test_db.query(InvestigationAuditLog).filter_by(investigation_id=inv.investigation_id).all()
    review_logs = [l for l in logs if l.event_type == "HUMAN_REVIEW_UPDATED"]
    assert len(review_logs) == 1
    assert review_logs[0].review_status == "APPROVED"
    assert review_logs[0].reviewer_notes == "Verified"


# ==============================================================================
# 16. Multiple review actions preserve audit history
# ==============================================================================
def test_multiple_reviews_preserve_audit_history(test_db, service, sample_ask_response):
    inv = service.create_investigation(test_db, sample_ask_response.question, sample_ask_response)

    # 1st review: APPROVED
    service.update_review(test_db, inv.investigation_id, ReviewDecision.APPROVED, "First pass: approved.")
    # 2nd review: FLAGGED
    service.update_review(test_db, inv.investigation_id, ReviewDecision.FLAGGED, "Second pass: wait, check Q4 numbers.")
    # 3rd review: REJECTED
    service.update_review(test_db, inv.investigation_id, ReviewDecision.REJECTED, "Third pass: numbers contradicted.")

    reloaded = test_db.query(Investigation).filter_by(investigation_id=inv.investigation_id).first()
    assert reloaded.review_status == "REJECTED"

    # All audit events are preserved
    audit_events = [l.event_type for l in reloaded.audit_logs]
    assert audit_events.count("HUMAN_REVIEW_UPDATED") == 3
    assert audit_events.count("INVESTIGATION_COMPLETED") == 1

    decisions = [l.review_status for l in reloaded.audit_logs if l.event_type == "HUMAN_REVIEW_UPDATED"]
    assert "APPROVED" in decisions
    assert "FLAGGED" in decisions
    assert "REJECTED" in decisions


# ==============================================================================
# 17. Database failure rolls back cleanly
# ==============================================================================
def test_database_failure_rolls_back_cleanly(test_db, service, sample_ask_response):
    with patch.object(test_db, "commit", side_effect=SQLAlchemyError("Simulated DB Disk Full")):
        with patch.object(test_db, "rollback", wraps=test_db.rollback) as mock_rollback:
            with pytest.raises(SQLAlchemyError):
                service.create_investigation(test_db, sample_ask_response.question, sample_ask_response)
            mock_rollback.assert_called_once()


# ==============================================================================
# 18. InvestigationDetailResponse integration via service
# ==============================================================================
def test_get_investigation_detail_integration(test_db, service, sample_ask_response):
    inv = service.create_investigation(test_db, sample_ask_response.question, sample_ask_response)
    service.update_review(test_db, inv.investigation_id, ReviewDecision.APPROVED, "Executive sign-off.")

    detail = service.get_investigation_detail(test_db, inv.investigation_id)
    assert detail is not None
    assert isinstance(detail, InvestigationDetailResponse)
    assert detail.investigation_id == inv.investigation_id
    assert detail.review_status == "APPROVED"
    assert detail.reviewer_notes == "Executive sign-off."
    assert detail.response.question == sample_ask_response.question
    assert len(detail.audit_trail) >= 2
    assert detail.audit_trail[-1].event_type == "HUMAN_REVIEW_UPDATED"
