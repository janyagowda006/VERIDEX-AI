import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.db import get_db
from app.schemas.sql_tool import SQLQueryResult, QueryMetadata
from app.schemas.evidence import EvidenceType, EvidenceSource, DerivedFactCalculation, EvidenceItem, ClaimEvidence
from app.services.evidence_assembler import EvidenceAssembler
from app.services.evidence_calculations import EvidenceCalculator
from app.ai.orchestrator import run_investigation_loop, _build_claims_and_evidence
from app.ai.provider import MockLLMProvider, get_llm_provider

client = TestClient(app)


def test_fact_evidence_creation_from_sql_result():
    assembler = EvidenceAssembler()
    meta = QueryMetadata(
        execution_time_ms=12.5,
        row_count=2,
        columns=["region", "revenue"],
        truncated=False,
        query_hash="hash_12345",
        timestamp="2026-09-30T00:00:00Z"
    )
    result = SQLQueryResult(
        success=True,
        sql="SELECT region, revenue FROM customers",
        data=[{"region": "North", "revenue": 1000.0}, {"region": "South", "revenue": 800.0}],
        columns=["region", "revenue"],
        row_count=2,
        metadata=meta
    )

    ev = assembler.extract_fact_evidence(result)
    assert ev is not None
    assert ev.evidence_type == EvidenceType.FACT
    assert ev.source is not None
    assert ev.source.query_hash == "hash_12345"
    assert ev.source.sql == "SELECT region, revenue FROM customers"


def test_derived_fact_evidence_creation():
    calculator = EvidenceCalculator()
    derived = calculator.percentage_change(1200.0, 1000.0, "North", "South", ["ev_fact_1"])

    assert derived.evidence_type == EvidenceType.DERIVED_FACT
    assert derived.calculation is not None
    assert derived.calculation.formula_name == "percentage_change"
    assert derived.calculation.output == 20.0
    assert "ev_fact_1" in derived.calculation.input_evidence_ids


def test_inference_evidence_classification():
    claims, evidence = _build_claims_and_evidence(
        "The regional difference suggests higher market penetration in North.",
        []
    )
    inf_items = [ev for ev in evidence if ev.evidence_type == EvidenceType.INFERENCE]
    inf_claims = [c for c in claims if c.evidence_type == EvidenceType.INFERENCE]

    assert len(inf_items) == 1
    assert len(inf_claims) == 1
    assert inf_items[0].evidence_type == EvidenceType.INFERENCE
    assert "qualitative" in inf_items[0].description.lower() or "interpretation" in inf_items[0].description.lower()


def test_query_hash_preservation():
    assembler = EvidenceAssembler()
    meta = QueryMetadata(
        execution_time_ms=5.0,
        row_count=1,
        columns=["id"],
        truncated=False,
        query_hash="abc_sha256_hash",
        timestamp="2026-09-30T00:00:00Z"
    )
    result = SQLQueryResult(
        success=True,
        sql="SELECT id FROM orders",
        data=[{"id": 1}],
        columns=["id"],
        row_count=1,
        metadata=meta
    )
    ev = assembler.extract_fact_evidence(result)
    assert ev.source.query_hash == "abc_sha256_hash"


def test_sql_provenance_preservation():
    assembler = EvidenceAssembler()
    sql_text = "SELECT c.customer_name, c.region FROM customers c WHERE c.region = 'North'"
    meta = QueryMetadata(
        execution_time_ms=8.0,
        row_count=1,
        columns=["customer_name", "region"],
        truncated=False,
        query_hash="hash99",
        timestamp="2026-09-30T00:00:00Z"
    )
    result = SQLQueryResult(
        success=True,
        sql=sql_text,
        data=[{"customer_name": "Alice", "region": "North"}],
        columns=["customer_name", "region"],
        row_count=1,
        metadata=meta
    )
    ev = assembler.extract_fact_evidence(result)
    assert ev.source.sql == sql_text


