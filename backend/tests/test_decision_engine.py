import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.db import get_db
from app.schemas.evidence import EvidenceItem, EvidenceType
from app.schemas.decision import DecisionCriterion, Recommendation, RobustnessCheck, DecisionAnalysis
from app.services.decision_engine import DecisionEngine
from app.services.robustness import RobustnessEngine
from app.ai.orchestrator import run_investigation_loop
from app.ai.provider import MockLLMProvider, get_llm_provider

client = TestClient(app)


def test_decision_criterion_evaluation_greater_than():
    engine = DecisionEngine()
    crit = engine.evaluate_criterion("Min Sales", "gross_revenue", ">=", 1000.0, 1500.0)

    assert crit.is_met is True
    assert crit.operator == ">="
    assert crit.actual_value == 1500.0
    assert "satisfied" in crit.explanation.lower()


def test_decision_criterion_evaluation_equal():
    engine = DecisionEngine()
    crit = engine.evaluate_criterion("Exact Target", "order_count", "==", 10, 10)

    assert crit.is_met is True
    assert crit.operator == "=="


def test_decision_criterion_evaluation_unmet():
    engine = DecisionEngine()
    crit = engine.evaluate_criterion("High Growth Target", "growth_rate", ">=", 50.0, 12.5)

    assert crit.is_met is False
    assert "not satisfied" in crit.explanation.lower()


def test_candidate_ranking_sorting():
    engine = DecisionEngine()
    data = [
        {"region": "South", "revenue": 800.0},
        {"region": "North", "revenue": 1200.0},
        {"region": "East", "revenue": 950.0}
    ]
    rankings = engine.rank_candidates(data, key_col="region", metric_col="revenue", top_n=5)

    assert len(rankings) == 3
    assert rankings[0]["region"] == "North"
    assert rankings[0]["rank"] == 1
    assert rankings[1]["region"] == "East"
    assert rankings[2]["region"] == "South"


def test_candidate_ranking_top_n_truncation():
    engine = DecisionEngine()
    data = [{"item": f"Product {i}", "sales": i * 10} for i in range(1, 10)]
    rankings = engine.rank_candidates(data, key_col="item", metric_col="sales", top_n=3)

    assert len(rankings) == 3
    assert rankings[0]["sales"] == 90
    assert rankings[2]["sales"] == 70


def test_recommendation_creation_with_evidence_linkage():
    engine = DecisionEngine()
    rec = engine.build_recommendation(
        action_title="Expand North Region Inventory",
        rationale="North region generated highest gross revenue.",
        supporting_evidence_ids=["ev_fact_1", "ev_derived_1"],
        robustness_status="STABLE"
    )

    assert rec.action_title == "Expand North Region Inventory"
    assert "ev_fact_1" in rec.supporting_evidence_ids
    assert rec.robustness_status == "STABLE"


def test_decision_analysis_generation():
    engine = DecisionEngine()
    ev_item = EvidenceItem(
        evidence_id="ev_fact_1",
        evidence_type=EvidenceType.FACT,
        description="Fact sales data"
    )
    data = [{"region": "North", "revenue": 1200.0}, {"region": "South", "revenue": 1000.0}]

    analysis = engine.analyze_decision("Gross revenue by region", [ev_item], data)

    assert analysis.analysis_id is not None
    assert len(analysis.rankings) == 2
    assert len(analysis.criteria_evaluated) == 1
    assert analysis.recommendation is not None
    assert analysis.recommendation.robustness_status is not None


def test_robustness_assessment_stable_classification():
    engine = RobustnessEngine()
    data = [{"region": "North", "revenue": 1500.0}, {"region": "South", "revenue": 900.0}]
    ev_item = EvidenceItem(evidence_id="ev_fact_1", evidence_type=EvidenceType.FACT, description="Sales")

    robustness = engine.run_robustness_assessment([ev_item], query_data=data)

    assert robustness.status == "STABLE"
    assert "STABLE" in robustness.explanation


