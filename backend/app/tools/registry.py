import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from sqlalchemy.orm import Session

from app.schemas.evidence import EvidenceItem
from app.schemas.sql_tool import SQLQueryRequest, SQLQueryResult
from app.tools.sql_tool import execute_read_only_sql
from app.services.evidence_assembler import EvidenceAssembler
from app.services.evidence_calculations import EvidenceCalculator
from app.services.driver_decomposition import decompose_change
from app.services.campaign_impact import campaign_impact
from app.services.claim_checker import verify_answer
from app.schemas.decomposition import DecompositionResponse
from app.schemas.campaign_impact import CampaignImpactResponse
from app.schemas.verification import VerificationResponse

logger = logging.getLogger(__name__)


@dataclass
class ToolExecutionResult:
    """
    Standardized, provider-agnostic result wrapper for any typed tool execution.
    Contains status, output dictionary, evidence items, and error details.
    """
    success: bool
    tool_name: str
    output_data: Dict[str, Any] = field(default_factory=dict)
    evidence_items: List[EvidenceItem] = field(default_factory=list)
    raw_response: Any = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None


class RegisteredTool:
    """
    Typed definition for a single tool in the VERIDEX ToolRegistry.
    """
    def __init__(
        self,
        name: str,
        description: str,
        parameters_schema: Dict[str, Any],
        handler: Callable[[Session, Dict[str, Any], Optional[List[EvidenceItem]]], ToolExecutionResult]
    ):
        self.name = name
        self.description = description
        self.parameters_schema = parameters_schema
        self.handler = handler

    def to_definition(self) -> Dict[str, Any]:
        """
        Returns JSON-serializable tool definition schema suitable for LLM provider function declarations.
        """
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters_schema
        }


class ToolRegistry:
    """
    Centralized, lightweight typed-tool registry for VERIDEX decision intelligence capabilities.
    Encapsulates:
    - sql_query
    - driver_decomposition
    - campaign_impact
    - claim_verification
    """

    def __init__(self):
        self._tools: Dict[str, RegisteredTool] = {}
        self._register_default_tools()

    def register_tool(self, tool: RegisteredTool) -> None:
        self._tools[tool.name] = tool

    def get_tool(self, tool_name: str) -> Optional[RegisteredTool]:
        return self._tools.get(tool_name)

    def list_tools(self) -> List[RegisteredTool]:
        return list(self._tools.values())

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        return [tool.to_definition() for tool in self._tools.values()]

    def execute_tool(
        self,
        tool_name: str,
        db: Session,
        arguments: Dict[str, Any],
        context_evidence: Optional[List[EvidenceItem]] = None
    ) -> ToolExecutionResult:
        tool = self.get_tool(tool_name)
        if not tool:
            return ToolExecutionResult(
                success=False,
                tool_name=tool_name,
                error_type="UNSUPPORTED_TOOL",
                error_message=f"Unsupported tool requested: '{tool_name}'. Allowed tools: {list(self._tools.keys())}"
            )
        try:
            return tool.handler(db, arguments, context_evidence)
        except Exception as exc:
            logger.error("Error executing tool '%s': %s", tool_name, exc, exc_info=True)
            return ToolExecutionResult(
                success=False,
                tool_name=tool_name,
                error_type="TOOL_EXECUTION_ERROR",
                error_message=f"Execution error in tool '{tool_name}': {str(exc)}"
            )

    def _register_default_tools(self) -> None:
        # 1. SQL Query Tool
        sql_tool = RegisteredTool(
            name="sql_query",
            description="Executes a safe read-only SQL SELECT query against the PostgreSQL business database.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "sql": {"type": "string", "description": "The SQL SELECT query to execute."},
                    "max_rows": {"type": "integer", "description": "Maximum rows to return (default 100)."}
                },
                "required": ["sql"]
            },
            handler=_execute_sql_query_tool
        )
        self.register_tool(sql_tool)

        # 2. Driver Decomposition Tool
        decomp_tool = RegisteredTool(
            name="driver_decomposition",
            description="Decomposes revenue change between two time periods across dimensions (region, category, segment, customer) to identify primary variance drivers.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "metric": {"type": "string", "description": "Metric to decompose (default 'revenue')."},
                    "period_a": {
                        "type": "object",
                        "description": "Baseline period range.",
                        "properties": {
                            "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                            "end_date": {"type": "string", "description": "YYYY-MM-DD"}
                        },
                        "required": ["start_date", "end_date"]
                    },
                    "period_b": {
                        "type": "object",
                        "description": "Comparison period range.",
                        "properties": {
                            "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                            "end_date": {"type": "string", "description": "YYYY-MM-DD"}
                        },
                        "required": ["start_date", "end_date"]
                    },
                    "dimensions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of dimensions: ['region', 'category', 'segment', 'customer']."
                    },
                    "top_n": {"type": "integer", "description": "Top N driver limit (default 10)."}
                },
                "required": ["period_a", "period_b"]
            },
            handler=_execute_driver_decomposition_tool
        )
        self.register_tool(decomp_tool)

        # 3. Campaign Impact Tool
        campaign_tool = RegisteredTool(
            name="campaign_impact",
            description="Evaluates Difference-in-Differences (DiD) observational lift for a marketing campaign by comparing exposed vs control customer cohorts.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string", "description": "Identifier of campaign to evaluate (e.g. 'CMP-2025-Q3-SOUTH')."},
                    "min_sample_size": {"type": "integer", "description": "Minimum sample size per group (default 15)."}
                },
                "required": ["campaign_id"]
            },
            handler=_execute_campaign_impact_tool
        )
        self.register_tool(campaign_tool)

        # 4. Claim Verification Tool
        verification_tool = RegisteredTool(
            name="claim_verification",
            description="Verifies numerical claims in answer text against structured evidence items using relative error tolerance.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "llm_text": {"type": "string", "description": "Candidate answer text containing numerical claims to verify."},
                    "tolerance": {"type": "number", "description": "Comparison tolerance threshold (default 0.05)."}
                },
                "required": ["llm_text"]
            },
            handler=_execute_claim_verification_tool
        )
        self.register_tool(verification_tool)