def test_timestamp_preservation():
    assembler = EvidenceAssembler()
    ts = "2026-09-30T12:34:56.789Z"
    meta = QueryMetadata(
        execution_time_ms=3.0,
        row_count=1,
        columns=["col"],
        truncated=False,
        query_hash="h1",
        timestamp=ts
    )
    result = SQLQueryResult(
        success=True,
        sql="SELECT col FROM table",
        data=[{"col": "val"}],
        columns=["col"],
        row_count=1,
        metadata=meta
    )
    ev = assembler.extract_fact_evidence(result)
    assert ev.source.timestamp == ts


def test_column_preservation():
    assembler = EvidenceAssembler()
    cols = ["customer_id", "region", "total_orders"]
    meta = QueryMetadata(
        execution_time_ms=4.0,
        row_count=1,
        columns=cols,
        truncated=False,
        query_hash="h2",
        timestamp="2026-09-30T00:00:00Z"
    )
    result = SQLQueryResult(
        success=True,
        sql="SELECT customer_id, region, total_orders FROM customers",
        data=[{"customer_id": 1, "region": "East", "total_orders": 5}],
        columns=cols,
        row_count=1,
        metadata=meta
    )
    ev = assembler.extract_fact_evidence(result)
    assert ev.source.columns == cols


def test_relevant_row_preservation():
    assembler = EvidenceAssembler()
    sample = [{"a": 10}, {"a": 20}]
    meta = QueryMetadata(
        execution_time_ms=2.0,
        row_count=2,
        columns=["a"],
        truncated=False,
        query_hash="h3",
        timestamp="2026-09-30T00:00:00Z"
    )
    result = SQLQueryResult(
        success=True,
        sql="SELECT a FROM t",
        data=sample,
        columns=["a"],
        row_count=2,
        metadata=meta
    )
    ev = assembler.extract_fact_evidence(result)
    assert ev.source.relevant_rows == sample


def test_truncation_metadata_preservation():
    assembler = EvidenceAssembler()
    meta = QueryMetadata(
        execution_time_ms=10.0,
        row_count=100,
        columns=["val"],
        truncated=True,
        query_hash="h4",
        timestamp="2026-09-30T00:00:00Z"
    )
    result = SQLQueryResult(
        success=True,
        sql="SELECT val FROM t LIMIT 100",
        data=[{"val": i} for i in range(100)],
        columns=["val"],
        row_count=100,
        metadata=meta
    )
    ev = assembler.extract_fact_evidence(result)
    assert ev.source.execution_metadata["truncated"] is True
    assert any("truncated" in lim.lower() for lim in ev.limitations)


def test_percentage_change_calculation():
    calculator = EvidenceCalculator()
    res = calculator.percentage_change(150.0, 100.0, "Current", "Baseline")
    assert res.calculation.output == 50.0

    res_neg = calculator.percentage_change(80.0, 100.0, "Current", "Baseline")
    assert res_neg.calculation.output == -20.0


def test_difference_calculation():
    calculator = EvidenceCalculator()
    res = calculator.difference(500.0, 350.0, "Sales A", "Sales B")
    assert res.calculation.output == 150.0


def test_ratio_calculation():
    calculator = EvidenceCalculator()
    res = calculator.ratio(300.0, 150.0, "Revenue", "Cost")
    assert res.calculation.output == 2.0


def test_share_of_total_calculation():
    calculator = EvidenceCalculator()
    res = calculator.share_of_total(25.0, 100.0, "North Region", "Total")
    assert res.calculation.output == 25.0


def test_division_by_zero_handling():
    calculator = EvidenceCalculator()
    res_pct = calculator.percentage_change(100.0, 0.0, "Current", "ZeroBaseline")
    assert res_pct.calculation.output is None
    assert any("zero" in lim.lower() for lim in res_pct.limitations)

    res_ratio = calculator.ratio(50.0, 0.0, "Numerator", "ZeroDenominator")
    assert res_ratio.calculation.output is None
    assert any("zero" in lim.lower() for lim in res_ratio.limitations)


def test_missing_evidence_handling():
    assembler = EvidenceAssembler()
    failed_result = SQLQueryResult(
        success=False,
        sql="SELECT * FROM missing_table",
        error_type="UNKNOWN_IDENTIFIER",
        error_message="Table missing_table does not exist"
    )
    ev = assembler.extract_fact_evidence(failed_result)
    assert ev is None