def test_robustness_assessment_sensitive_classification():
    engine = RobustnessEngine()
    data = [{"region": "North", "revenue": 1000.0}, {"region": "South", "revenue": 980.0}]
    ev_item = EvidenceItem(evidence_id="ev_fact_1", evidence_type=EvidenceType.FACT, description="Sales")

    robustness = engine.run_robustness_assessment([ev_item], query_data=data)

    assert robustness.status == "SENSITIVE"
    assert "SENSITIVE" in robustness.explanation


def test_robustness_assessment_insufficient_evidence_classification():
    engine = RobustnessEngine()
    robustness = engine.run_robustness_assessment([], query_data=[])

    assert robustness.status == "INSUFFICIENT_EVIDENCE"
    assert "insufficient" in robustness.explanation.lower()


def test_robustness_assessment_explicit_alternate_scenario():
    engine = RobustnessEngine()
    baseline_data = [{"region": "North", "revenue": 1000.0}]
    alternate_data = [{"region": "South", "revenue": 1200.0}]
    ev_item = EvidenceItem(evidence_id="ev_fact_1", evidence_type=EvidenceType.FACT, description="Sales")

    robustness = engine.run_robustness_assessment(
        [ev_item],
        query_data=baseline_data,
        alternate_data=alternate_data,
        scenario_description="All order statuses"
    )

    assert robustness.status == "SENSITIVE"
    assert len(robustness.alternate_scenarios) == 1
    assert robustness.alternate_scenarios[0].is_recommendation_changed is True


def test_decision_engine_empty_data_handling():
    engine = DecisionEngine()
    analysis = engine.analyze_decision("What is top product?", [], query_data=[])

    assert analysis.recommendation is not None
    assert analysis.recommendation.robustness_status == "INSUFFICIENT_EVIDENCE"
    assert len(analysis.rankings) == 0


def test_decision_engine_missing_metric_value_handling():
    engine = DecisionEngine()
    crit = engine.evaluate_criterion("Missing Metric", "revenue", ">=", 100.0, None)

    assert crit.is_met is False
    assert "missing" in crit.explanation.lower()


def test_orchestrator_integration_returns_decision_analysis(test_db_session):
    provider = MockLLMProvider()
    res = run_investigation_loop(
        question="What is our gross revenue by region?",
        db=test_db_session,
        provider=provider,
        max_turns=3
    )

    assert res.success is True
    assert res.analysis is not None
    assert res.analysis.recommendation is not None
    assert res.analysis.robustness is not None
    assert res.analysis.robustness.status in ["STABLE", "SENSITIVE", "INSUFFICIENT_EVIDENCE"]


def test_ask_endpoint_returns_decision_analysis_payload(test_db_session):
    app.dependency_overrides[get_db] = lambda: test_db_session
    app.dependency_overrides[get_llm_provider] = lambda: MockLLMProvider()

    try:
        response = client.post(
            "/api/ask",
            json={"question": "Show top products by revenue", "max_turns": 3}
        )

        assert response.status_code == 200
        data = response.json()

        assert "analysis" in data
        assert data["analysis"] is not None
        assert "recommendation" in data["analysis"]
        assert "robustness" in data["analysis"]
        assert data["analysis"]["robustness"]["status"] in ["STABLE", "SENSITIVE", "INSUFFICIENT_EVIDENCE"]
    finally:
        app.dependency_overrides.clear()


def test_no_arbitrary_confidence_scores_in_decision_output(test_db_session):
    engine = DecisionEngine()
    analysis = engine.analyze_decision("Test query", [], query_data=[{"val": 10}])

    res_dict = analysis.model_dump()
    assert "confidence_score" not in res_dict
    assert "confidence_percentage" not in res_dict


def test_recommendation_traceable_to_supporting_evidence_ids():
    engine = DecisionEngine()
    rec = engine.build_recommendation(
        action_title="Action Title",
        rationale="Rationale text",
        supporting_evidence_ids=["ev_fact_1", "ev_derived_1"],
        robustness_status="STABLE"
    )
    assert rec.supporting_evidence_ids == ["ev_fact_1", "ev_derived_1"]


def test_decision_criteria_operators():
    engine = DecisionEngine()
    assert engine.evaluate_criterion("c1", "m", "<=", 100, 50).is_met is True
    assert engine.evaluate_criterion("c2", "m", "<", 100, 100).is_met is False
    assert engine.evaluate_criterion("c3", "m", "!=", 10, 20).is_met is True