# =====================================================================
# HANDLER IMPLEMENTATIONS
# =====================================================================

def _execute_sql_query_tool(
    db: Session,
    arguments: Dict[str, Any],
    context_evidence: Optional[List[EvidenceItem]] = None
) -> ToolExecutionResult:
    sql_val = arguments.get("sql")
    max_rows = arguments.get("max_rows", 100)

    if not isinstance(sql_val, str) or not sql_val.strip():
        return ToolExecutionResult(
            success=False,
            tool_name="sql_query",
            error_type="MALFORMED_ARGUMENT",
            error_message="Invalid argument: 'sql' must be a non-empty string."
        )

    sql_req = SQLQueryRequest(sql=sql_val.strip(), max_rows=max_rows)
    sql_res: SQLQueryResult = execute_read_only_sql(db, sql_req)

    evidence_items: List[EvidenceItem] = []
    if sql_res.success:
        assembler = EvidenceAssembler()
        calculator = EvidenceCalculator()
        fact_item = assembler.extract_fact_evidence(
            sql_res,
            description="SQL query execution output."
        )
        if fact_item:
            evidence_items.append(fact_item)

            if sql_res.data and len(sql_res.data) >= 2:
                first_row = sql_res.data[0]
                second_row = sql_res.data[1]
                num_cols = [col for col, val in first_row.items() if isinstance(val, (int, float))]
                if num_cols:
                    col_name = num_cols[0]
                    v1 = float(first_row[col_name])
                    v2 = float(second_row[col_name])
                    label1 = str(first_row.get("region") or first_row.get("product_name") or f"Row 1 ({col_name})")
                    label2 = str(second_row.get("region") or second_row.get("product_name") or f"Row 2 ({col_name})")

                    derived_item = calculator.percentage_change(
                        val_a=v1,
                        val_b=v2,
                        label_a=label1,
                        label_b=label2,
                        input_evidence_ids=[fact_item.evidence_id]
                    )
                    evidence_items.append(derived_item)

    out_dict = {
        "success": sql_res.success,
        "row_count": sql_res.row_count,
        "columns": sql_res.columns,
        "data": sql_res.data,
        "sql": sql_res.sql,
        "error_type": sql_res.error_type,
        "error_message": sql_res.error_message
    }

    return ToolExecutionResult(
        success=sql_res.success,
        tool_name="sql_query",
        output_data=out_dict,
        evidence_items=evidence_items,
        raw_response=sql_res,
        error_type=sql_res.error_type if not sql_res.success else None,
        error_message=sql_res.error_message if not sql_res.success else None
    )


