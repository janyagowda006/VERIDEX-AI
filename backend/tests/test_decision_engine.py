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
