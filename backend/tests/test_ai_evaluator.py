import os
import pytest
from app.ai.eval.schemas import (
    BenchmarkItem,
    CaseEvaluation,
    BenchmarkReport,
    BenchmarkCategory
)
from app.ai.eval.evaluator import ResponseEvaluator, BenchmarkRunner
from app.schemas.ai import AskResponse, ClaimEvidence, ToolCallRecord
from app.schemas.evidence import EvidenceItem, EvidenceType
from app.schemas.decision import DecisionAnalysis, RobustnessCheck, Recommendation
from app.schemas.sql_tool import SQLQueryResult
from app.ai.provider import MockLLMProvider


def test_benchmark_dataset_loading():
    """
    Verifies that benchmark_dataset.json loads correctly and parses into 20 valid BenchmarkItem objects.
    """
    runner = BenchmarkRunner()
    assert len(runner.items) == 20
    for item in runner.items:
        assert item.id.startswith("bench_")
        assert isinstance(item.category, BenchmarkCategory)
        assert len(item.question) > 0


def test_response_evaluator_sql_extraction():
    """
    Verifies table name extraction from SQL queries using regex.
    """
    sql = "SELECT c.region, SUM(oi.quantity * p.unit_price) FROM orders o JOIN customers c ON o.customer_id = c.customer_id JOIN order_items oi ON o.order_id = oi.order_id GROUP BY c.region"
    tables = ResponseEvaluator.extract_tables_from_sql(sql)
    assert "customers" in tables
    assert "orders" in tables
    assert "order_items" in tables
    assert "products" not in tables


def test_response_evaluator_groundedness_and_citations():
    """
    Verifies calculation of groundedness_score, citation_precision, citation_recall, and unsupported claims.
    """
    item = BenchmarkItem(
        id="test_01",
        category=BenchmarkCategory.FACTUAL,
        question="Test factual question"
    )

    ev1 = EvidenceItem(
        evidence_id="ev_fact_1",
        evidence_type=EvidenceType.FACT,
        description="Fact item 1"
    )
    ev2 = EvidenceItem(
        evidence_id="ev_derived_1",
        evidence_type=EvidenceType.DERIVED_FACT,
        description="Derived item 1"
    )

    claims = [
        ClaimEvidence(
            claim_id="claim_1",
            claim_text="Claim 1 text",
            evidence_ids=["ev_fact_1"],
            evidence_type=EvidenceType.FACT,
            is_supported=True
        ),
        ClaimEvidence(
            claim_id="claim_2",
            claim_text="Claim 2 text",
            evidence_ids=["ev_unknown_99"],  # Invalid evidence ID
            evidence_type=EvidenceType.FACT,
            is_supported=False
        )
    ]

    response = AskResponse(
        success=True,
        question=item.question,
        answer="Test answer text",
        claims=claims,
        evidence=[ev1, ev2],
        tool_calls=[]
    )

    case_eval = ResponseEvaluator.evaluate_case(item=item, response=response, latency_ms=10.0)

    assert case_eval.success is True
    assert case_eval.claims_count == 2
    assert case_eval.unsupported_claims_count == 1
    assert case_eval.groundedness_score == 0.5  # 1 supported / 2 total
    assert case_eval.citation_precision == 0.5   # 1 valid citation / 2 total cited
    assert case_eval.citation_recall == 0.5      # 1 unique valid cited / 2 available evidence items


def test_response_evaluator_decision_agreement():
    """
    Verifies decision agreement matching against expected robustness status.
    """
    item = BenchmarkItem(
        id="test_decision",
        category=BenchmarkCategory.DECISION,
        question="Which option to choose?",
        expected_decision_status="STABLE"
    )

    robustness = RobustnessCheck(
        check_id="rob_1",
        status="STABLE",
        baseline_scenario={"scenario_name": "baseline"},
        explanation="Stable across scenarios"
    )
    analysis = DecisionAnalysis(
        analysis_id="anal_1",
        summary="Analysis summary",
        robustness=robustness
    )

    response = AskResponse(
        success=True,
        question=item.question,
        answer="Answer text",
        claims=[],
        evidence=[],
        analysis=analysis
    )

    case_eval = ResponseEvaluator.evaluate_case(item=item, response=response, latency_ms=15.0)
    assert case_eval.decision_agreement is True
    assert case_eval.robustness_agreement is True


def test_benchmark_runner_mock_execution(test_db_session):
    """
    Verifies full benchmark dataset execution using MockLLMProvider and in-memory test database.
    """
    runner = BenchmarkRunner()
    provider = MockLLMProvider()

    report = runner.run_benchmark(db=test_db_session, provider=provider, max_turns=3, provider_name="mock")

    assert isinstance(report, BenchmarkReport)
    assert report.total_cases == 20
    assert report.successful_cases == 20
    assert report.failed_cases == 0
    assert report.sql_execution_success_rate > 0.0
    assert report.groundedness_rate > 0.0
    assert report.average_latency_ms > 0.0
    assert len(report.case_evaluations) == 20
