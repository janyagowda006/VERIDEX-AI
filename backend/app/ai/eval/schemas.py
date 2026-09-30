from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from enum import Enum


class BenchmarkCategory(str, Enum):
    FACTUAL = "FACTUAL"
    METRIC = "METRIC"
    RANKING = "RANKING"
    DECISION = "DECISION"
    ROBUSTNESS = "ROBUSTNESS"
    INSUFFICIENT = "INSUFFICIENT"


class BenchmarkItem(BaseModel):
    """
    Structured benchmark test case for business decision intelligence evaluation.
    """
    id: str = Field(..., description="Unique benchmark case identifier (e.g. bench_01).")
    category: BenchmarkCategory = Field(..., description="Query classification category.")
    question: str = Field(..., description="Natural language business question.")
    expected_tables: List[str] = Field(default_factory=list, description="Database tables expected to be queried.")
    expected_columns: List[str] = Field(default_factory=list, description="Key columns expected in SQL query or result.")
    expected_evidence_types: List[str] = Field(default_factory=list, description="Evidence types expected (FACT, DERIVED_FACT, INFERENCE).")
    expected_metrics: List[str] = Field(default_factory=list, description="Key metric identifiers expected.")
    expected_decision_status: Optional[str] = Field(None, description="Expected robustness status (STABLE, SENSITIVE, INSUFFICIENT_EVIDENCE).")
    expected_recommendation: Optional[str] = Field(None, description="Keywords expected in recommendation action title.")
    evaluation_notes: Optional[str] = Field(None, description="Additional context or evaluation guidance.")


class CaseEvaluation(BaseModel):
    """
    Evaluation results for an individual benchmark question execution.
    """
    item_id: str
    category: BenchmarkCategory
    question: str
    success: bool
    execution_time_ms: float
    turns_used: int
    tool_calls_count: int
    sql_executed: Optional[str] = None
    sql_success: bool = False
    tables_accessed: List[str] = Field(default_factory=list)
    evidence_count: int = 0
    claims_count: int = 0
    unsupported_claims_count: int = 0
    groundedness_score: float = 0.0  # % of claims with valid evidence support (0.0 to 1.0)
    citation_precision: float = 0.0  # valid citations / total produced citations
    citation_recall: float = 0.0     # valid evidence items cited / total evidence items available
    decision_agreement: Optional[bool] = None  # None if non-decision query
    robustness_agreement: Optional[bool] = None
    error_message: Optional[str] = None


class BenchmarkReport(BaseModel):
    """
    Aggregated benchmark evaluation report across all dataset questions.
    """
    timestamp: str = Field(..., description="ISO 8601 evaluation timestamp.")
    benchmark_version: str = Field(default="1.0.0", description="Benchmark dataset version.")
    provider_name: str = Field(..., description="LLM provider name evaluated (mock or gemini).")
    total_cases: int
    successful_cases: int
    failed_cases: int
    sql_execution_success_rate: float = Field(..., description="Percentage of SQL queries executing without error.")
    groundedness_rate: float = Field(..., description="Average groundedness score across claims.")
    citation_precision: float = Field(..., description="Average citation precision.")
    citation_recall: float = Field(..., description="Average citation recall.")
    unsupported_claim_rate: float = Field(..., description="Percentage of claims lacking evidence support.")
    decision_agreement_rate: float = Field(..., description="Percentage of decision queries matching expected outcome.")
    robustness_agreement_rate: float = Field(..., description="Percentage of robustness status matches.")
    average_latency_ms: float = Field(..., description="Average investigation loop latency in milliseconds.")
    case_evaluations: List[CaseEvaluation] = Field(default_factory=list)
