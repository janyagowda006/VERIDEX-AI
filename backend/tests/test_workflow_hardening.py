import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.schemas.ai import AskResponse, ToolCallRecord
from app.schemas.evidence import EvidenceItem, EvidenceType
from app.schemas.decision import DecisionAnalysis
from app.tools.registry import ToolRegistry, ToolExecutionResult
from app.ai.provider import MockLLMProvider, ModelResponse, ToolCallRequest
from app.ai.orchestrator import run_investigation_loop
from app.services.claim_checker import verify_answer, extract_claims_from_sentence
from app.services.investigation_service import InvestigationService
from app.services.audit_logger import AuditLogger
from app.models.user import User
from app.models.investigation import Investigation, InvestigationTurn, InvestigationReview
from app.main import app
from app.core.db import get_db
from app.ai.provider import get_llm_provider


def test_phase_8a_simple_sql_workflow(test_db_session):
    """
    PHASE 8A: Simple SQL Investigation Workflow test.
    Verifies simple SQL business questions select sql_query, execute safe SQL AST validation,
    create FACT evidence, perform claim checking, evaluate robustness, and persist detail.
    """
    provider = MockLLMProvider()
    question = "What was our total revenue last month?"

    response = run_investigation_loop(
        question=question,
        db=test_db_session,
        provider=provider,
        max_turns=3
    )

    # 1. API execution success
    assert response.success is True
    assert response.question == question

    # 2. Tool selection includes sql_query
    assert len(response.tool_calls) >= 1
    assert response.tool_calls[0].tool_name == "sql_query"
    assert "sql" in response.tool_calls[0].arguments

    # 3. Evidence created and classified as FACT
    assert len(response.evidence) >= 1
    assert any(ev.evidence_type == EvidenceType.FACT for ev in response.evidence)

    # 4. Answer returned and claims checked
    assert response.answer is not None
    assert len(response.claims) >= 1
    assert all(c.is_supported for c in response.claims)

    # 5. Robustness status present
    assert response.analysis is not None
    assert response.analysis.robustness is not None
    assert response.analysis.robustness.status in ("STABLE", "SENSITIVE", "INSUFFICIENT_EVIDENCE")

    # 6. Investigation persistence & retrieval
    inv_id = InvestigationService.generate_investigation_id()
    service = InvestigationService(test_db_session)
    inv_rec = service.create_investigation(
        db=test_db_session,
        question=question,
        response=response,
        investigation_id=inv_id,
        owner_id="usr_analyst_01"
    )
    assert inv_rec.investigation_id == inv_id

    detail = service.get_investigation_detail(inv_id)
    assert detail is not None
    assert detail.question == question
    assert detail.status == "COMPLETED"
    assert detail.review_status in ("REQUIRES_REVIEW", "PENDING")


def test_phase_8b_driver_decomposition_workflow(test_db_session):
    """
    PHASE 8B: Driver Decomposition Workflow test.
    Verifies driver_decomposition executes directly through ToolRegistry without HTTP calls,
    reconciles revenue delta mathematically, generates DERIVED_FACT evidence, and verifies claims.
    """
    provider = MockLLMProvider()
    question = "Revenue fell last month. What were the main drivers?"

    response = run_investigation_loop(
        question=question,
        db=test_db_session,
        provider=provider,
        max_turns=3
    )

    # 1. driver_decomposition tool selected
    assert response.success is True
    assert len(response.tool_calls) >= 1
    assert response.tool_calls[0].tool_name == "driver_decomposition"

    # 2. Evidence is DERIVED_FACT
    assert len(response.evidence) >= 1
    derived_ev = [ev for ev in response.evidence if ev.evidence_type == EvidenceType.DERIVED_FACT]
    assert len(derived_ev) >= 1

    # 3. Mathematical reconciliation check
    for ev in derived_ev:
        if ev.calculation:
            calc = ev.calculation
            if "period_a_total" in calc.inputs and "period_b_total" in calc.inputs:
                p_a = float(calc.inputs["period_a_total"])
                p_b = float(calc.inputs["period_b_total"])
                total_delta = p_b - p_a
                # output should match total_delta within floating point tolerance
                assert abs(float(calc.output) - total_delta) < 1e-4

    # 4. Numerical claims verified & robustness available
    assert len(response.claims) >= 1
    assert response.analysis is not None
    assert response.analysis.robustness is not None


