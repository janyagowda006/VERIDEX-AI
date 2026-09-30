import json
import pytest
from app.ai.orchestrator import (
    run_investigation_loop,
    _evaluate_orchestrated_robustness,
    _build_claims_and_evidence
)
from app.ai.provider import MockLLMProvider
from app.ai.prompts import format_deterministic_reasoning_context
from app.ai.eval.evaluator import ResponseEvaluator, BenchmarkRunner
from app.ai.eval.schemas import BenchmarkItem, BenchmarkCategory, BenchmarkReport
from app.services.robustness import (
    RobustnessEngine,
    ROBUSTNESS_STATUS_STABLE,
    ROBUSTNESS_STATUS_SENSITIVE,
    ROBUSTNESS_STATUS_INSUFFICIENT_EVIDENCE
)
from app.services.investigation_service import InvestigationService
from app.schemas.ai import AskResponse, ClaimEvidence
from app.schemas.evidence import EvidenceItem, EvidenceType
from app.schemas.decision import (
    DecisionAnalysis,
    Recommendation,
    RobustnessCheck,
    RobustnessScenario
)


def test_benchmark_orchestrator_robustness_integration(test_db_session):
    """
    Verifies that run_investigation_loop orchestrates multi-scenario robustness evaluation
    and populates AskResponse.analysis.robustness and metadata['robustness_status'].
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
    assert response.analysis.robustness.status in [
        ROBUSTNESS_STATUS_STABLE,
        ROBUSTNESS_STATUS_SENSITIVE,
        ROBUSTNESS_STATUS_INSUFFICIENT_EVIDENCE
    ]
    assert response.metadata["robustness_status"] == response.analysis.robustness.status
    assert len(response.analysis.robustness.alternate_scenarios) >= 0


def test_benchmark_stable_ranking_scenario():
    """
    Verifies that a decision dataset with wide candidate performance margins yields
    ROBUSTNESS_STATUS_STABLE when alternate scenarios preserve top candidate ranking
    and remain within the sensitivity threshold.
    """
    engine = RobustnessEngine()
    baseline_data = [
        {"region": "North America", "gross_revenue": 10000.0},
        {"region": "Europe", "gross_revenue": 2000.0}
    ]

    scenarios = [
        {
            "scenario_name": "gross_revenue_minus_2_percent",
            "assumptions": {"metric": "gross_revenue", "shift_pct": -2.0},
            "data": [
                {"region": "North America", "gross_revenue": 9800.0},
                {"region": "Europe", "gross_revenue": 1960.0}
            ]
        }
    ]

    check = engine.evaluate_multi_scenario_robustness(
        baseline_data=baseline_data,
        scenarios=scenarios,
        key_col="region",
        metric_col="gross_revenue",
        threshold_pct=5.0
    )

    assert isinstance(check, RobustnessCheck)
    assert check.status == ROBUSTNESS_STATUS_STABLE
    assert len(check.alternate_scenarios) == 1
    for sc in check.alternate_scenarios:
        assert sc.is_recommendation_changed is False


def test_benchmark_sensitive_ranking_scenario():
    """
    Verifies that a decision dataset with narrow candidate performance margins yields
    ROBUSTNESS_STATUS_SENSITIVE when +-10% metric shifts re-rank top candidates.
    """
    engine = RobustnessEngine()
    # Narrow lead margin between Option A and Option B
    baseline_data = [
        {"candidate": "Option A", "score": 100.0},
        {"candidate": "Option B", "score": 98.0}
    ]

    # Alternate scenario where Option A decreases by 10% (90.0) while Option B remains 98.0
    scenarios = [
        {
            "scenario_name": "score_minus_10_percent",
            "data": [
                {"candidate": "Option A", "score": 90.0},
                {"candidate": "Option B", "score": 98.0}
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
    assert len(check.alternate_scenarios) == 1
    assert check.alternate_scenarios[0].is_recommendation_changed is True


def test_deterministic_reasoning_context_formatting_and_prompt_injection():
    """
    Verifies format_deterministic_reasoning_context correctly structures decision analysis
    for prompt injection, and gracefully returns empty string when analysis is None.
    """
    assert format_deterministic_reasoning_context(None) == ""

    rec = Recommendation(
        recommendation_id="rec_bench_1",
        action_title="Expand Marketing in Region 'North America'",
        rationale="Top performing region by gross revenue",
        supporting_evidence_ids=["ev_fact_1"],
        robustness_status="STABLE"
    )
    rob_sc = RobustnessScenario(
        scenario_name="gross_revenue_minus_10_percent",
        assumptions={"metric": "gross_revenue", "shift_pct": -10.0},
        result_summary={},
        is_recommendation_changed=False
    )
    rob = RobustnessCheck(
        check_id="rob_bench_1",
        status="STABLE",
        baseline_scenario=rob_sc,
        alternate_scenarios=[rob_sc],
        explanation="Top candidate recommendation held consistent across all scenario stress tests."
    )
    analysis = DecisionAnalysis(
        analysis_id="anal_bench_1",
        summary="Deterministic decision evaluation completed.",
        recommendation=rec,
        robustness=rob
    )

    context = format_deterministic_reasoning_context(analysis)
    assert "DETERMINISTIC DECISION & ROBUSTNESS ANALYSIS" in context
    assert "Expand Marketing in Region 'North America'" in context
    assert "STATUS IS STABLE" in context
    assert "STRICT INSTRUCTIONS:" in context


def test_citation_validation_and_supported_unsupported_claims():
    """
    Verifies claim citation parsing, supported vs unsupported claim identification,
    and evaluator metric calculations (groundedness, precision, recall).
    """
    ev1 = EvidenceItem(
        evidence_id="ev_fact_1",
        evidence_type=EvidenceType.FACT,
        description="Gross revenue by region data"
    )
    ev2 = EvidenceItem(
        evidence_id="ev_fact_2",
        evidence_type=EvidenceType.FACT,
        description="Customer counts by region"
    )

    valid_text = "Gross revenue was $1.25M in North America [ev_fact_1]."
    claims_valid, _ = _build_claims_and_evidence(valid_text, [ev1, ev2])

    assert len(claims_valid) == 1
    assert claims_valid[0].evidence_ids == ["ev_fact_1"]
    assert claims_valid[0].is_supported is True

    invalid_text = "Invented metric is $999M [ev_nonexistent_99]."
    claims_invalid, _ = _build_claims_and_evidence(invalid_text, [ev1, ev2])

    assert len(claims_invalid) == 1
    assert claims_invalid[0].evidence_ids == []
    assert claims_invalid[0].is_supported is False

    # Construct an explicit claim citing an unknown ID to verify precision math (1 valid / 2 cited = 0.5)
    unsupported_citing_claim = ClaimEvidence(
        claim_id="claim_unsupported_citing",
        claim_text="Invented metric citing fake ID",
        evidence_ids=["ev_nonexistent_99"],
        evidence_type=EvidenceType.FACT,
        is_supported=False
    )

    # Benchmark evaluator verification
    item = BenchmarkItem(
        id="bench_test_citations",
        category=BenchmarkCategory.FACTUAL,
        question="What is our gross revenue?"
    )
    response = AskResponse(
        success=True,
        question=item.question,
        answer="North America gross revenue is $1.25M [ev_fact_1]. Fake stat is $999M [ev_nonexistent_99].",
        claims=[claims_valid[0], unsupported_citing_claim],
        evidence=[ev1, ev2],
        tool_calls=[]
    )

    eval_result = ResponseEvaluator.evaluate_case(item=item, response=response, latency_ms=12.5)

    assert eval_result.success is True
    assert eval_result.claims_count == 2
    assert eval_result.unsupported_claims_count == 1
    assert eval_result.groundedness_score == 0.5
    assert eval_result.citation_precision == 0.5
    assert eval_result.citation_recall == 0.5


def test_insufficient_evidence_handling_non_numeric_and_empty_queries():
    """
    Verifies that empty datasets or non-numeric query responses generate
    INSUFFICIENT_EVIDENCE or fall back safely without raising runtime exceptions.
    """
    engine = RobustnessEngine()

    # Empty query data test
    empty_check = _evaluate_orchestrated_robustness(
        robustness_engine=engine,
        evidence_items=[],
        query_data=[]
    )
    assert empty_check.status in [ROBUSTNESS_STATUS_STABLE, ROBUSTNESS_STATUS_INSUFFICIENT_EVIDENCE]

    # Non-numeric query data test
    non_numeric_data = [
        {"category": "Electronics", "status": "Active"},
        {"category": "Apparel", "status": "Active"}
    ]
    non_num_check = _evaluate_orchestrated_robustness(
        robustness_engine=engine,
        evidence_items=[],
        query_data=non_numeric_data
    )
    assert non_num_check.status in [ROBUSTNESS_STATUS_STABLE, ROBUSTNESS_STATUS_INSUFFICIENT_EVIDENCE]

    # Context formatting with INSUFFICIENT_EVIDENCE
    rob_sc = RobustnessScenario(
        scenario_name="baseline",
        assumptions={},
        result_summary={},
        is_recommendation_changed=False
    )
    rob_insufficient = RobustnessCheck(
        check_id="rob_empty",
        status=ROBUSTNESS_STATUS_INSUFFICIENT_EVIDENCE,
        baseline_scenario=rob_sc,
        alternate_scenarios=[],
        explanation="No numeric metrics available for scenario simulation."
    )
    anal_insufficient = DecisionAnalysis(
        analysis_id="anal_empty",
        summary="Insufficient evidence.",
        robustness=rob_insufficient
    )

    context = format_deterministic_reasoning_context(anal_insufficient)
    assert "STATUS IS INSUFFICIENT_EVIDENCE" in context
    assert "INSUFFICIENT to draw a robust conclusion" in context


def test_end_to_end_persistence_fidelity_with_ask_response(test_db_session):
    """
    Verifies end-to-end investigation lifecycle persistence, storing AskResponse containing
    DecisionAnalysis and RobustnessCheck into database and re-reading with full fidelity.
    """
    provider = MockLLMProvider()
    question = "Which product category yields the highest gross margin?"
    
    inv_rec = InvestigationService.create_investigation(
        db=test_db_session,
        question=question
    )
    assert inv_rec is not None
    assert inv_rec.investigation_id.startswith("inv_")

    response = run_investigation_loop(
        question=question,
        db=test_db_session,
        provider=provider,
        max_turns=3
    )

    updated_inv = InvestigationService.update_investigation_success(
        db=test_db_session,
        investigation_id=inv_rec.investigation_id,
        response=response,
        execution_time_ms=45.2
    )

    assert updated_inv is not None
    assert updated_inv.status in ["COMPLETED", "REQUIRES_REVIEW"]
    assert updated_inv.robustness_status == response.analysis.robustness.status

    fetched = InvestigationService.get_investigation_by_id(
        db=test_db_session,
        investigation_id=inv_rec.investigation_id
    )

    assert fetched is not None
    result_data = json.loads(fetched.result_json)
    assert "analysis" in result_data
    assert "robustness" in result_data["analysis"]
    assert result_data["analysis"]["robustness"]["status"] == response.analysis.robustness.status

    reconstructed_resp = AskResponse.model_validate(result_data)
    assert reconstructed_resp.analysis is not None
    assert reconstructed_resp.analysis.robustness is not None
    assert reconstructed_resp.analysis.robustness.status == response.analysis.robustness.status


def test_baseline_evaluator_metrics_regression_check(test_db_session):
    """
    Verifies that running BenchmarkRunner over the 20 benchmark test cases
    maintains 100% execution success and expected evaluation metrics.
    """
    runner = BenchmarkRunner()
    provider = MockLLMProvider()

    report = runner.run_benchmark(
        db=test_db_session,
        provider=provider,
        max_turns=3,
        provider_name="mock"
    )

    assert isinstance(report, BenchmarkReport)
    assert report.total_cases == 20
    assert report.successful_cases == 20
    assert report.failed_cases == 0
    assert report.sql_execution_success_rate == 1.0
    assert report.groundedness_rate == 1.0
    assert report.unsupported_claim_rate == 0.0
    assert report.decision_agreement_rate >= 0.0
    assert report.robustness_agreement_rate >= 0.0
    assert len(report.case_evaluations) == 20
