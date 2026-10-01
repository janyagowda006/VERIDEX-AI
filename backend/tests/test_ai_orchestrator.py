import pytest
from unittest.mock import patch, MagicMock
import google.genai
from fastapi.testclient import TestClient

from app.main import app
from app.core.db import get_db
from app.core.config import settings
from app.schemas.ai import AskRequest
from app.schemas.evidence import EvidenceItem, EvidenceType, ClaimEvidence
from app.ai.prompts import SYSTEM_PROMPT_V1, format_schema_for_prompt
from app.ai.provider import BaseLLMProvider, MockLLMProvider, GeminiProvider, ModelResponse, ToolCallRequest, get_llm_provider
from app.ai.orchestrator import run_investigation_loop, _build_claims_and_evidence, _clean_text_tags, _format_prior_turns_context
from app.services.schema_introspection import get_database_schema

client = TestClient(app)


def test_system_prompt_rendering(test_db_session):
    """
    Verifies system prompt formatting and schema context injection.
    """
    schema = get_database_schema(test_db_session)
    formatted_text = format_schema_for_prompt(schema)

    assert "Table: customers" in formatted_text
    assert "Table: products" in formatted_text
    assert "Table: orders" in formatted_text
    assert "Table: order_items" in formatted_text
    assert "FK:" in formatted_text

    full_prompt = SYSTEM_PROMPT_V1.format(schema_context_text=formatted_text)
    assert "VERIDEX" in full_prompt
    assert "SINGLE SOURCE OF TRUTH" in full_prompt


def test_mock_provider_orchestration_flow(test_db_session):
    """
    Tests end-to-end question -> tool call -> safe SQL execution -> final answer using MockLLMProvider.
    """
    provider = MockLLMProvider()
    res = run_investigation_loop(
        question="What is our gross revenue by region?",
        db=test_db_session,
        provider=provider,
        max_turns=3
    )

    assert res.success is True
    assert res.question == "What is our gross revenue by region?"
    assert len(res.tool_calls) == 1

    tool_call = res.tool_calls[0]
    assert tool_call.turn == 1
    assert tool_call.tool_name == "sql_query"
    assert tool_call.result.success is True
    assert tool_call.result.row_count > 0
    assert "region" in tool_call.result.columns

    assert "evidence" in res.answer.lower() or "completed" in res.answer.lower()


