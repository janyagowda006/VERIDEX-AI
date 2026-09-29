from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from app.schemas.sql_tool import SQLQueryResult


class EvidenceType(str, Enum):
    """
    Taxonomy for evidence and claims in VERIDEX.
    - FACT: Directly supported by returned database evidence.
    - DERIVED_FACT: Deterministically calculated from verified evidence.
    - INFERENCE: Qualitative LLM interpretation beyond directly observed values.
    """
    FACT = "FACT"
    DERIVED_FACT = "DERIVED_FACT"
    INFERENCE = "INFERENCE"


class EvidenceSource(BaseModel):
    """
    Preserves exact provenance of database query execution.
    """
    source_type: str = Field(default="sql_query", description="Source tool type.")
    query_hash: str = Field(..., description="SHA-256 hash of the executed SQL query.")
    sql: str = Field(..., description="Exact executed SQL SELECT statement.")
    timestamp: str = Field(..., description="ISO-8601 UTC timestamp of execution.")
    columns: List[str] = Field(default_factory=list, description="Column names returned.")
    relevant_rows: List[Dict[str, Any]] = Field(default_factory=list, description="Sample or relevant returned rows.")
    execution_metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata including execution_time_ms, row_count, truncated.")


class DerivedFactCalculation(BaseModel):
    """
    Preserves formula, input values, input evidence IDs, and deterministic output.
    """
    formula_name: str = Field(..., description="Name of calculation (e.g. percentage_change, difference, ratio, share_of_total).")
    formula: str = Field(..., description="Human-readable mathematical expression.")
    inputs: Dict[str, Any] = Field(default_factory=dict, description="Input values used in calculation.")
    output: Any = Field(..., description="Deterministic output result.")
    input_evidence_ids: List[str] = Field(default_factory=list, description="Evidence IDs of inputs used.")


class EvidenceItem(BaseModel):
    """
    Single structured evidence item with provenance and limitations.
    """
    evidence_id: str = Field(..., description="Unique evidence identifier (e.g., ev_fact_1).")
    evidence_type: EvidenceType = Field(..., description="Classification: FACT, DERIVED_FACT, or INFERENCE.")
    description: str = Field(..., description="Human-readable description of evidence.")
    source: Optional[EvidenceSource] = Field(default=None, description="Database provenance for FACT or DERIVED_FACT.")
    calculation: Optional[DerivedFactCalculation] = Field(default=None, description="Calculation provenance for DERIVED_FACT.")
    limitations: List[str] = Field(default_factory=list, description="Known evidence limitations (e.g. truncated rows, null values).")


class ClaimEvidence(BaseModel):
    """
    Maps an individual business claim in the final answer to its supporting evidence IDs.
    """
    claim_id: str = Field(..., description="Unique claim identifier (e.g., claim_1).")
    claim_text: str = Field(..., description="The claim assertion text.")
    evidence_ids: List[str] = Field(default_factory=list, description="IDs of supporting EvidenceItem objects.")
    evidence_type: EvidenceType = Field(..., description="Claim evidence classification.")
    is_supported: bool = Field(default=True, description="Whether claim has valid supporting evidence.")