def test_robustness_scenario_result_summary():
    engine = RobustnessEngine()
    check = engine.run_robustness_assessment(
        [],
        query_data=[{"region": "North", "sales": 100}]
    )
    assert check.baseline_scenario.scenario_name == "baseline_completed_orders"
    assert check.baseline_scenario.result_summary["top_candidate"] == "North"


def test_orchestrator_backward_compatibility_with_analysis_none_handling():
    res = run_investigation_loop(
        question="Health query",
        db=None,
        provider=MockLLMProvider(),
        max_turns=1
    )
    # When DB is None or tool execution fails, AskResponse returns error safely with analysis=None
    assert hasattr(res, "analysis")


# ---------------------------------------------------------
# Phase 7B: Multi-Scenario Robustness & Outlier Sensitivity
# ---------------------------------------------------------

def test_robustness_multi_scenario_baseline():
    engine = RobustnessEngine()
    baseline = [
        {"region": "North", "revenue": 1000.0},
        {"region": "South", "revenue": 800.0}
    ]
    # Revenue shift for North is -2.0% (from 1000 to 980), which stays within 5.0% threshold
    scenarios = [
        {"name": "status_completed", "data": [{"region": "North", "revenue": 980.0}, {"region": "South", "revenue": 780.0}]}
    ]
    ev_item = EvidenceItem(evidence_id="ev_fact_1", evidence_type=EvidenceType.FACT, description="Sales")

    check = engine.evaluate_multi_scenario_robustness(baseline, scenarios, evidence_items=[ev_item])

    assert check.status == "STABLE"
    assert check.baseline_scenario.scenario_name == "baseline_scenario"
    assert check.baseline_scenario.result_summary["top_candidate"] == "North"
    assert check.baseline_scenario.is_recommendation_changed is False
    assert "ev_fact_1" in check.supporting_evidence_ids


def test_robustness_multi_scenario_multiple_scenarios():
    engine = RobustnessEngine()
    baseline = [
        {"region": "North", "revenue": 1000.0},
        {"region": "South", "revenue": 800.0},
        {"region": "East", "revenue": 600.0}
    ]
    scenarios = [
        {"name": "scenario_rev_plus_10", "adjustments": {"revenue": 10.0}},
        {"name": "scenario_rev_minus_10", "adjustments": {"revenue": -10.0}},
        {"name": "scenario_cost_shift", "data": [{"region": "North", "revenue": 1050.0}, {"region": "South", "revenue": 850.0}]}
    ]

    check = engine.evaluate_multi_scenario_robustness(baseline, scenarios)

    assert len(check.alternate_scenarios) == 3
    assert check.alternate_scenarios[0].scenario_name == "scenario_rev_plus_10"
    assert check.alternate_scenarios[1].scenario_name == "scenario_rev_minus_10"
    assert check.alternate_scenarios[2].scenario_name == "scenario_cost_shift"


def test_robustness_multi_scenario_stable_result():
    engine = RobustnessEngine()
    baseline = [
        {"region": "North", "revenue": 2000.0},
        {"region": "South", "revenue": 500.0}
    ]
    # Small revenue shifts (-2% and +3%) keep North top and within threshold (5.0%)
    scenarios = [
        {"name": "scenario_a", "adjustments": {"revenue": -2.0}},
        {"name": "scenario_b", "adjustments": {"revenue": 3.0}}
    ]

    check = engine.evaluate_multi_scenario_robustness(baseline, scenarios, threshold_pct=5.0)

    assert check.status == "STABLE"
    assert all(not s.is_recommendation_changed for s in check.alternate_scenarios)
    assert "remained consistent" in check.explanation


def test_robustness_multi_scenario_sensitive_result():
    engine = RobustnessEngine()
    baseline = [
        {"region": "North", "revenue": 1000.0},
        {"region": "South", "revenue": 950.0}
    ]
    scenarios = [
        {"name": "scenario_north_drop", "adjustments": {"North": -10.0}}
    ]

    check = engine.evaluate_multi_scenario_robustness(baseline, scenarios)

    assert check.status == "SENSITIVE"
    assert check.alternate_scenarios[0].is_recommendation_changed is True
    assert check.alternate_scenarios[0].result_summary["top_candidate"] == "South"
    assert "changed" in check.explanation


