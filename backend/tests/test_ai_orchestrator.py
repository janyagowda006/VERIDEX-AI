import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.db import get_db
from app.schemas.ai import AskRequest
from app.ai.prompts import SYSTEM_PROMPT_V1, format_schema_for_prompt
from app.ai.provider import BaseLLMProvider, MockLLMProvider, GeminiProvider, ModelResponse, ToolCallRequest, get_llm_provider
from app.ai.orchestrator import run_investigation_loop
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
