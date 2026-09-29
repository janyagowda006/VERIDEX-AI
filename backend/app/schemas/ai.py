from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from app.schemas.sql_tool import SQLQueryResult


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
    Structured response returned by the VERIDEX decision engine.
    """
    success: bool
    question: str
    answer: str
    tool_calls: List[ToolCallRecord] = []
    metadata: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