def test_unsupported_claim_handling():
    claims, evidence = _build_claims_and_evidence("Generic unsupported answer text", [])
    assert len(evidence) == 0
    assert len(claims) == 0


def test_claim_to_evidence_mapping():
    fact_ev = EvidenceItem(
        evidence_id="ev_fact_10",
        evidence_type=EvidenceType.FACT,
        description="Factual sales data"
    )
    claims, evidence = _build_claims_and_evidence("Observed data shows sales growth", [fact_ev])
    assert len(claims) == 1
    assert claims[0].evidence_type == EvidenceType.FACT
    assert "ev_fact_10" in claims[0].evidence_ids


def test_multiple_evidence_items_single_claim():
    ev1 = EvidenceItem(evidence_id="ev_fact_1", evidence_type=EvidenceType.FACT, description="Fact 1")
    ev2 = EvidenceItem(evidence_id="ev_fact_2", evidence_type=EvidenceType.FACT, description="Fact 2")
    claims, evidence = _build_claims_and_evidence("Data compiled from queries", [ev1, ev2])

    fact_claim = claims[0]
    assert "ev_fact_1" in fact_claim.evidence_ids
    assert "ev_fact_2" in fact_claim.evidence_ids


def test_evidence_from_multiple_sql_queries(test_db_session):
    provider = MockLLMProvider()
    res = run_investigation_loop(
        question="What is our gross revenue by region?",
        db=test_db_session,
        provider=provider,
        max_turns=3
    )
    assert res.success is True
    assert len(res.evidence) > 0
    assert any(ev.evidence_type == EvidenceType.FACT for ev in res.evidence)


def test_no_fabricated_evidence():
    assembler = EvidenceAssembler()
    meta = QueryMetadata(
        execution_time_ms=1.0,
        row_count=0,
        columns=["a"],
        truncated=False,
        query_hash="h5",
        timestamp="2026-09-30T00:00:00Z"
    )
    result = SQLQueryResult(
        success=True,
        sql="SELECT a FROM empty_table",
        data=[],
        columns=["a"],
        row_count=0,
        metadata=meta
    )
    ev = assembler.extract_fact_evidence(result)
    assert ev.source.relevant_rows == []
    assert any("zero rows" in lim.lower() for lim in ev.limitations)


def test_phase_4_orchestrator_compatibility(test_db_session):
    provider = MockLLMProvider()
    res = run_investigation_loop(
        question="Show top products",
        db=test_db_session,
        provider=provider,
        max_turns=3
    )

    assert hasattr(res, "claims")
    assert hasattr(res, "evidence")
    assert res.success is True
    assert res.question == "Show top products"


def test_ask_endpoint_evidence_response(test_db_session):
    app.dependency_overrides[get_db] = lambda: test_db_session
    app.dependency_overrides[get_llm_provider] = lambda: MockLLMProvider()

    try:
        response = client.post(
            "/api/ask",
            json={"question": "What is our gross revenue by region?", "max_turns": 3}
        )

        assert response.status_code == 200
        data = response.json()

        assert "claims" in data
        assert "evidence" in data
        assert isinstance(data["claims"], list)
        assert isinstance(data["evidence"], list)
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------
# Phase 7A: Growth Rate, Margin Percent, Statistical Summary,
# Safe Compound Metric, and Provenance Tests
# ---------------------------------------------------------

def test_growth_rate_positive():
    calc = EvidenceCalculator()
    res = calc.growth_rate(120.0, 100.0, "Current Revenue", "Previous Revenue", ["ev_fact_1"])
    assert res.evidence_type == EvidenceType.DERIVED_FACT
    assert res.calculation is not None
    assert res.calculation.formula_name == "growth_rate"
    assert res.calculation.output == 20.0
    assert "ev_fact_1" in res.calculation.input_evidence_ids
    assert "positive growth" in res.description.lower()
    assert len(res.limitations) == 0


def test_growth_rate_negative():
    calc = EvidenceCalculator()
    res = calc.growth_rate(80.0, 100.0, "Current", "Previous")
    assert res.calculation.output == -20.0
    assert "negative growth" in res.description.lower()


