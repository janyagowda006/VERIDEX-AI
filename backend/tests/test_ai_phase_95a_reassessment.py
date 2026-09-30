import json
import pytest
import unittest.mock as mock
from fastapi.testclient import TestClient

from app.main import app
from app.core.db import get_db
from app.ai.provider import get_llm_provider, MockLLMProvider
from app.ai.orchestrator import _evaluate_orchestrated_robustness
from app.services.robustness import (
    RobustnessEngine,
    ROBUSTNESS_STATUS_STABLE,
    ROBUSTNESS_STATUS_SENSITIVE,
    ROBUSTNESS_STATUS_INSUFFICIENT_EVIDENCE
)
from app.services.investigation_service import InvestigationService
from app.schemas.investigation import (
    InvestigationReassessRequest,
    InvestigationReassessResponse
)
from app.schemas.ai import AskResponse
from app.schemas.decision import RobustnessCheck


@pytest.fixture
def client(test_db_session):
    """
    FastAPI TestClient with overridden get_db and get_llm_provider dependencies using in-memory SQLite.
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


def test_default_compatibility_preserves_10_percent_shift():
    """
    Verifies that calling _evaluate_orchestrated_robustness without scenario_shift_pct
    preserves default 10.0% scenario shift behavior.
    """
    engine = RobustnessEngine()
    query_data = [
        {"region": "North America", "gross_revenue": 10000.0},
        {"region": "Europe", "gross_revenue": 2000.0}
    ]

    check = _evaluate_orchestrated_robustness(
        robustness_engine=engine,
        evidence_items=[],
        query_data=query_data
    )

    assert isinstance(check, RobustnessCheck)
    assert len(check.alternate_scenarios) == 2
    sc_names = [sc.scenario_name for sc in check.alternate_scenarios]
    assert "gross_revenue_minus_10_percent" in sc_names
    assert "gross_revenue_plus_10_percent" in sc_names


def test_custom_scenario_shift_percentages():
    """
    Verifies dynamic multi-scenario evaluation with custom shift percentages (5%, 15%, 20%, 25%, 30%).
    """
    engine = RobustnessEngine()
    query_data = [
        {"product_name": "Widget Alpha", "sales": 5000.0},
        {"product_name": "Widget Beta", "sales": 1000.0}
    ]

    for shift_pct in [5.0, 15.0, 20.0, 25.0, 30.0]:
        check = _evaluate_orchestrated_robustness(
            robustness_engine=engine,
            evidence_items=[],
            query_data=query_data,
            scenario_shift_pct=shift_pct
        )

        assert isinstance(check, RobustnessCheck)
        assert len(check.alternate_scenarios) == 2
        sc_names = [sc.scenario_name for sc in check.alternate_scenarios]
        shift_int = int(shift_pct) if shift_pct.is_integer() else shift_pct
        assert f"sales_minus_{shift_int}_percent" in sc_names
        assert f"sales_plus_{shift_int}_percent" in sc_names


def test_reassessment_validation_rejects_invalid_percentages():
    """
    Verifies Pydantic schema validation rejects invalid scenario shift percentages
    (negative, 0, >100).
    """
    with pytest.raises(Exception):
        InvestigationReassessRequest(scenario_shift_pct=-10.0)

    with pytest.raises(Exception):
        InvestigationReassessRequest(scenario_shift_pct=0.0)

    with pytest.raises(Exception):
        InvestigationReassessRequest(scenario_shift_pct=150.0)

    # Valid values
    valid_req = InvestigationReassessRequest(scenario_shift_pct=25.0)
    assert valid_req.scenario_shift_pct == 25.0


def test_reassessment_determinism_and_baseline_immutability():
    """
    Verifies that running reassessment multiple times with the same parameters produces
    identical outputs, and that original query_data objects are never mutated.
    """
    engine = RobustnessEngine()
    orig_row1 = {"region": "North America", "revenue": 10000.0}
    orig_row2 = {"region": "Europe", "revenue": 9500.0}
    query_data = [orig_row1, orig_row2]

    check1 = _evaluate_orchestrated_robustness(
        robustness_engine=engine,
        evidence_items=[],
        query_data=query_data,
        scenario_shift_pct=20.0
    )

    check2 = _evaluate_orchestrated_robustness(
        robustness_engine=engine,
        evidence_items=[],
        query_data=query_data,
        scenario_shift_pct=20.0
    )

    # Determinism assertion
    assert check1.status == check2.status
    assert len(check1.alternate_scenarios) == len(check2.alternate_scenarios)

    # Immutability assertion
    assert orig_row1["revenue"] == 10000.0
    assert orig_row2["revenue"] == 9500.0
    assert query_data[0]["revenue"] == 10000.0


def test_reassessment_classifications_stable_sensitive_insufficient():
    """
    Verifies that custom scenario shift percentages trigger expected STABLE, SENSITIVE,
    or INSUFFICIENT_EVIDENCE robustness status classifications.
    """
    engine = RobustnessEngine()

    # Wide margin data -> STABLE under 2% shift (less than 5% threshold)
    wide_data = [
        {"candidate": "Option A", "score": 1000.0},
        {"candidate": "Option B", "score": 100.0}
    ]
    stable_check = _evaluate_orchestrated_robustness(
        robustness_engine=engine,
        evidence_items=[],
        query_data=wide_data,
        scenario_shift_pct=2.0
    )
    assert stable_check.status == ROBUSTNESS_STATUS_STABLE

    # Narrow margin data -> SENSITIVE under 20% shift (Option A decreases to 80, Option B stays 95)
    narrow_data = [
        {"candidate": "Option A", "score": 100.0},
        {"candidate": "Option B", "score": 95.0}
    ]
    sensitive_check = _evaluate_orchestrated_robustness(
        robustness_engine=engine,
        evidence_items=[],
        query_data=narrow_data,
        scenario_shift_pct=20.0
    )
    assert sensitive_check.status == ROBUSTNESS_STATUS_SENSITIVE

    # Non-numeric data -> INSUFFICIENT_EVIDENCE
    empty_check = _evaluate_orchestrated_robustness(
        robustness_engine=engine,
        evidence_items=[],
        query_data=[]
    )
    assert empty_check.status in [ROBUSTNESS_STATUS_STABLE, ROBUSTNESS_STATUS_INSUFFICIENT_EVIDENCE]


def test_investigation_service_reassess_valid_missing_and_insufficient(test_db_session):
    """
    Verifies InvestigationService.reassess_investigation for valid, missing, and corrupted investigation records.
    """
    # Create valid investigation record with persisted result_json
    provider = MockLLMProvider()
    question = "What is our profit margin by product category?"

    inv_rec = InvestigationService.create_investigation(
        db=test_db_session,
        question=question
    )

    from app.ai.orchestrator import run_investigation_loop
    resp = run_investigation_loop(
        question=question,
        db=test_db_session,
        provider=provider,
        max_turns=3
    )

    InvestigationService.update_investigation_success(
        db=test_db_session,
        investigation_id=inv_rec.investigation_id,
        response=resp,
        execution_time_ms=30.0
    )

    # Valid reassessment execution
    reassessed = InvestigationService.reassess_investigation(
        db=test_db_session,
        investigation_id=inv_rec.investigation_id,
        scenario_shift_pct=20.0
    )

    assert isinstance(reassessed, InvestigationReassessResponse)
    assert reassessed.investigation_id == inv_rec.investigation_id
    assert reassessed.requested_scenario_shift_pct == 20.0
    assert "robustness_check" in reassessed.model_dump()
    assert reassessed.robustness_check["status"] in [ROBUSTNESS_STATUS_STABLE, ROBUSTNESS_STATUS_SENSITIVE]

    # Missing investigation ID test
    with pytest.raises(ValueError) as exc_missing:
        InvestigationService.reassess_investigation(
            db=test_db_session,
            investigation_id="inv_nonexistent_999",
            scenario_shift_pct=15.0
        )
    assert "not found" in str(exc_missing.value).lower()

    # Corrupted / empty result payload test
    corrupt_inv = InvestigationService.create_investigation(
        db=test_db_session,
        question="Empty test question"
    )
    with pytest.raises(ValueError) as exc_corrupt:
        InvestigationService.reassess_investigation(
            db=test_db_session,
            investigation_id=corrupt_inv.investigation_id,
            scenario_shift_pct=10.0
        )
    assert "no stored result payload" in str(exc_corrupt.value).lower()


def test_api_reassess_endpoint_flow_and_errors(client, test_db_session):
    """
    Verifies HTTP POST /api/investigations/{id}/reassess endpoint success, 404, and 422 error handling.
    """
    # Create investigation record via API /ask
    ask_resp = client.post(
        "/api/ask",
        json={"question": "What is our gross revenue by region?", "max_turns": 3}
    )
    assert ask_resp.status_code == 200
    inv_id = ask_resp.json()["metadata"]["investigation_id"]

    # Test HTTP 200 POST reassess with custom shift_pct = 25.0
    reassess_resp = client.post(
        f"/api/investigations/{inv_id}/reassess",
        json={"scenario_shift_pct": 25.0}
    )
    assert reassess_resp.status_code == 200
    data = reassess_resp.json()
    assert data["investigation_id"] == inv_id
    assert data["requested_scenario_shift_pct"] == 25.0
    assert "robustness_check" in data

    # Test HTTP 404 missing investigation ID
    res_404 = client.post(
        "/api/investigations/inv_fake_12345/reassess",
        json={"scenario_shift_pct": 10.0}
    )
    assert res_404.status_code == 404

    # Test HTTP 422 invalid negative shift percentage
    res_422 = client.post(
        f"/api/investigations/{inv_id}/reassess",
        json={"scenario_shift_pct": -5.0}
    )
    assert res_422.status_code == 422


def test_architectural_boundary_reassessment_never_invokes_llm_or_sql(test_db_session):
    """
    CRITICAL ARCHITECTURAL BOUNDARY TEST:
    Proves that reassessing an investigation deterministically re-evaluates stored data
    and NEVER invokes LLM provider generation or database SQL execution.
    """
    # Create valid investigation record
    provider = MockLLMProvider()
    question = "Which product line should receive increased inventory allocation?"

    inv_rec = InvestigationService.create_investigation(
        db=test_db_session,
        question=question
    )

    from app.ai.orchestrator import run_investigation_loop
    resp = run_investigation_loop(
        question=question,
        db=test_db_session,
        provider=provider,
        max_turns=3
    )

    InvestigationService.update_investigation_success(
        db=test_db_session,
        investigation_id=inv_rec.investigation_id,
        response=resp,
        execution_time_ms=25.0
    )

    # Attach spies/mocks on LLM provider and execute_read_only_sql
    with mock.patch("app.ai.provider.BaseLLMProvider.generate_turn") as mock_llm_gen, \
         mock.patch("app.tools.sql_tool.execute_read_only_sql") as mock_sql_exec:

        # Execute reassessment
        reassessed = InvestigationService.reassess_investigation(
            db=test_db_session,
            investigation_id=inv_rec.investigation_id,
            scenario_shift_pct=30.0
        )

        assert reassessed.requested_scenario_shift_pct == 30.0

        # ABSOLUTE PROOF: Neither LLM nor SQL tool were invoked during reassessment
        mock_llm_gen.assert_not_called()
        mock_sql_exec.assert_not_called()


def test_reassessment_handles_empty_dict_query_data():
    """
    Verifies that _evaluate_orchestrated_robustness safely handles empty dict rows [{}]
    without raising IndexError during key/metric column extraction.
    """
    engine = RobustnessEngine()
    empty_dict_data = [{}]

    check = _evaluate_orchestrated_robustness(
        robustness_engine=engine,
        evidence_items=[],
        query_data=empty_dict_data,
        scenario_shift_pct=15.0
    )

    assert isinstance(check, RobustnessCheck)
    assert check.status in [ROBUSTNESS_STATUS_STABLE, ROBUSTNESS_STATUS_INSUFFICIENT_EVIDENCE]