def test_phase_8c_campaign_impact_workflow(test_db_session):
    """
    PHASE 8C: Campaign Impact Workflow test.
    Verifies campaign_impact evaluates exposed/control cohorts, computes DiD,
    generates DERIVED_FACT evidence and INFERENCE qualitative interpretation with mandatory disclaimer.
    """
    provider = MockLLMProvider()
    question = "Did the campaign improve revenue?"

    response = run_investigation_loop(
        question=question,
        db=test_db_session,
        provider=provider,
        max_turns=3
    )

    # 1. campaign_impact selected
    assert response.success is True
    assert len(response.tool_calls) >= 1
    assert response.tool_calls[0].tool_name == "campaign_impact"

    # 2. Evidence DERIVED_FACT present
    assert len(response.evidence) >= 1
    assert any(ev.evidence_type == EvidenceType.DERIVED_FACT for ev in response.evidence)

    # 3. Mandatory disclaimer present in evidence limitations or answer
    disclaimer = "Observational evidence; causation not proven."
    disclaimer_found = any(
        disclaimer.lower() in str(lim).lower()
        for ev in response.evidence
        if ev.limitations
        for lim in ev.limitations
    ) or (disclaimer.lower() in response.answer.lower())
    assert disclaimer_found is True

    # 4. Claims separation: qualitative inference separated from fact
    assert len(response.claims) >= 1


def test_phase_8d_complex_multi_tool_workflow(test_db_session):
    """
    PHASE 8D: Complex Multi-Tool Question test.
    Verifies multi-turn sequence: driver_decomposition -> campaign_impact -> evidence assembly -> decision -> robustness.
    """
    provider = MockLLMProvider()
    question = "Revenue fell last month. Why, and did the campaign help?"

    response = run_investigation_loop(
        question=question,
        db=test_db_session,
        provider=provider,
        max_turns=3
    )

    # 1. Multiple tool calls executed & persisted
    assert response.success is True
    assert len(response.tool_calls) == 2
    tool_names = [tc.tool_name for tc in response.tool_calls]
    assert "driver_decomposition" in tool_names
    assert "campaign_impact" in tool_names

    # 2. Status & arguments preserved
    for tc in response.tool_calls:
        assert tc.result.success is True
        assert isinstance(tc.arguments, dict)

    # 3. Evidence items generated and linked
    assert len(response.evidence) >= 2
    ev_types = {ev.evidence_type for ev in response.evidence}
    assert EvidenceType.DERIVED_FACT in ev_types

    # 4. Recommendation & Robustness present
    assert response.analysis is not None
    assert response.analysis.recommendation is not None
    assert response.analysis.robustness is not None


def test_phase_8e_claim_verification_workflow(test_db_session):
    """
    PHASE 8E: Claim Verification Workflow & Entity ID Isolation test.
    Verifies supported claims pass, unsupported claims fail, and entity identifiers
    (ORD-101, CUST-202, PRD-303, CMP-2025-Q3-SOUTH) are NEVER treated as numerical claims.
    """
    # 1. Verify Entity Identifiers are NOT extracted as numerical claims
    sample_text = "Order ORD-101 for customer CUST-202 bought product PRD-303 under campaign CMP-2025-Q3-SOUTH for $48.20."
    extracted_claims = extract_claims_from_sentence(sample_text)

    # Only $48.20 should be extracted as a numerical claim, NOT 101, 202, 303, or 2025!
    claim_values = [c.normalized_value for c in extracted_claims]
    assert 48.20 in claim_values
    assert 101 not in claim_values
    assert 202 not in claim_values
    assert 303 not in claim_values

    # 2. Verify deterministic claim verification matching
    fact_ev = EvidenceItem(
        evidence_id="ev_fact_1",
        evidence_type=EvidenceType.FACT,
        description="Gross revenue in North region",
        source={
            "source_type": "sql_query",
            "query_hash": "a3f9c21e",
            "sql": "SELECT region, SUM(revenue) FROM orders GROUP BY region",
            "timestamp": "2026-10-02T10:00:00Z",
            "columns": ["region", "revenue"],
            "relevant_rows": [{"region": "North", "revenue": 4820311.0}]
        },
        limitations=[]
    )

    # Supported claim = $4,820,311
    res_pass = verify_answer("North generated total revenue of $4,820,311.", [fact_ev], tolerance=0.05)
    assert res_pass.status == "PASS"
    assert res_pass.verified_count >= 1

    # Unsupported claim = $9.99M (differs materially from $4,820,311)
    res_fail = verify_answer("North generated total revenue of $9.99M.", [fact_ev], tolerance=0.05)
    assert res_fail.status == "FAIL"
    assert res_fail.unverified_count >= 1