def test_growth_rate_negative_previous_value():
    calc = EvidenceCalculator()
    res = calc.growth_rate(-80.0, -100.0, "Current", "Previous")
    # ((-80 - (-100)) / -100) * 100 = (20 / -100) * 100 = -20.0%
    assert res.calculation.output == -20.0
    assert "negative growth" in res.description.lower()



def test_growth_rate_zero():
    calc = EvidenceCalculator()
    res = calc.growth_rate(100.0, 100.0, "Current", "Previous")
    assert res.calculation.output == 0.0
    assert "zero growth" in res.description.lower()


def test_growth_rate_zero_denominator():
    calc = EvidenceCalculator()
    res = calc.growth_rate(150.0, 0.0, "Current", "ZeroPrevious")
    assert res.calculation.output is None
    assert any("zero" in lim.lower() for lim in res.limitations)
    assert "undefined" in res.description.lower()


def test_growth_rate_decimal_values():
    calc = EvidenceCalculator()
    res = calc.growth_rate(123.45, 98.76, "Current", "Previous")
    expected = round(((123.45 - 98.76) / 98.76) * 100, 2)
    assert res.calculation.output == expected
    assert res.calculation.output == 25.0


def test_margin_percent_positive():
    calc = EvidenceCalculator()
    res = calc.margin_percent(1000.0, 700.0, "Gross Revenue", "COGS", ["ev_fact_2"])
    assert res.evidence_type == EvidenceType.DERIVED_FACT
    assert res.calculation.formula_name == "margin_percent"
    assert res.calculation.output == 30.0
    assert "ev_fact_2" in res.calculation.input_evidence_ids
    assert len(res.limitations) == 0


def test_margin_percent_zero():
    calc = EvidenceCalculator()
    res = calc.margin_percent(500.0, 500.0, "Revenue", "Cost")
    assert res.calculation.output == 0.0


def test_margin_percent_negative():
    calc = EvidenceCalculator()
    res = calc.margin_percent(800.0, 1000.0, "Revenue", "Cost")
    assert res.calculation.output == -25.0


def test_margin_percent_zero_revenue():
    calc = EvidenceCalculator()
    res = calc.margin_percent(0.0, 100.0, "ZeroRevenue", "Cost")
    assert res.calculation.output is None
    assert any("zero" in lim.lower() for lim in res.limitations)
    assert "undefined" in res.description.lower()


def test_margin_percent_decimal_values():
    calc = EvidenceCalculator()
    res = calc.margin_percent(1450.75, 980.50, "Revenue", "Cost")
    expected = round(((1450.75 - 980.50) / 1450.75) * 100, 2)
    assert res.calculation.output == expected
    assert res.calculation.output == 32.41


def test_statistical_summary_normal_unsorted_list():
    calc = EvidenceCalculator()
    values = [50, 10, 30, 20, 40]
    res = calc.statistical_summary(values, "Order Amounts", ["ev_fact_3"])

    assert res.evidence_type == EvidenceType.DERIVED_FACT
    assert res.calculation.formula_name == "statistical_summary"
    assert "ev_fact_3" in res.calculation.input_evidence_ids
    output = res.calculation.output
    assert output["count"] == 5
    assert output["min"] == 10.0
    assert output["max"] == 50.0
    assert output["mean"] == 30.0
    assert output["median"] == 30.0
    assert output["q1"] == 15.0
    assert output["q3"] == 45.0
    assert output["iqr"] == 30.0
    assert len(res.limitations) == 0


def test_statistical_summary_single_value():
    calc = EvidenceCalculator()
    res = calc.statistical_summary([42.5], "SingleMetric")
    output = res.calculation.output
    assert output["count"] == 1
    assert output["min"] == 42.5
    assert output["max"] == 42.5
    assert output["mean"] == 42.5
    assert output["median"] == 42.5
    assert output["q1"] == 42.5
    assert output["q3"] == 42.5
    assert output["iqr"] == 0.0


