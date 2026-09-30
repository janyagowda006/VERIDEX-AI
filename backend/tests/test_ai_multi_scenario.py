import unittest.mock as mock
from app.ai.orchestrator import run_investigation_loop, _evaluate_orchestrated_robustness, DEFAULT_SCENARIO_SHIFT_PCT
from app.ai.provider import MockLLMProvider, ModelResponse, ToolCallRequest
from app.ai.prompts import format_deterministic_reasoning_context
from app.services.robustness import RobustnessEngine, ROBUSTNESS_STATUS_STABLE, ROBUSTNESS_STATUS_SENSITIVE, ROBUSTNESS_STATUS_INSUFFICIENT_EVIDENCE
from app.services.decision_engine import DecisionEngine
from app.schemas.ai import AskResponse
from app.schemas.decision import DecisionAnalysis, Recommendation, RobustnessCheck, RobustnessScenario


def test_numeric_decision_data_produces_deterministic_10_percent_scenarios():
    """
    Verifies that _evaluate_orchestrated_robustness generates -10% and +10% scenarios
    for numeric query data without error.
    """
    engine = RobustnessEngine()
    query_data = [
        {"region": "North America", "gross_revenue": 10000.0},
        {"region": "Europe", "gross_revenue": 5000.0}
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


def test_baseline_data_is_not_mutated_during_scenario_generation():
    """
    Verifies that original query_data objects and row dictionaries are not mutated
    when constructing scenario stress test datasets.
    """
    engine = RobustnessEngine()
    original_row1 = {"product_name": "Widget A", "total_sales": 500.0}
    original_row2 = {"product_name": "Widget B", "total_sales": 300.0}
    query_data = [original_row1, original_row2]

    check = _evaluate_orchestrated_robustness(
        robustness_engine=engine,
        evidence_items=[],
        query_data=query_data
    )

    # Confirm original dictionaries remain completely untouched
    assert original_row1["total_sales"] == 500.0
    assert original_row2["total_sales"] == 300.0
    assert query_data[0]["total_sales"] == 500.0


def test_scenario_changing_top_candidate_detected_as_sensitive():
    """
    Verifies that when a scenario adjustment changes candidate ordering or ranking,
    the resulting RobustnessCheck status is marked SENSITIVE.
    """
    engine = RobustnessEngine()

    # Narrow gap baseline where a shift easily changes top candidate
    baseline_data = [
        {"candidate": "Option A", "score": 100.0},
        {"candidate": "Option B", "score": 98.0}
    ]

    # Scenario where Option B gains +5% and Option A loses -5%
    scenarios = [
        {
            "scenario_name": "reverse_ranking_scenario",
            "data": [
                {"candidate": "Option A", "score": 95.0},
                {"candidate": "Option B", "score": 102.9}
            ]
        }
    ]

    check = engine.evaluate_multi_scenario_robustness(
        baseline_data=baseline_data,
        scenarios=scenarios,
        key_col="candidate",
        metric_col="score"
    )

    assert check.status == ROBUSTNESS_STATUS_SENSITIVE
    assert check.alternate_scenarios[0].is_recommendation_changed is True


def test_scenario_preserving_top_candidate_remains_stable():
    """
    Verifies that when alternate scenarios preserve top candidate ranking and remain within threshold,
    RobustnessCheck status is STABLE.
    """
    engine = RobustnessEngine()
    baseline_data = [
        {"region": "North America", "revenue": 10000.0},
        {"region": "Europe", "revenue": 2000.0}
    ]

    scenarios = [
        {
            "scenario_name": "revenue_minus_2_percent",
            "data": [
                {"region": "North America", "revenue": 9800.0},
                {"region": "Europe", "revenue": 1960.0}
            ]
        }
    ]

    check = engine.evaluate_multi_scenario_robustness(
        baseline_data=baseline_data,
        scenarios=scenarios,
        key_col="region",
        metric_col="revenue",
        threshold_pct=5.0
    )

    assert check.status == ROBUSTNESS_STATUS_STABLE
    assert check.alternate_scenarios[0].is_recommendation_changed is False


def test_non_numeric_query_structure_falls_back_safely():
    """
    Verifies that non-numeric or empty query datasets fall back cleanly
    to standard run_robustness_assessment without errors or exceptions.
    """
    engine = RobustnessEngine()
    non_numeric_data = [
        {"category": "Electronics", "status": "Active"},
        {"category": "Apparel", "status": "Active"}
    ]

    check = _evaluate_orchestrated_robustness(
        robustness_engine=engine,
        evidence_items=[],
        query_data=non_numeric_data
    )

    assert isinstance(check, RobustnessCheck)
    assert check.status in [ROBUSTNESS_STATUS_STABLE, ROBUSTNESS_STATUS_INSUFFICIENT_EVIDENCE]


def test_deterministic_reasoning_context_formatting():
    """
    Verifies format_deterministic_reasoning_context outputs structured text
    containing action titles, rationale, and robustness instructions.
    """
    rec = Recommendation(
        recommendation_id="rec_1",
        action_title="Prioritize Region 'North America'",
        rationale="Top revenue performer",
        supporting_evidence_ids=["ev_fact_1"],
        robustness_status="STABLE"
    )

    rob_sc = RobustnessScenario(
        scenario_name="gross_revenue_minus_10_percent",
        assumptions={"metric": "gross_revenue"},
        result_summary={},
        is_recommendation_changed=False
    )
    rob = RobustnessCheck(
        check_id="rob_1",
        status="STABLE",
        baseline_scenario=rob_sc,
        alternate_scenarios=[rob_sc],
        explanation="Baseline finding holds under multi-scenario metric shift."
    )

    anal = DecisionAnalysis(
        analysis_id="anal_1",
        summary="Analysis complete.",
        recommendation=rec,
        robustness=rob
    )

    formatted = format_deterministic_reasoning_context(anal)
    assert "DETERMINISTIC DECISION & ROBUSTNESS ANALYSIS" in formatted
    assert "Prioritize Region 'North America'" in formatted
    assert "Deterministic Robustness Status: STABLE" in formatted
    assert "STRICT INSTRUCTION" in formatted


def test_orchestration_loop_injects_robustness_context(test_db_session):
    """
    Verifies end-to-end orchestration loop runs multi-scenario robustness assessment
    and populates AskResponse.analysis and metadata correctly.
    """
    provider = MockLLMProvider()
    response = run_investigation_loop(
        question="What is our gross revenue by region?",
        db=test_db_session,
        provider=provider,
        max_turns=3
    )

    assert response.success is True
    assert response.analysis is not None
    assert response.analysis.robustness is not None
    assert response.analysis.robustness.status in ["STABLE", "SENSITIVE"]
    assert response.metadata["robustness_status"] == response.analysis.robustness.status
