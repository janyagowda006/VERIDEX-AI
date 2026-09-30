import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.core.db import get_db
from app.services.investigation_service import InvestigationService
from app.services.report_exporter import ReportExporter
from app.schemas.ai import AskResponse, ClaimEvidence, ToolCallRecord
from app.schemas.evidence import EvidenceItem, EvidenceType, EvidenceSource, DerivedFactCalculation
from app.schemas.decision import DecisionAnalysis, Recommendation, RobustnessCheck
from app.schemas.investigation import InvestigationReviewCreate


@pytest.fixture
def client(test_db_session):
    def override_get_db():
        try:
            yield test_db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()



def test_report_exporter_json_and_markdown(test_db_session):
    """
    Verifies ReportExporter produces structured JSON and human-readable Markdown reports
    containing evidence provenance, turn timelines, and human review records.
    """
    # 1. Create investigation record
    inv = InvestigationService.create_investigation(
        db=test_db_session,
        question="What is our gross revenue by region?"
    )

    # 2. Build mock AskResponse with claims, evidence, analysis, tool calls
    source = EvidenceSource(
        source_type="sql_query",
        query_hash="8f9a2b1c4e7d3f5a6b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a",
        sql="SELECT c.region, SUM(oi.quantity * oi.unit_price) FROM orders o GROUP BY c.region",
        timestamp="2026-09-30T00:35:00Z",
        columns=["region", "gross_revenue"],
        relevant_rows=[{"region": "North", "gross_revenue": 1200000.0}],
        execution_metadata={"execution_time_ms": 14.2, "row_count": 1}
    )

    evidence_item = EvidenceItem(
        evidence_id="ev_fact_1",
        evidence_type=EvidenceType.FACT,
        description="Turn 1 SQL query execution output.",
        source=source
    )

    calc_item = EvidenceItem(
        evidence_id="ev_derived_1",
        evidence_type=EvidenceType.DERIVED_FACT,
        description="North is 26.32% higher than South.",
        calculation=DerivedFactCalculation(
            formula_name="percentage_change",

            formula="((1200000 - 950000) / 950000) * 100",
            inputs={"North": 1200000.0, "South": 950000.0},
            output=26.32,
            input_evidence_ids=["ev_fact_1"]
        )
    )

    rec = Recommendation(
        recommendation_id="rec_1",
        action_title="Prioritize Region 'North'",
        rationale="Observed top performance in 'North' with gross_revenue = 1200000.0.",
        supporting_evidence_ids=["ev_fact_1"],
        relevant_claim_ids=["claim_1"],
        robustness_status="STABLE"
    )

    analysis = DecisionAnalysis(
        analysis_id="anal_1",
        summary="Decision analysis completed.",
        recommendation=rec,
        robustness=RobustnessCheck(
            check_id="rob_1",
            status="STABLE",
            baseline_scenario={"scenario_name": "baseline"},
            explanation="Findings remain stable"
        )
    )

    response = AskResponse(
        success=True,
        question=inv.question,
        answer="North region generated top gross revenue at ₹1,200,000.",
        claims=[
            ClaimEvidence(
                claim_id="claim_1",
                claim_text="Database query execution returned factual metrics.",
                evidence_ids=["ev_fact_1"],
                evidence_type=EvidenceType.FACT,
                is_supported=True
            )
        ],
        evidence=[evidence_item, calc_item],
        analysis=analysis,
        metadata={"total_turns": 1, "robustness_status": "STABLE"}
    )

    InvestigationService.update_investigation_success(
        db=test_db_session,
        investigation_id=inv.investigation_id,
        response=response,
        execution_time_ms=14.2
    )

    # 3. Create Turn 1 & Human Review
    InvestigationService.create_turn(
        db=test_db_session,
        investigation_id=inv.investigation_id,
        user_question=inv.question,
        response=response,
        execution_time_ms=14.2
    )

    InvestigationService.create_review(
        db=test_db_session,
        investigation_id=inv.investigation_id,
        review_data=InvestigationReviewCreate(
            review_status="APPROVED",
            reviewer_id="lead_analyst_01",
            review_notes="Verified against Q3 revenue audit."
        )
    )

    # Test JSON Export
    json_data = ReportExporter.export_as_json(test_db_session, inv.investigation_id)
    assert json_data["veridex_report_version"] == "1.0"
    assert json_data["investigation"]["investigation_id"] == inv.investigation_id
    assert json_data["investigation"]["status"] == "COMPLETED"
    assert len(json_data["claims"]) == 1
    assert json_data["claims"][0]["claim_id"] == "claim_1"
    assert len(json_data["evidence"]) == 2
    assert json_data["evidence"][0]["source"]["query_hash"] == "8f9a2b1c4e7d3f5a6b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a"
    assert len(json_data["turns"]) == 1
    assert json_data["turns"][0]["turn_number"] == 1
    assert len(json_data["reviews"]) == 1
    assert json_data["reviews"][0]["reviewer_id"] == "lead_analyst_01"

    # Test Markdown Export
    md_text = ReportExporter.export_as_markdown(test_db_session, inv.investigation_id)
    assert "# VERIDEX Executive Audit Report" in md_text
    assert inv.investigation_id in md_text
    assert "Prioritize Region 'North'" in md_text
    assert "8f9a2b1c4e7d3f5a6b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a" in md_text
    assert "lead_analyst_01" in md_text


def test_report_exporter_nonexistent_raises_value_error(test_db_session):
    """
    Verifies ReportExporter raises ValueError for unknown investigation ID.
    """
    with pytest.raises(ValueError, match="Investigation 'inv_nonexistent_000' not found"):
        ReportExporter.export_as_json(test_db_session, "inv_nonexistent_000")


def test_export_endpoint_json_and_markdown(client, test_db_session):
    """
    Verifies GET /api/investigations/{id}/export returns JSON or Markdown file responses
    and handles 404 and 400 invalid format errors cleanly.
    """
    inv = InvestigationService.create_investigation(
        db=test_db_session,
        question="Export API endpoint test question"
    )

    # JSON export
    res_json = client.get(f"/api/investigations/{inv.investigation_id}/export?format=json")
    assert res_json.status_code == 200
    assert res_json.headers["content-type"] == "application/json"
    assert res_json.json()["investigation"]["investigation_id"] == inv.investigation_id

    # Markdown export
    res_md = client.get(f"/api/investigations/{inv.investigation_id}/export?format=markdown")
    assert res_md.status_code == 200
    assert "text/markdown" in res_md.headers["content-type"]
    assert "# VERIDEX Executive Audit Report" in res_md.text

    # 404 Unknown ID
    res_404 = client.get("/api/investigations/inv_fake_9999/export?format=json")
    assert res_404.status_code == 404

    # 400 Invalid format (e.g. pdf or invalid string)
    res_400 = client.get(f"/api/investigations/{inv.investigation_id}/export?format=pdf")
    assert res_400.status_code == 400
    assert "Unsupported export format" in res_400.json()["detail"]
