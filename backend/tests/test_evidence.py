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
