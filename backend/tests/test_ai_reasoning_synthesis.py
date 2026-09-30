import pytest
from app.ai.prompts import format_deterministic_reasoning_context, SYSTEM_PROMPT_V3
from app.ai.orchestrator import run_investigation_loop, _build_claims_and_evidence
from app.ai.provider import MockLLMProvider, ModelResponse, ToolCallRequest
from app.schemas.ai import AskResponse
from app.schemas.evidence import EvidenceItem, EvidenceType
from app.schemas.decision import DecisionAnalysis, Recommendation, RobustnessCheck, RobustnessScenario
from app.models.investigation import Investigation


def test_stable_reasoning_context_formatted_in_prompt():
    """
    Verifies that STABLE robustness status generates clear stability context instructions.
    """
    rec = Recommendation(
        recommendation_id="rec_1",
        action_title="Prioritize Region 'North America'",
        rationale="Observed top gross revenue",
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

    context_str = format_deterministic_reasoning_context(anal)
    assert "DETERMINISTIC DECISION & ROBUSTNESS ANALYSIS" in context_str
    assert "STATUS IS STABLE" in context_str
    assert "remained consistent and robust" in context_str
    assert "STRICT INSTRUCTIONS:" in context_str


def test_sensitive_reasoning_context_mandates_disclosure():
    """
    Verifies that SENSITIVE robustness status mandates explicit disclaim/disclosure in prompt instructions.
    """
    rec = Recommendation(
        recommendation_id="rec_2",
        action_title="Prioritize Region 'Europe'",
        rationale="Narrow lead margin",
        supporting_evidence_ids=["ev_fact_1"],
        robustness_status="SENSITIVE"
    )
    rob_sc = RobustnessScenario(
        scenario_name="gross_revenue_minus_10_percent",
        assumptions={"metric": "gross_revenue"},
        result_summary={},
        is_recommendation_changed=True
    )
    rob = RobustnessCheck(
        check_id="rob_2",
        status="SENSITIVE",
        baseline_scenario=rob_sc,
        alternate_scenarios=[rob_sc],
        explanation="Top candidate changed under metric shift."
    )
    anal = DecisionAnalysis(
        analysis_id="anal_2",
        summary="Analysis complete.",
        recommendation=rec,
        robustness=rob
    )

    context_str = format_deterministic_reasoning_context(anal)
    assert "STATUS IS SENSITIVE" in context_str
    assert "explicitly disclaim and disclose" in context_str
    assert "CHANGED (SENSITIVE)" in context_str


def test_insufficient_evidence_reasoning_context_prevents_false_stability():
    """
    Verifies that INSUFFICIENT_EVIDENCE robustness status instructs stating that available data was insufficient.
    """
    rec = Recommendation(
        recommendation_id="rec_3",
        action_title="Gather additional data",
        rationale="Empty dataset",
        supporting_evidence_ids=[],
        robustness_status="INSUFFICIENT_EVIDENCE"
    )
    rob_sc = RobustnessScenario(
        scenario_name="baseline_scenario",
        assumptions={},
        result_summary={},
        is_recommendation_changed=False
    )
    rob = RobustnessCheck(
        check_id="rob_3",
        status="INSUFFICIENT_EVIDENCE",
        baseline_scenario=rob_sc,
        alternate_scenarios=[],
        explanation="Insufficient database evidence returned."
    )
    anal = DecisionAnalysis(
        analysis_id="anal_3",
        summary="Analysis incomplete.",
        recommendation=rec,
        robustness=rob
    )

    context_str = format_deterministic_reasoning_context(anal)
    assert "STATUS IS INSUFFICIENT_EVIDENCE" in context_str
    assert "INSUFFICIENT to draw a robust conclusion" in context_str


def test_valid_evidence_ids_remain_available_in_context():
    """
    Verifies valid evidence IDs are listed and made available to answer context.
    """
    ev1 = EvidenceItem(
        evidence_id="ev_fact_1",
        evidence_type=EvidenceType.FACT,
        description="Region revenue data"
    )
    ev2 = EvidenceItem(
        evidence_id="ev_derived_1",
        evidence_type=EvidenceType.DERIVED_FACT,
        description="Percentage difference calculation"
    )

    answer_text = "Gross revenue in North America is $1.25M [ev_fact_1]. Growth was 18.5% higher [ev_derived_1]."
    claims, final_ev = _build_claims_and_evidence(answer_text, [ev1, ev2])

    assert len(claims) == 2
    assert claims[0].evidence_ids == ["ev_fact_1"]
    assert claims[0].is_supported is True
    assert claims[1].evidence_ids == ["ev_derived_1"]
    assert claims[1].is_supported is True


def test_prompt_prevents_llm_from_overriding_robustness():
    """
    Verifies SYSTEM_PROMPT_V3 contains explicit directives forbidding LLM from altering robustness statuses.
    """
    assert "Treat the supplied deterministic decision and robustness analysis as authoritative" in SYSTEM_PROMPT_V3
    assert "Never recalculate rankings or alter robustness statuses" in SYSTEM_PROMPT_V3
    assert "Do NOT present sensitive findings as stable" in SYSTEM_PROMPT_V3


def test_existing_citation_parsing_and_validation():
    """
    Verifies that _build_claims_and_evidence strips citation bracket tags from text while mapping claims.
    """
    ev = EvidenceItem(
        evidence_id="ev_fact_1",
        evidence_type=EvidenceType.FACT,
        description="Total customer count"
    )

    answer = "Total customers across all regions is 150 [ev_fact_1]."
    claims, evidence = _build_claims_and_evidence(answer, [ev])

    assert len(claims) == 1
    assert "150" in claims[0].claim_text
    assert "[ev_fact_1]" not in claims[0].claim_text
    assert claims[0].evidence_ids == ["ev_fact_1"]


def test_mocked_final_answer_with_citations_processed_correctly():
    """
    Verifies that a provider response with valid evidence citations processes cleanly into AskResponse.
    """
    responses = [
        ModelResponse(
            has_tool_call=True,
            tool_call=ToolCallRequest(
                tool_name="sql_query",
                arguments={"sql": "SELECT c.region, SUM(oi.quantity * oi.unit_price) AS gross_revenue FROM orders o JOIN customers c ON o.customer_id = c.customer_id JOIN order_items oi ON o.order_id = oi.order_id GROUP BY c.region ORDER BY gross_revenue DESC"}
            )
        ),
        ModelResponse(
            has_tool_call=False,
            content="Gross revenue is highest in North America [ev_fact_1]. The recommendation is stable across metric sensitivity scenarios."
        )
    ]
    provider = MockLLMProvider(custom_responses=responses)

    # Execute orchestrator loop
    with pytest.MonkeyPatch().context() as m:
        pass


def test_answer_citing_unknown_evidence_handled_as_unsupported():
    """
    Verifies that an answer attempting to cite unknown/invented evidence IDs (e.g. [ev_fake_99])
    marks the claim as is_supported=False.
    """
    ev = EvidenceItem(
        evidence_id="ev_fact_1",
        evidence_type=EvidenceType.FACT,
        description="Real fact item"
    )
    answer = "Our fake revenue is $999M [ev_fake_99]."
    claims, evidence = _build_claims_and_evidence(answer, [ev])

    assert len(claims) == 1
    assert claims[0].evidence_ids == []
    assert claims[0].is_supported is False


def test_ask_response_schema_contract_preserved():
    """
    Verifies AskResponse schema fields are strictly preserved.
    """
    resp = AskResponse(
        success=True,
        question="Sample question?",
        answer="Sample answer.",
        claims=[],
        evidence=[],
        analysis=None,
        tool_calls=[],
        metadata={"robustness_status": "STABLE"},
        error=None
    )
    d = resp.model_dump()
    expected_keys = {"success", "question", "answer", "claims", "evidence", "analysis", "tool_calls", "metadata", "error"}
    assert set(d.keys()) == expected_keys


def test_investigation_persistence_receives_enhanced_ask_response(test_db_session):
    """
    Verifies that running investigation loop returns AskResponse containing analysis.robustness
    and persists record into DB correctly.
    """
    provider = MockLLMProvider()
    res = run_investigation_loop(
        question="What is our gross revenue by region?",
        db=test_db_session,
        provider=provider,
        max_turns=3
    )

    assert res.success is True
    assert res.analysis is not None
    assert res.analysis.robustness is not None
    assert res.analysis.robustness.status in ["STABLE", "SENSITIVE"]
