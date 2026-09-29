from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from app.schemas.sql_tool import SQLQueryResult
from app.schemas.evidence import ClaimEvidence, EvidenceItem


class AskRequest(BaseModel):
    """
    Request payload for natural language decision intelligence queries.
    """
    question: str = Field(..., description="The business question in natural language.")
    max_turns: Optional[int] = Field(default=3, ge=1, le=5, description="Maximum orchestration reasoning turns.")


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
    Structured response returned by the VERIDEX decision engine, preserving evidence & claims.
    """
    success: bool
    question: str
    answer: str
    claims: List[ClaimEvidence] = Field(default_factory=list, description="Claim-to-evidence mappings.")
    evidence: List[EvidenceItem] = Field(default_factory=list, description="Categorized evidence items (FACT, DERIVED_FACT, INFERENCE).")
    tool_calls: List[ToolCallRecord] = Field(default_factory=list, description="Tool execution history.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Execution metadata.")
    error: Optional[str] = None