def test_robustness_explicit_sensitivity_threshold_behavior():
    engine = RobustnessEngine()
    query_data = [
        {"region": "North", "revenue": 1000.0},
        {"region": "South", "revenue": 920.0}
    ]
    # Gap is ((1000 - 920) / 1000) * 100 = 8.0%
    # Threshold 5%: 8% >= 5% -> STABLE
    check_stable = engine.run_robustness_assessment(
        [],
        query_data=query_data,
        sensitivity_threshold_pct=5.0
    )
    assert check_stable.status == "STABLE"

    # Threshold 10%: 8% < 10% -> SENSITIVE
    check_sensitive = engine.run_robustness_assessment(
        [],
        query_data=query_data,
        sensitivity_threshold_pct=10.0
    )
    assert check_sensitive.status == "SENSITIVE"


def test_outlier_sensitivity_basic_execution():
    engine = RobustnessEngine()
    values = [100.0, 105.0, 95.0, 102.0, 98.0]
    ev_item = EvidenceItem(evidence_id="ev_fact_outlier", evidence_type=EvidenceType.FACT, description="Fact")

    check = engine.evaluate_outlier_sensitivity(values, metric_type="mean", threshold_pct=10.0, evidence_items=[ev_item])

    assert check.check_id is not None
    assert check.status == "STABLE"
    assert check.baseline_scenario.scenario_name == "baseline_all_observations"
    assert len(check.alternate_scenarios) == 5
    assert "ev_fact_outlier" in check.supporting_evidence_ids


def test_outlier_does_not_materially_affect_result():
    engine = RobustnessEngine()
    values = [100.0, 102.0, 99.0, 101.0, 103.0]
    check = engine.evaluate_outlier_sensitivity(values, metric_type="mean", threshold_pct=10.0)

    assert check.status == "STABLE"
    assert all(not s.is_recommendation_changed for s in check.alternate_scenarios)
    assert "no single observation alters" in check.explanation


def test_outlier_materially_affects_result():
    engine = RobustnessEngine()
    # 9 typical values of 100.0 and 1 outlier of 250.0 (baseline mean 115.0)
    # Removing 250 shifts mean to 100 (-13.04%), while removing any 100 shifts mean to 116.67 (+1.45%)
    values = [100.0] * 9 + [250.0]
    labels = [f"order_{i}" for i in range(1, 10)] + ["whale_order"]

    check = engine.evaluate_outlier_sensitivity(values, metric_type="mean", threshold_pct=10.0, labels=labels)

    assert check.status == "SENSITIVE"
    whale_scenario = next(s for s in check.alternate_scenarios if "whale_order" in s.scenario_name)
    assert whale_scenario.is_recommendation_changed is True
    assert whale_scenario.result_summary["is_material_outlier"] is True
    assert "detected 1 influential observation" in check.explanation


def test_outlier_sensitivity_empty_input():
    engine = RobustnessEngine()
    check = engine.evaluate_outlier_sensitivity([])

    assert check.status == "INSUFFICIENT_EVIDENCE"
    assert "empty" in check.explanation.lower()
    assert len(check.alternate_scenarios) == 0


def test_outlier_sensitivity_single_value_input():
    engine = RobustnessEngine()
    check = engine.evaluate_outlier_sensitivity([42.0])

    assert check.status == "INSUFFICIENT_EVIDENCE"
    assert "at least 2 observations" in check.explanation.lower()


def test_outlier_sensitivity_invalid_non_numeric_input():
    engine = RobustnessEngine()
    check = engine.evaluate_outlier_sensitivity([10.0, "corrupted", None, True])

    assert check.status == "INSUFFICIENT_EVIDENCE"
    assert "non-numeric" in check.explanation.lower()