def _execute_driver_decomposition_tool(
    db: Session,
    arguments: Dict[str, Any],
    context_evidence: Optional[List[EvidenceItem]] = None
) -> ToolExecutionResult:
    metric = arguments.get("metric", "revenue")
    period_a = arguments.get("period_a")
    period_b = arguments.get("period_b")
    dimensions = arguments.get("dimensions")
    top_n = arguments.get("top_n", 10)

    if not period_a or not period_b:
        return ToolExecutionResult(
            success=False,
            tool_name="driver_decomposition",
            error_type="MALFORMED_ARGUMENT",
            error_message="Missing required parameters: 'period_a' and 'period_b' are required."
        )

    resp: DecompositionResponse = decompose_change(
        db=db,
        metric=metric,
        period_a=period_a,
        period_b=period_b,
        dimensions=dimensions,
        top_n=top_n
    )

    out_dict = resp.model_dump() if hasattr(resp, "model_dump") else dict(resp)

    return ToolExecutionResult(
        success=resp.success,
        tool_name="driver_decomposition",
        output_data=out_dict,
        evidence_items=resp.evidence or [],
        raw_response=resp
    )


def _execute_campaign_impact_tool(
    db: Session,
    arguments: Dict[str, Any],
    context_evidence: Optional[List[EvidenceItem]] = None
) -> ToolExecutionResult:
    campaign_id = arguments.get("campaign_id")
    min_sample_size = arguments.get("min_sample_size", 15)

    if not campaign_id or not isinstance(campaign_id, str):
        return ToolExecutionResult(
            success=False,
            tool_name="campaign_impact",
            error_type="MALFORMED_ARGUMENT",
            error_message="Missing required parameter: 'campaign_id' must be a string."
        )

    resp: CampaignImpactResponse = campaign_impact(
        db=db,
        campaign_id=campaign_id,
        min_sample_size=min_sample_size
    )

    out_dict = resp.model_dump() if hasattr(resp, "model_dump") else dict(resp)

    return ToolExecutionResult(
        success=True,
        tool_name="campaign_impact",
        output_data=out_dict,
        evidence_items=resp.evidence or [],
        raw_response=resp
    )


def _execute_claim_verification_tool(
    db: Session,
    arguments: Dict[str, Any],
    context_evidence: Optional[List[EvidenceItem]] = None
) -> ToolExecutionResult:
    llm_text = arguments.get("llm_text")
    tolerance = arguments.get("tolerance", 0.05)

    if not llm_text or not isinstance(llm_text, str):
        return ToolExecutionResult(
            success=False,
            tool_name="claim_verification",
            error_type="MALFORMED_ARGUMENT",
            error_message="Missing required parameter: 'llm_text' must be a non-empty string."
        )

    evidence_to_use = context_evidence or []
    resp: VerificationResponse = verify_answer(
        llm_text=llm_text,
        evidence_list=evidence_to_use,
        tolerance=tolerance
    )

    out_dict = resp.model_dump() if hasattr(resp, "model_dump") else dict(resp)

    return ToolExecutionResult(
        success=True,
        tool_name="claim_verification",
        output_data=out_dict,
        evidence_items=[],
        raw_response=resp
    )
