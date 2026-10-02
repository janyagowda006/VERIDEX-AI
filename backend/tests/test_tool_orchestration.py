import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session

from app.schemas.ai import AskResponse, ToolCallRecord
from app.schemas.evidence import EvidenceItem, EvidenceType
from app.tools.registry import ToolRegistry, ToolExecutionResult
from app.ai.provider import MockLLMProvider, ModelResponse, ToolCallRequest
from app.ai.orchestrator import run_investigation_loop


def test_tool_registry_initialization():
    """
    Verifies ToolRegistry initializes with all four core specialized tools.
    """
    registry = ToolRegistry()
    tools = registry.list_tools()
    tool_names = [t.name for t in tools]

    assert "sql_query" in tool_names
    assert "driver_decomposition" in tool_names
    assert "campaign_impact" in tool_names
    assert "claim_verification" in tool_names


def test_tool_registry_rejects_unknown_tool(test_db_session):
    """
    Verifies ToolRegistry safely rejects requests for unknown or un-registered tools (Phase 12: F).
    """
    registry = ToolRegistry()
    res = registry.execute_tool("unknown_tool_xyz", test_db_session, {})

    assert res.success is False
    assert res.error_type == "UNSUPPORTED_TOOL"
    assert "Unsupported tool" in res.error_message


def test_tool_registry_invalid_arguments(test_db_session):
    """
    Verifies ToolRegistry safely rejects malformed or missing tool arguments (Phase 12: G).
    """
    registry = ToolRegistry()
    
    # Missing required 'sql' in sql_query
    res_sql = registry.execute_tool("sql_query", test_db_session, {"sql": ""})
    assert res_sql.success is False
    assert res_sql.error_type == "MALFORMED_ARGUMENT"

    # Missing required 'period_a' in driver_decomposition
    res_decomp = registry.execute_tool("driver_decomposition", test_db_session, {})
    assert res_decomp.success is False
    assert res_decomp.error_type == "MALFORMED_ARGUMENT"

    # Missing required 'campaign_id' in campaign_impact
    res_camp = registry.execute_tool("campaign_impact", test_db_session, {})
    assert res_camp.success is False
    assert res_camp.error_type == "MALFORMED_ARGUMENT"


def test_orchestration_sql_tool(test_db_session):
    """
    Verifies SQL question selects and executes sql_query tool (Phase 12: A).
    """
    provider = MockLLMProvider()
    res = run_investigation_loop("What were our sales last month?", test_db_session, provider, max_turns=3)

    assert res.success is True
    assert len(res.tool_calls) >= 1
    assert res.tool_calls[0].tool_name == "sql_query"
    assert len(res.evidence) >= 1
    assert any(ev.evidence_type == EvidenceType.FACT for ev in res.evidence)


def test_orchestration_driver_decomposition(test_db_session):
    """
    Verifies driver decomposition question selects and executes driver_decomposition tool (Phase 12: B).
    """
    provider = MockLLMProvider()
    res = run_investigation_loop("Why did revenue decline between January and February?", test_db_session, provider, max_turns=3)

    assert res.success is True
    assert len(res.tool_calls) >= 1
    assert res.tool_calls[0].tool_name == "driver_decomposition"
    assert len(res.evidence) >= 1
    assert any(ev.evidence_type == EvidenceType.DERIVED_FACT for ev in res.evidence)


def test_orchestration_campaign_impact(test_db_session):
    """
    Verifies campaign question selects and executes campaign_impact tool (Phase 12: C).
    """
    provider = MockLLMProvider()
    res = run_investigation_loop("Did the South campaign actually increase revenue?", test_db_session, provider, max_turns=3)

    assert res.success is True
    assert len(res.tool_calls) >= 1
    assert res.tool_calls[0].tool_name == "campaign_impact"
    assert len(res.evidence) >= 1
    assert any(ev.evidence_type == EvidenceType.DERIVED_FACT for ev in res.evidence)


def test_orchestration_multi_tool_investigation(test_db_session):
    """
    Verifies single investigation can execute multiple tools in sequence (Phase 12: E).
    """
    provider = MockLLMProvider()
    res = run_investigation_loop("Revenue fell last month. Why, and did the campaign help?", test_db_session, provider, max_turns=3)

    assert res.success is True
    assert len(res.tool_calls) == 2
    assert res.tool_calls[0].tool_name == "driver_decomposition"
    assert res.tool_calls[1].tool_name == "campaign_impact"
    assert len(res.evidence) >= 2


def test_orchestration_tool_failure_handling(test_db_session):
    """
    Verifies tool execution failures are handled gracefully without corrupting evidence (Phase 12: H).
    """
    responses = [
        ModelResponse(
            has_tool_call=True,
            tool_call=ToolCallRequest(
                tool_name="driver_decomposition",
                arguments={"metric": "invalid_metric", "period_a": {"start_date": "2025-01-01", "end_date": "2025-03-31"}, "period_b": {"start_date": "2025-04-01", "end_date": "2025-06-30"}}
            )
        ),
        ModelResponse(
            has_tool_call=False,
            content="Tool execution failed due to invalid metric specification."
        )
    ]
    provider = MockLLMProvider(custom_responses=responses)
    res = run_investigation_loop("Failed tool test", test_db_session, provider, max_turns=3)

    assert res.success is True
    assert len(res.tool_calls) == 1
    assert res.tool_calls[0].result.success is False
    assert res.tool_calls[0].result.error_type == "TOOL_EXECUTION_ERROR"


def test_orchestration_claim_verification_integration(test_db_session):
    """
    Verifies final claims are checked against evidence via Claim Checker (Phase 12: D, J).
    """
    responses = [
        ModelResponse(
            has_tool_call=True,
            tool_call=ToolCallRequest(
                tool_name="sql_query",
                arguments={"sql": "SELECT c.region, COUNT(o.order_id) AS total_orders FROM orders o JOIN customers c ON o.customer_id = c.customer_id GROUP BY c.region LIMIT 1"}
            )
        ),
        ModelResponse(
            has_tool_call=False,
            content="Database query completed. Total orders in region was observed."
        )
    ]
    provider = MockLLMProvider(custom_responses=responses)
    res = run_investigation_loop("Claim check integration test", test_db_session, provider, max_turns=3)

    assert res.success is True
    assert len(res.claims) >= 1
    assert res.analysis is not None
    assert res.analysis.robustness is not None