def test_outlier_sensitivity_duplicate_values():
    engine = RobustnessEngine()
    values = [10.0, 10.0, 100.0, 100.0]
    check = engine.evaluate_outlier_sensitivity(values, metric_type="mean", threshold_pct=10.0)

    assert check.status == "SENSITIVE"
    assert len(check.alternate_scenarios) == 4
    outlier_scenarios = [s for s in check.alternate_scenarios if s.assumptions["excluded_value"] == 100.0]
    assert len(outlier_scenarios) == 2
    assert outlier_scenarios[0].result_summary["shift_percent"] == outlier_scenarios[1].result_summary["shift_percent"]


def test_outlier_sensitivity_deterministic_repeated_execution():
    engine = RobustnessEngine()
    values = [20.0, 25.0, 30.0, 150.0]

    check1 = engine.evaluate_outlier_sensitivity(values, threshold_pct=15.0)
    check2 = engine.evaluate_outlier_sensitivity(values, threshold_pct=15.0)

    assert check1.status == check2.status
    assert check1.explanation == check2.explanation
    assert len(check1.alternate_scenarios) == len(check2.alternate_scenarios)
    for s1, s2 in zip(check1.alternate_scenarios, check2.alternate_scenarios):
        assert s1.scenario_name == s2.scenario_name
        assert s1.is_recommendation_changed == s2.is_recommendation_changed
        assert s1.result_summary["shift_percent"] == s2.result_summary["shift_percent"]


def test_robustness_provenance_preservation():
    engine = RobustnessEngine()
    ev1 = EvidenceItem(evidence_id="ev_fact_101", evidence_type=EvidenceType.FACT, description="Fact 1")
    ev2 = EvidenceItem(evidence_id="ev_derived_102", evidence_type=EvidenceType.DERIVED_FACT, description="Derived 2")

    check_multi = engine.evaluate_multi_scenario_robustness(
        baseline_data=[{"region": "North", "sales": 100}],
        scenarios=[{"name": "s1", "adjustments": {"sales": 5}}],
        evidence_items=[ev1, ev2]
    )
    assert "ev_fact_101" in check_multi.supporting_evidence_ids
    assert "ev_derived_102" not in check_multi.supporting_evidence_ids

    check_outlier = engine.evaluate_outlier_sensitivity(
        values=[10, 20, 30],
        evidence_items=[ev1, ev2]
    )
    assert "ev_fact_101" in check_outlier.supporting_evidence_ids
    assert "ev_derived_102" not in check_outlier.supporting_evidence_ids


def test_run_robustness_assessment_multi_scenario_dispatch():
    engine = RobustnessEngine()
    query_data = [
        {"region": "North", "revenue": 1000.0},
        {"region": "South", "revenue": 800.0}
    ]
    # Adjustments of +2% and -2% stay within default 5.0% threshold
    scenarios = [
        {"name": "alt_1", "adjustments": {"revenue": 2.0}},
        {"name": "alt_2", "adjustments": {"revenue": -2.0}}
    ]

    check = engine.run_robustness_assessment(
        evidence_items=[],
        query_data=query_data,
        alternate_scenarios=scenarios
    )
    assert len(check.alternate_scenarios) == 2
    assert check.status == "STABLE"


# ---------------------------------------------------------------------------
# Phase 7B Hardening: Multi-Scenario Threshold, Invalid Inputs, and Outliers
# ---------------------------------------------------------------------------

def test_robustness_multi_scenario_threshold_behavior():
    """
    Demonstrates deterministic threshold sensitivity rule:
    When baseline top candidate stays top in alternate scenario, sensitivity is determined
    strictly by whether the metric shift equals or exceeds threshold_pct.
    """
    engine = RobustnessEngine()
    baseline = [
        {"region": "North", "revenue": 1000.0},
        {"region": "South", "revenue": 800.0}
    ]
    # North drops from 1000 to 920: metric shift is ((920 - 1000) / 1000) * 100 = -8.0%
    # North remains top candidate (920 > 750), but shift magnitude is 8.0%
    scenario_moderate_drop = [
        {"name": "moderate_drop", "data": [{"region": "North", "revenue": 920.0}, {"region": "South", "revenue": 750.0}]}
    ]

    # At threshold_pct=5.0: abs(-8.0%) >= 5.0% -> SENSITIVE
    check_sens = engine.evaluate_multi_scenario_robustness(
        baseline,
        scenario_moderate_drop,
        threshold_pct=5.0
    )
    assert check_sens.status == "SENSITIVE"
    alt_sc = check_sens.alternate_scenarios[0]
    assert alt_sc.is_recommendation_changed is True
    assert alt_sc.result_summary["candidate_changed"] is False
    assert alt_sc.result_summary["metric_exceeded_threshold"] is True
    assert alt_sc.result_summary["metric_shift_percent"] == -8.0
    assert "exceeded threshold" in check_sens.explanation

    # At threshold_pct=10.0: abs(-8.0%) < 10.0% -> STABLE
    check_stable = engine.evaluate_multi_scenario_robustness(
        baseline,
        scenario_moderate_drop,
        threshold_pct=10.0
    )
    assert check_stable.status == "STABLE"
    alt_sc_stable = check_stable.alternate_scenarios[0]
    assert alt_sc_stable.is_recommendation_changed is False
    assert alt_sc_stable.result_summary["candidate_changed"] is False
    assert alt_sc_stable.result_summary["metric_exceeded_threshold"] is False
    assert "remained consistent" in check_stable.explanation