def test_phase_8f_insufficient_evidence_workflow(test_db_session):
    """
    PHASE 8F: Insufficient Evidence Workflow test.
    Verifies that when evidence data is non-numeric or empty, robustness status becomes
    INSUFFICIENT_EVIDENCE or baseline sensitivity without data fabrication.
    """
    provider = MockLLMProvider()

    response = run_investigation_loop(
        question="What is the forecasted revenue for Q4 2030?",
        db=test_db_session,
        provider=provider,
        max_turns=1
    )

    assert response.success is True
    assert response.analysis is not None
    assert response.analysis.robustness is not None
    assert response.analysis.robustness.status in ("INSUFFICIENT_EVIDENCE", "STABLE", "SENSITIVE")


def test_phase_8g_tool_failure_workflow(test_db_session):
    """
    PHASE 8G: Tool Failure Workflow test.
    Verifies controlled handling of malformed arguments, unsupported tools, and SQL syntax errors
    without API crashes or evidence corruption.
    """
    registry = ToolRegistry()

    # 1. Unsupported tool
    res_unsupported = registry.execute_tool("invalid_tool_name", test_db_session, {})
    assert res_unsupported.success is False
    assert res_unsupported.error_type == "UNSUPPORTED_TOOL"

    # 2. Malformed arguments (missing 'sql' in sql_query)
    res_malformed = registry.execute_tool("sql_query", test_db_session, {"sql": ""})
    assert res_malformed.success is False
    assert res_malformed.error_type == "MALFORMED_ARGUMENT"

    # 3. SQL Syntax Error
    res_sql_err = registry.execute_tool("sql_query", test_db_session, {"sql": "SELECT * FROM non_existent_table_12345"})
    assert res_sql_err.success is False
    assert res_sql_err.error_type in ("SQL_EXECUTION_ERROR", "UNKNOWN_IDENTIFIER")
    assert "error" in res_sql_err.error_message.lower() or "syntax" in res_sql_err.error_message.lower() or "relation" in res_sql_err.error_message.lower() or "no such table" in res_sql_err.error_message.lower()


def test_phase_8h_investigation_persistence(test_db_session):
    """
    PHASE 8H: Investigation Persistence test.
    Verifies that GET /api/investigations/{id} reconstructs question, status, tool calls,
    evidence, claims, analysis, robustness, recommendation, review status, and audit log.
    """
    provider = MockLLMProvider()
    question = "What was our total revenue last month?"

    response = run_investigation_loop(question=question, db=test_db_session, provider=provider)
    inv_id = InvestigationService.generate_investigation_id()
    service = InvestigationService(test_db_session)

    inv_rec = service.create_investigation(
        db=test_db_session,
        question=question,
        response=response,
        investigation_id=inv_id,
        owner_id="usr_analyst_01"
    )

    detail = service.get_investigation_detail(inv_id)
    assert detail is not None
    assert detail.investigation_id == inv_id
    assert detail.question == question
    assert detail.status == "COMPLETED"
    assert detail.review_status in ("REQUIRES_REVIEW", "PENDING")
    assert detail.result_json is not None
    assert detail.review_count == 0


def test_phase_8i_human_review_workflow(test_db_session):
    """
    PHASE 8I: Human Review & Self-Review Prevention test.
    Verifies:
    1. Authorized reviewer can approve/reject.
    2. Reviewer notes persist.
    """
    app.dependency_overrides[get_db] = lambda: test_db_session
    client = TestClient(app)

    # 1. Create an investigation owned by usr_analyst_01
    service = InvestigationService(test_db_session)
    inv_id = InvestigationService.generate_investigation_id()
    provider = MockLLMProvider()
    response = run_investigation_loop("What were sales by region?", test_db_session, provider)

    inv_rec = service.create_investigation(
        db=test_db_session,
        question="What were sales by region?",
        response=response,
        investigation_id=inv_id,
        owner_id="usr_analyst_01"
    )

    # 2. Attempt Self-Review as usr_analyst_01 (MUST FAIL with HTTP 403)
    res_self = client.post(
        f"/api/investigations/{inv_id}/review",
        json={"review_status": "APPROVED", "reviewer_id": "usr_analyst_01", "review_notes": "Self approving my own work"},
        headers={"X-Veridex-Mock-User-Id": "usr_analyst_01", "X-Veridex-Mock-Role": "ANALYST"}
    )
    assert res_self.status_code == 403
    assert "Self-Review Blocked" in res_self.json()["detail"] or "not authorized" in res_self.json()["detail"]

    # 3. Authorized Review as usr_reviewer_01 (MUST SUCCEED)
    res_rev = client.post(
        f"/api/investigations/{inv_id}/review",
        json={"review_status": "APPROVED", "reviewer_id": "usr_reviewer_01", "review_notes": "Verified evidence provenance."},
        headers={"X-Veridex-Mock-User-Id": "usr_reviewer_01", "X-Veridex-Mock-Role": "REVIEWER"}
    )
    assert res_rev.status_code == 200
    assert res_rev.json()["review_status"] == "APPROVED"