def test_statistical_summary_two_values():
    calc = EvidenceCalculator()
    res = calc.statistical_summary([10.0, 30.0], "TwoValues")
    output = res.calculation.output
    assert output["count"] == 2
    assert output["min"] == 10.0
    assert output["max"] == 30.0
    assert output["mean"] == 20.0
    assert output["median"] == 20.0
    assert output["q1"] == 10.0
    assert output["q3"] == 30.0
    assert output["iqr"] == 20.0


def test_statistical_summary_repeated_values():
    calc = EvidenceCalculator()
    res = calc.statistical_summary([7, 7, 7, 7], "RepeatedValues")
    output = res.calculation.output
    assert output["count"] == 4
    assert output["min"] == 7.0
    assert output["max"] == 7.0
    assert output["mean"] == 7.0
    assert output["median"] == 7.0
    assert output["iqr"] == 0.0


def test_statistical_summary_negative_and_decimal_values():
    calc = EvidenceCalculator()
    values = [-10.5, 0.0, 10.5, 21.0]
    res = calc.statistical_summary(values, "SpreadValues")
    output = res.calculation.output
    assert output["count"] == 4
    assert output["min"] == -10.5
    assert output["max"] == 21.0
    assert output["mean"] == 5.25
    assert output["median"] == 5.25
    assert output["q1"] == -5.25
    assert output["q3"] == 15.75
    assert output["iqr"] == 21.0


def test_statistical_summary_empty_list():
    calc = EvidenceCalculator()
    res = calc.statistical_summary([], "EmptyMetric")
    assert res.calculation.output is None
    assert any("empty" in lim.lower() for lim in res.limitations)


def test_statistical_summary_invalid_non_numeric_input():
    calc = EvidenceCalculator()
    res = calc.statistical_summary([10.0, "corrupted", None, True], "CorruptedMetric")
    assert res.calculation.output is None
    assert any("non-numeric" in lim.lower() for lim in res.limitations)


def test_compound_metric_registered_safe_template():
    calc = EvidenceCalculator()
    res = calc.compound_metric(
        name="gross_margin_check",
        formula_expr="((a - b) / a) * 100",
        inputs={"revenue": 1000.0, "cost": 650.0},
        input_evidence_ids=["ev_fact_9"]
    )
    assert res.evidence_type == EvidenceType.DERIVED_FACT
    assert res.calculation.output == 35.0
    assert "ev_fact_9" in res.calculation.input_evidence_ids
    assert len(res.limitations) == 0


def test_compound_metric_safe_difference():
    calc = EvidenceCalculator()
    res = calc.compound_metric(
        name="sales_diff",
        formula_expr="a - b",
        inputs={"q1": 500.0, "q2": 320.0}
    )
    assert res.calculation.output == 180.0


def test_compound_metric_rejects_arbitrary_eval_execution():
    calc = EvidenceCalculator()
    res = calc.compound_metric(
        name="arbitrary_exploit_attempt",
        formula_expr="__import__('os').system('echo pwned')",
        inputs={"val": 100.0}
    )
    assert res.calculation.output is None
    assert any("security rejection" in lim.lower() for lim in res.limitations)


def test_compound_metric_rejects_invalid_inputs():
    calc = EvidenceCalculator()
    res = calc.compound_metric(
        name="invalid_input_test",
        formula_expr="a - b",
        inputs={"a": "bad_string", "b": 10.0}
    )
    assert res.calculation.output is None
    assert any("non-numeric" in lim.lower() for lim in res.limitations)


def test_new_derived_evidence_provenance_preservation():
    calc = EvidenceCalculator()
    gr = calc.growth_rate(200.0, 100.0, "Rev2", "Rev1", ["ev_1", "ev_2"])
    mp = calc.margin_percent(500.0, 250.0, "Rev", "Cost", ["ev_3"])
    ss = calc.statistical_summary([1, 2, 3], "Vals", ["ev_4"])

    for item in [gr, mp, ss]:
        assert item.evidence_id.startswith("ev_derived_")
        assert item.evidence_type == EvidenceType.DERIVED_FACT
        assert item.source is None
        assert item.calculation is not None
        assert len(item.calculation.input_evidence_ids) > 0
        assert item.calculation.formula_name != ""
        assert item.calculation.formula != ""