def test_robustness_invalid_threshold_handling():
    """
    Validates that negative, NaN, infinite, or non-numeric thresholds are rejected deterministically
    with status INSUFFICIENT_EVIDENCE across all robustness methods.
    """
    engine = RobustnessEngine()
    baseline = [{"region": "North", "revenue": 1000.0}, {"region": "South", "revenue": 800.0}]
    scenarios = [{"name": "sc1", "data": [{"region": "North", "revenue": 1000.0}]}]
    values = [10.0, 20.0, 30.0]

    for bad_threshold in [-5.0, float('nan'), float('inf'), float('-inf')]:
        # 1. Multi-scenario robustness
        check_multi = engine.evaluate_multi_scenario_robustness(baseline, scenarios, threshold_pct=bad_threshold)
        assert check_multi.status == "INSUFFICIENT_EVIDENCE"
        assert "Invalid threshold_pct" in check_multi.explanation

        # 2. Outlier sensitivity
        check_outlier = engine.evaluate_outlier_sensitivity(values, threshold_pct=bad_threshold)
        assert check_outlier.status == "INSUFFICIENT_EVIDENCE"
        assert "Invalid threshold_pct" in check_outlier.explanation

        # 3. Assessment dispatch
        check_assess = engine.run_robustness_assessment([], query_data=baseline, sensitivity_threshold_pct=bad_threshold)
        assert check_assess.status == "INSUFFICIENT_EVIDENCE"
        assert "Invalid sensitivity_threshold_pct" in check_assess.explanation


def test_robustness_invalid_baseline_metric():
    """
    Ensures that invalid, string, NaN, or infinite metric values in baseline data
    safely produce INSUFFICIENT_EVIDENCE without unhandled exceptions.
    """
    engine = RobustnessEngine()
    scenarios = [{"name": "sc1", "data": [{"region": "North", "revenue": 1000.0}]}]

    for bad_val in ["corrupted", float('nan'), float('inf'), float('-inf')]:
        bad_baseline = [
            {"region": "North", "revenue": bad_val},
            {"region": "South", "revenue": 800.0}
        ]
        check = engine.evaluate_multi_scenario_robustness(bad_baseline, scenarios)
        assert check.status == "INSUFFICIENT_EVIDENCE"
        assert "Invalid non-numeric or non-finite metric value" in check.explanation