def test_mock_provider_via_ask_endpoint(test_db_session):
    """
    Tests POST /api/ask endpoint using MockLLMProvider and overridden DB & LLM provider dependencies.
    """
    app.dependency_overrides[get_db] = lambda: test_db_session
    app.dependency_overrides[get_llm_provider] = lambda: MockLLMProvider()

    try:
        response = client.post(
            "/api/ask",
            json={"question": "Show top 5 products by revenue", "max_turns": 3}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["question"] == "Show top 5 products by revenue"
        assert len(data["tool_calls"]) == 1
        assert data["tool_calls"][0]["tool_name"] == "sql_query"
        assert data["tool_calls"][0]["result"]["success"] is True
    finally:
        app.dependency_overrides.clear()


def test_unsafe_sql_rejection_in_loop(test_db_session):
    """
    Verifies that if an LLM emits an INSERT/DROP statement, execute_read_only_sql rejects it
    as UNSAFE_SQL and orchestrator captures the error safely without crashing.
    """
    unsafe_responses = [
        ModelResponse(
            has_tool_call=True,
            tool_call=ToolCallRequest(
                tool_name="sql_query",
                arguments={"sql": "DROP TABLE customers"}
            )
        ),
        ModelResponse(
            has_tool_call=False,
            content="Attempted query execution failed due to security rejection."
        )
    ]

    provider = MockLLMProvider(custom_responses=unsafe_responses)
    res = run_investigation_loop(
        question="Delete all customers",
        db=test_db_session,
        provider=provider,
        max_turns=3
    )

    assert res.success is True
    assert len(res.tool_calls) == 1
    tool_record = res.tool_calls[0]

    assert tool_record.result.success is False
    assert tool_record.result.error_type == "UNSAFE_SQL"
    assert "prohibited" in tool_record.result.error_message.lower() or "only select" in tool_record.result.error_message.lower()


def test_orchestrator_max_turns_bounding(test_db_session):
    """
    Verifies orchestrator loop halts when max_turns threshold is reached.
    """
    infinite_tool_responses = [
        ModelResponse(
            has_tool_call=True,
            tool_call=ToolCallRequest(
                tool_name="sql_query",
                arguments={"sql": "SELECT * FROM customers LIMIT 1"}
            )
        ) for _ in range(10)
    ]

    provider = MockLLMProvider(custom_responses=infinite_tool_responses)
    res = run_investigation_loop(
        question="Keep querying forever",
        db=test_db_session,
        provider=provider,
        max_turns=2
    )

    assert res.success is True
    assert len(res.tool_calls) == 2
    assert res.metadata.get("boundary_reached") is True
    assert "turn boundary" in res.answer.lower()


def test_missing_api_key_handling():
    """
    Verifies GeminiProvider returns structured error when API key is missing or unconfigured.
    """
    provider = GeminiProvider(api_key="your_llm_api_key_here")
    res = provider.generate_turn([], [], "")

    assert res.has_tool_call is False
    assert res.error is not None
    assert "api key is not configured" in res.error.lower()


def test_provider_factory_selection():
    """
    Verifies get_llm_provider returns MockLLMProvider when configured as mock.
    """
    with patch.object(settings, "LLM_PROVIDER", "mock"):
        provider = get_llm_provider()
        assert isinstance(provider, MockLLMProvider)

    with patch.object(settings, "LLM_PROVIDER", "gemini"):
        provider = get_llm_provider()
        assert isinstance(provider, GeminiProvider)


def test_gemini_provider_sanitizes_error_messages():
    """
    Verifies GeminiProvider redacts API key from exception error messages.
    """
    provider = GeminiProvider(api_key="secret_test_key_12345")
    with patch("google.genai.Client", side_effect=Exception("Failed connection using secret_test_key_12345")):
        res = provider.generate_turn([{"role": "user", "content": "hello"}], [], "schema")
        assert res.error is not None
        assert "secret_test_key_12345" not in res.error
        assert "[REDACTED_API_KEY]" in res.error


def test_duplicate_sql_query_detection(test_db_session):
    """
    Verifies that requesting the exact same SQL query twice in the loop detects
    the duplicate, skips secondary DB execution, and returns DUPLICATE_QUERY error.
    """
    responses = [
        ModelResponse(
            has_tool_call=True,
            tool_call=ToolCallRequest(
                tool_name="sql_query",
                arguments={"sql": "SELECT * FROM customers LIMIT 5"}
            )
        ),
        ModelResponse(
            has_tool_call=True,
            tool_call=ToolCallRequest(
                tool_name="sql_query",
                arguments={"sql": "SELECT * FROM customers LIMIT 5"}
            )
        ),
        ModelResponse(
            has_tool_call=False,
            content="Analysis complete after duplicate query prevention."
        )
    ]
    provider = MockLLMProvider(custom_responses=responses)
    res = run_investigation_loop(
        question="Duplicate query test",
        db=test_db_session,
        provider=provider,
        max_turns=3
    )

    assert res.success is True
    assert len(res.tool_calls) == 2
    assert res.tool_calls[0].result.success is True
    assert res.tool_calls[1].result.success is False
    assert res.tool_calls[1].result.error_type == "DUPLICATE_QUERY"
    assert "duplicate" in res.tool_calls[1].result.error_message.lower()


def test_duplicate_sql_query_whitespace_normalization(test_db_session):
    """
    Verifies that SQL whitespace and case variations are normalized and recognized as duplicates.
    """
    responses = [
        ModelResponse(
            has_tool_call=True,
            tool_call=ToolCallRequest(
                tool_name="sql_query",
                arguments={"sql": "SELECT * FROM customers LIMIT 5"}
            )
        ),
        ModelResponse(
            has_tool_call=True,
            tool_call=ToolCallRequest(
                tool_name="sql_query",
                arguments={"sql": "  select   *   from   customers   limit  5  "}
            )
        ),
        ModelResponse(
            has_tool_call=False,
            content="Analysis complete."
        )
    ]
    provider = MockLLMProvider(custom_responses=responses)
    res = run_investigation_loop(
        question="Whitespace normalization test",
        db=test_db_session,
        provider=provider,
        max_turns=3
    )

    assert res.success is True
    assert len(res.tool_calls) == 2
    assert res.tool_calls[0].result.success is True
    assert res.tool_calls[1].result.success is False
    assert res.tool_calls[1].result.error_type == "DUPLICATE_QUERY"


def test_distinct_sql_queries_allowed(test_db_session):
    """
    Verifies that distinct SQL queries in consecutive turns both execute successfully.
    """
    responses = [
        ModelResponse(
            has_tool_call=True,
            tool_call=ToolCallRequest(
                tool_name="sql_query",
                arguments={"sql": "SELECT * FROM customers LIMIT 2"}
            )
        ),
        ModelResponse(
            has_tool_call=True,
            tool_call=ToolCallRequest(
                tool_name="sql_query",
                arguments={"sql": "SELECT * FROM products LIMIT 2"}
            )
        ),
        ModelResponse(
            has_tool_call=False,
            content="Analysis complete for both tables."
        )
    ]
    provider = MockLLMProvider(custom_responses=responses)
    res = run_investigation_loop(
        question="Distinct query test",
        db=test_db_session,
        provider=provider,
        max_turns=3
    )

    assert res.success is True
    assert len(res.tool_calls) == 2
    assert res.tool_calls[0].result.success is True
    assert res.tool_calls[1].result.success is True


def test_malformed_tool_argument_missing_sql(test_db_session):
    """
    Verifies that tool call missing 'sql' argument returns MALFORMED_ARGUMENT error without calling DB.
    """
    responses = [
        ModelResponse(
            has_tool_call=True,
            tool_call=ToolCallRequest(
                tool_name="sql_query",
                arguments={}
            )
        ),
        ModelResponse(
            has_tool_call=False,
            content="Finished after receiving malformed argument error."
        )
    ]
    provider = MockLLMProvider(custom_responses=responses)
    res = run_investigation_loop(
        question="Missing sql arg test",
        db=test_db_session,
        provider=provider,
        max_turns=3
    )

    assert res.success is True
    assert len(res.tool_calls) == 1
    assert res.tool_calls[0].result.success is False
    assert res.tool_calls[0].result.error_type == "MALFORMED_ARGUMENT"


def test_malformed_tool_argument_non_string_sql(test_db_session):
    """
    Verifies that tool call with non-string 'sql' argument returns MALFORMED_ARGUMENT error without calling DB.
    """
    responses = [
        ModelResponse(
            has_tool_call=True,
            tool_call=ToolCallRequest(
                tool_name="sql_query",
                arguments={"sql": 12345}
            )
        ),
        ModelResponse(
            has_tool_call=False,
            content="Finished after receiving non-string argument error."
        )
    ]
    provider = MockLLMProvider(custom_responses=responses)
    res = run_investigation_loop(
        question="Non-string sql arg test",
        db=test_db_session,
        provider=provider,
        max_turns=3
    )

    assert res.success is True
    assert len(res.tool_calls) == 1
    assert res.tool_calls[0].result.success is False
    assert res.tool_calls[0].result.error_type == "MALFORMED_ARGUMENT"


def test_malformed_tool_argument_empty_sql(test_db_session):
    """
    Verifies that tool call with empty/whitespace-only 'sql' argument returns MALFORMED_ARGUMENT error.
    """
    responses = [
        ModelResponse(
            has_tool_call=True,
            tool_call=ToolCallRequest(
                tool_name="sql_query",
                arguments={"sql": "   "}
            )
        ),
        ModelResponse(
            has_tool_call=False,
            content="Finished after empty query error."
        )
    ]
    provider = MockLLMProvider(custom_responses=responses)
    res = run_investigation_loop(
        question="Empty sql arg test",
        db=test_db_session,
        provider=provider,
        max_turns=3
    )

    assert res.success is True
    assert len(res.tool_calls) == 1
    assert res.tool_calls[0].result.success is False
    assert res.tool_calls[0].result.error_type == "MALFORMED_ARGUMENT"


def test_max_turns_bounding_clamping(test_db_session):
    """
    Verifies max_turns bounds between 1 and 5 (clamping out-of-range values like 0 or 10).
    """
    provider = MockLLMProvider()

    res_min = run_investigation_loop(
        question="Test min turns",
        db=test_db_session,
        provider=provider,
        max_turns=0
    )
    assert res_min.metadata["max_turns"] == 1

    res_max = run_investigation_loop(
        question="Test max turns",
        db=test_db_session,
        provider=provider,
        max_turns=10
    )
    assert res_max.metadata["max_turns"] == 5


def test_repeated_duplicate_query_protection(test_db_session):
    """
    Verifies that a model sending the same duplicate query on every turn reaches turn boundary cleanly
    without crashing or executing redundant DB queries, and preserves initial evidence.
    """
    responses = [
        ModelResponse(
            has_tool_call=True,
            tool_call=ToolCallRequest(
                tool_name="sql_query",
                arguments={"sql": "SELECT * FROM customers LIMIT 2"}
            )
        ) for _ in range(5)
    ]

    provider = MockLLMProvider(custom_responses=responses)
    res = run_investigation_loop(
        question="Repeated duplicate loop test",
        db=test_db_session,
        provider=provider,
        max_turns=3
    )

    assert res.success is True
    assert len(res.tool_calls) == 3
    assert res.tool_calls[0].result.success is True
    assert res.tool_calls[1].result.error_type == "DUPLICATE_QUERY"
    assert res.tool_calls[2].result.error_type == "DUPLICATE_QUERY"
    assert res.metadata.get("boundary_reached") is True
    assert len(res.evidence) >= 1


def test_ai3_single_valid_evidence_tag(test_db_session):
    """
    TEST 1: Single valid evidence tag [ev_fact_1] is extracted, verified, and mapped.
    """
    responses = [
        ModelResponse(
            has_tool_call=True,
            tool_call=ToolCallRequest(
                tool_name="sql_query",
                arguments={"sql": "SELECT * FROM customers LIMIT 2"}
            )
        ),
        ModelResponse(
            has_tool_call=False,
            content="North region generated $1.2M in revenue. [ev_fact_1]"
        )
    ]
    provider = MockLLMProvider(custom_responses=responses)
    res = run_investigation_loop("Single tag test", test_db_session, provider, max_turns=3)

    assert res.success is True
    assert len(res.claims) == 1
    claim = res.claims[0]
    assert claim.claim_text == "North region generated $1.2M in revenue."
    assert claim.evidence_ids == ["ev_fact_1"]
    assert claim.is_supported is True
    assert claim.evidence_type == EvidenceType.FACT
    assert "[ev_fact_1]" not in res.answer


def test_ai3_multiple_valid_evidence_tags(test_db_session):
    """
    TEST 2: Multiple valid evidence tags [ev_fact_1] [ev_derived_1] on a claim.
    """
    responses = [
        ModelResponse(
            has_tool_call=True,
            tool_call=ToolCallRequest(
                tool_name="sql_query",
                arguments={"sql": "SELECT product_id, unit_price FROM products LIMIT 2"}
            )
        ),
        ModelResponse(
            has_tool_call=False,
            content="Product 1 led price comparison. [ev_fact_1] [ev_derived_1]"
        )
    ]
    provider = MockLLMProvider(custom_responses=responses)
    res = run_investigation_loop("Multiple tags test", test_db_session, provider, max_turns=3)

    assert res.success is True
    assert len(res.claims) >= 1
    claim = res.claims[0]
    assert "ev_fact_1" in claim.evidence_ids
    assert "ev_derived_1" in claim.evidence_ids
    assert claim.is_supported is True
    assert claim.evidence_type == EvidenceType.DERIVED_FACT


def test_ai3_unknown_evidence_id_rejected(test_db_session):
    """
    TEST 3: Unknown evidence ID [ev_fact_999] is rejected and marked unsupported.
    """
    responses = [
        ModelResponse(
            has_tool_call=True,
            tool_call=ToolCallRequest(
                tool_name="sql_query",
                arguments={"sql": "SELECT * FROM customers LIMIT 1"}
            )
        ),
        ModelResponse(
            has_tool_call=False,
            content="North region generated $1.2M in revenue. [ev_fact_999]"
        )
    ]
    provider = MockLLMProvider(custom_responses=responses)
    res = run_investigation_loop("Unknown ID test", test_db_session, provider, max_turns=3)

    assert res.success is True
    assert len(res.claims) == 1
    claim = res.claims[0]
    assert "ev_fact_999" not in claim.evidence_ids
    assert claim.evidence_ids == []
    assert claim.is_supported is False


def test_ai3_mixed_valid_and_invalid_evidence_ids(test_db_session):
    """
    TEST 4: Mixed valid + invalid IDs preserves valid ID and filters invalid ID.
    """
    responses = [
        ModelResponse(
            has_tool_call=True,
            tool_call=ToolCallRequest(
                tool_name="sql_query",
                arguments={"sql": "SELECT * FROM customers LIMIT 1"}
            )
        ),
        ModelResponse(
            has_tool_call=False,
            content="North region generated $1.2M in revenue. [ev_fact_1] [ev_fact_999]"
        )
    ]
    provider = MockLLMProvider(custom_responses=responses)
    res = run_investigation_loop("Mixed IDs test", test_db_session, provider, max_turns=3)

    assert res.success is True
    assert len(res.claims) == 1
    claim = res.claims[0]
    assert claim.evidence_ids == ["ev_fact_1"]
    assert claim.is_supported is True


def test_ai3_claim_with_no_evidence_tag(test_db_session):
    """
    TEST 5: Claim with no evidence tag is not falsely marked supported.
    """
    responses = [
        ModelResponse(
            has_tool_call=True,
            tool_call=ToolCallRequest(
                tool_name="sql_query",
                arguments={"sql": "SELECT * FROM customers LIMIT 1"}
            )
        ),
        ModelResponse(
            has_tool_call=False,
            content="North region generated $1.2M. [ev_fact_1] We should expand operations to new markets."
        )
    ]
    provider = MockLLMProvider(custom_responses=responses)
    res = run_investigation_loop("No tag claim test", test_db_session, provider, max_turns=3)

    assert res.success is True
    assert len(res.claims) == 2
    c1, c2 = res.claims[0], res.claims[1]
    assert c1.is_supported is True
    assert c1.evidence_ids == ["ev_fact_1"]

    assert c2.evidence_ids == []
    assert c2.is_supported is False


def test_ai3_fact_claim_classification(test_db_session):
    """
    TEST 6: FACT claim classification when citing only FACT evidence.
    """
    ev_items = [
        EvidenceItem(evidence_id="ev_fact_1", evidence_type=EvidenceType.FACT, description="Direct DB query")
    ]
    answer = "Customer count is 500. [ev_fact_1]"
    claims, _ = _build_claims_and_evidence(answer, ev_items)

    assert len(claims) == 1
    assert claims[0].evidence_type == EvidenceType.FACT
    assert claims[0].is_supported is True


def test_ai3_derived_fact_claim_classification(test_db_session):
    """
    TEST 7: DERIVED_FACT claim classification when citing DERIVED_FACT evidence.
    """
    ev_items = [
        EvidenceItem(evidence_id="ev_derived_1", evidence_type=EvidenceType.DERIVED_FACT, description="Arithmetic calc")
    ]
    answer = "Revenue increased by 18.4%. [ev_derived_1]"
    claims, _ = _build_claims_and_evidence(answer, ev_items)

    assert len(claims) == 1
    assert claims[0].evidence_type == EvidenceType.DERIVED_FACT
    assert claims[0].is_supported is True


def test_ai3_inference_claim_classification(test_db_session):
    """
    TEST 8: INFERENCE claim classification when citing INFERENCE evidence or qualitative indicator.
    """
    ev_items = [
        EvidenceItem(evidence_id="ev_inf_1", evidence_type=EvidenceType.INFERENCE, description="Qualitative inference")
    ]
    answer = "The trend suggests potential growth. [ev_inf_1]"
    claims, _ = _build_claims_and_evidence(answer, ev_items)

    assert len(claims) == 1
    assert claims[0].evidence_type == EvidenceType.INFERENCE
    assert claims[0].is_supported is True


def test_ai3_evidence_tags_removed_from_clean_claim_text():
    """
    TEST 9: Evidence tags are removed from clean claim text and answer text.
    """
    raw_text = "North region generated $1.2M. [ev_fact_1]"
    clean = _clean_text_tags(raw_text)

    assert clean == "North region generated $1.2M."
    assert "[ev_fact_1]" not in clean


def test_ai3_multiple_claims_with_different_evidence_mappings():
    """
    TEST 10: Multiple claims map cleanly to different evidence IDs.
    """
    ev_items = [
        EvidenceItem(evidence_id="ev_fact_1", evidence_type=EvidenceType.FACT, description="North rev"),
        EvidenceItem(evidence_id="ev_fact_2", evidence_type=EvidenceType.FACT, description="South rev"),
        EvidenceItem(evidence_id="ev_derived_1", evidence_type=EvidenceType.DERIVED_FACT, description="Growth calc"),
    ]
    answer = "North generated $1.2M. [ev_fact_1] South generated $800k. [ev_fact_2] Growth was 50%. [ev_derived_1]"
    claims, _ = _build_claims_and_evidence(answer, ev_items)

    assert len(claims) == 3
    assert claims[0].evidence_ids == ["ev_fact_1"]
    assert claims[0].evidence_type == EvidenceType.FACT

    assert claims[1].evidence_ids == ["ev_fact_2"]
    assert claims[1].evidence_type == EvidenceType.FACT

    assert claims[2].evidence_ids == ["ev_derived_1"]
    assert claims[2].evidence_type == EvidenceType.DERIVED_FACT


def test_ai3_malformed_evidence_tags_handling():
    """
    TEST 11: Malformed evidence tags are ignored/cleaned without crashing.
    """
    ev_items = [
        EvidenceItem(evidence_id="ev_fact_1", evidence_type=EvidenceType.FACT, description="Fact 1")
    ]
    answer = "North generated $1.2M. [ev_fact_1 [ev_fact_] [ev_invalid#1] [ev_fact_1]"
    claims, _ = _build_claims_and_evidence(answer, ev_items)

    assert len(claims) == 1
    assert claims[0].evidence_ids == ["ev_fact_1"]
    assert "[" not in claims[0].claim_text


def test_ai3_duplicate_evidence_tags_uniquified():
    """
    TEST 12: Duplicate evidence tags in a single claim do not create duplicate IDs in evidence_ids.
    """
    ev_items = [
        EvidenceItem(evidence_id="ev_fact_1", evidence_type=EvidenceType.FACT, description="Fact 1")
    ]
    answer = "North generated $1.2M. [ev_fact_1] [ev_fact_1]"
    claims, _ = _build_claims_and_evidence(answer, ev_items)

    assert len(claims) == 1
    assert claims[0].evidence_ids == ["ev_fact_1"]


def test_format_prior_turns_context_bounds_and_formatting():
    """
    Verifies _format_prior_turns_context formats prior user questions and assistant answers
    with strict fact-grounding instructions.
    """
    mock_turn1 = MagicMock()
    mock_turn1.turn_number = 1
    mock_turn1.user_question = "What is revenue by region?"
    mock_turn1.result_json = '{"answer": "North generated $1.2M."}'

    mock_turn2 = MagicMock()
    mock_turn2.turn_number = 2
    mock_turn2.user_question = "Why did North outperform South?"
    mock_turn2.result_json = '{"answer": "North had strong marketing."}'

    context_text = _format_prior_turns_context([mock_turn1, mock_turn2])

    assert "<PRIOR_CONVERSATION_CONTEXT>" in context_text
    assert "</PRIOR_CONVERSATION_CONTEXT>" in context_text
    assert "Turn 1:" in context_text
    assert "What is revenue by region?" in context_text
    assert "North generated $1.2M." in context_text
    assert "Turn 2:" in context_text
    assert "Why did North outperform South?" in context_text
    assert "MUST NOT be treated as fresh FACT evidence" in context_text


def test_orchestrator_prior_turns_context_injection_and_fact_isolation(test_db_session):
    """
    Verifies run_investigation_loop injects prior turn context into LLM prompt
    while keeping FACT evidence strictly tied to current-turn SQL execution.
    """
    mock_turn = MagicMock()
    mock_turn.turn_number = 1
    mock_turn.user_question = "Initial revenue query"
    mock_turn.result_json = '{"answer": "Initial findings"}'

    provider = MockLLMProvider()
    res = run_investigation_loop(
        question="Was product mix the main driver?",
        db=test_db_session,
        provider=provider,
        max_turns=2,
        prior_turns=[mock_turn]
    )

    assert res.success is True
    # FACT evidence collected in current turn stems from current SQL execution only
    for item in res.evidence:
        if item.evidence_type == EvidenceType.FACT:
            assert item.description.startswith("Turn")
            assert item.source is not None
            assert item.source.sql is not None
