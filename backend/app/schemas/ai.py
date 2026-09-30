from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from app.schemas.sql_tool import SQLQueryResult
from app.schemas.evidence import ClaimEvidence, EvidenceItem
from app.schemas.decision import DecisionAnalysis


class AskRequest(BaseModel):
    """
    Request payload for natural language decision intelligence queries.
    """
    question: str = Field(..., description="The business question in natural language.")
    max_turns: Optional[int] = Field(default=3, ge=1, le=5, description="Maximum orchestration reasoning turns.")
    investigation_id: Optional[str] = Field(default=None, description="Optional existing investigation ID to continue an ongoing multi-turn investigation.")


class ToolCallRecord(BaseModel):
    """
    Record of a tool invocation made during the investigation loop.
    """
    turn: int
    tool_name: str
    arguments: Dict[str, Any]
    result: SQLQueryResult


class AskResponse(BaseModel):
    """
    Structured response returned by the VERIDEX decision engine, preserving evidence, claims, and decision analysis.
    """
    success: bool
    question: str
    answer: str
    investigation_id: Optional[str] = Field(default=None, description="Associated persistent investigation ID.")
    claims: List[ClaimEvidence] = Field(default_factory=list, description="Claim-to-evidence mappings.")
    evidence: List[EvidenceItem] = Field(default_factory=list, description="Categorized evidence items (FACT, DERIVED_FACT, INFERENCE).")
    analysis: Optional[DecisionAnalysis] = Field(default=None, description="Deterministic decision analysis, recommendation, and robustness evaluation.")
    tool_calls: List[ToolCallRecord] = Field(default_factory=list, description="Tool execution history.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Execution metadata.")
    error: Optional[str] = None