def test_robustness_invalid_alternate_scenario_metric():
    """
    Ensures that invalid, string, NaN, or infinite metric values in alternate scenarios
    (data rows, adjustments, or summaries) return INSUFFICIENT_EVIDENCE deterministically.
    """
    engine = RobustnessEngine()
    valid_baseline = [
        {"region": "North", "revenue": 1000.0},
        {"region": "South", "revenue": 800.0}
    ]

    for bad_val in ["corrupted", float('nan'), float('inf'), float('-inf')]:
        # Bad metric in explicit scenario data
        bad_data_scenarios = [
            {"name": "bad_data", "data": [{"region": "North", "revenue": bad_val}]}
        ]
        check_data = engine.evaluate_multi_scenario_robustness(valid_baseline, bad_data_scenarios)
        assert check_data.status == "INSUFFICIENT_EVIDENCE"
        assert "Invalid non-numeric or non-finite metric value" in check_data.explanation

        # Bad adjustment in scenario adjustments dict
        bad_adj_scenarios = [
            {"name": "bad_adj", "adjustments": {"revenue": bad_val}}
        ]
        check_adj = engine.evaluate_multi_scenario_robustness(valid_baseline, bad_adj_scenarios)
        assert check_adj.status == "INSUFFICIENT_EVIDENCE"
        assert "Invalid non-numeric or non-finite adjustment" in check_adj.explanation

        # Bad metric_value in pre-evaluated scenario summary
        bad_summary_scenarios = [
            {"name": "bad_summary", "result_summary": {"top_candidate": "North", "metric_value": bad_val}}
        ]
        check_sum = engine.evaluate_multi_scenario_robustness(valid_baseline, bad_summary_scenarios)
        assert check_sum.status == "INSUFFICIENT_EVIDENCE"
        assert "Invalid non-numeric or non-finite metric_value" in check_sum.explanation


def test_outlier_sensitivity_zero_baseline():
    """
    When baseline metric is zero, percentage change is mathematically undefined.
    evaluate_outlier_sensitivity() must return INSUFFICIENT_EVIDENCE and preserve baseline info.
    """
    engine = RobustnessEngine()

    # Case 1: Mean is exactly zero
    zeros = [0.0, 0.0, 0.0, 0.0]
    check_zeros = engine.evaluate_outlier_sensitivity(zeros, metric_type="mean", threshold_pct=10.0)
    assert check_zeros.status == "INSUFFICIENT_EVIDENCE"
    assert check_zeros.baseline_scenario.result_summary["baseline_metric"] == 0.0
    assert len(check_zeros.alternate_scenarios) == 0
    assert "Baseline metric is zero; percentage-based outlier sensitivity is undefined." in check_zeros.explanation

    # Case 2: Sum is zero from opposing values
    balanced = [-15.0, 15.0, 0.0]
    check_balanced = engine.evaluate_outlier_sensitivity(balanced, metric_type="sum", threshold_pct=10.0)
    assert check_balanced.status == "INSUFFICIENT_EVIDENCE"
    assert check_balanced.baseline_scenario.result_summary["baseline_metric"] == 0.0
    assert len(check_balanced.alternate_scenarios) == 0
    assert "zero" in check_balanced.explanation.lower()


def test_outlier_sensitivity_nan_and_infinity():
    """
    NaN and infinite values are treated as invalid numeric observations and rejected
    with INSUFFICIENT_EVIDENCE.
    """
    engine = RobustnessEngine()

    for bad_num in [float('nan'), float('inf'), float('-inf')]:
        values = [10.0, bad_num, 20.0, 30.0]
        check = engine.evaluate_outlier_sensitivity(values, metric_type="mean")
        assert check.status == "INSUFFICIENT_EVIDENCE"
        assert "non-finite" in check.explanation.lower()
        assert len(check.alternate_scenarios) == 0


def test_robustness_multi_scenario_deterministic_repeated_execution():
    """
    Multi-scenario evaluation must produce byte-for-byte identical outcomes on repeated runs.
    """
    engine = RobustnessEngine()
    baseline = [{"region": "North", "revenue": 1000.0}, {"region": "South", "revenue": 800.0}]
    scenarios = [
        {"name": "sc_down", "adjustments": {"revenue": -8.0}},
        {"name": "sc_up", "adjustments": {"revenue": 4.0}}
    ]

    run1 = engine.evaluate_multi_scenario_robustness(baseline, scenarios, threshold_pct=5.0)
    run2 = engine.evaluate_multi_scenario_robustness(baseline, scenarios, threshold_pct=5.0)

    assert run1.status == run2.status
    assert run1.explanation == run2.explanation
    assert len(run1.alternate_scenarios) == len(run2.alternate_scenarios)
    for s1, s2 in zip(run1.alternate_scenarios, run2.alternate_scenarios):
        assert s1.scenario_name == s2.scenario_name
        assert s1.is_recommendation_changed == s2.is_recommendation_changed
        assert s1.result_summary == s2.result_summary
