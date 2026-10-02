from typing import List, Dict, Any, Optional, Union, Literal
from pydantic import BaseModel, Field
from app.schemas.evidence import EvidenceItem


class VerificationClaim(BaseModel):
    """
    Structured numerical claim extracted from LLM text and evaluated against evidence.
    """
    claim_text: str = Field(..., description="Original raw text span containing the numerical claim.")
    sentence: str = Field(..., description="Full sentence containing the claim.")
    normalized_value: Union[float, int, str] = Field(..., description="Deterministic normalized numeric or date value.")
    unit: str = Field(..., description="Semantic unit: 'currency', 'percent', 'count', 'date', or 'number'.")
    status: Literal["VERIFIED", "UNVERIFIED"] = Field(..., description="Verification status of the individual claim.")
    matching_evidence_ids: List[str] = Field(
        default_factory=list,
        description="IDs of supporting EvidenceItem objects that deterministically justify the claim."
    )
    reason: Optional[str] = Field(
        default=None,
        description="Deterministic explanation of verification success or rejection reason."
    )
    verified: bool = Field(
        default=False,
        description="Boolean verification flag (True if status=='VERIFIED')."
    )
    evidence_type: Optional[str] = Field(
        default=None,
        description="Primary supporting evidence type: FACT or DERIVED_FACT."
    )
    source: Optional[str] = Field(
        default=None,
        description="Source tool or database provenance (e.g. SQL, calculation)."
    )
    query: Optional[str] = Field(
        default=None,
        description="Executed SQL statement if supported by FACT evidence."
    )
    calculation: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Deterministic formula provenance if supported by DERIVED_FACT evidence."
    )
    text: Optional[str] = Field(
        default=None,
        description="UI-ready full sentence or assertion text."
    )
    claim: Optional[str] = Field(
        default=None,
        description="UI-ready claim span."
    )
    evidence_ids: List[str] = Field(
        default_factory=list,
        description="UI-ready list of supporting evidence IDs."
    )


class VerificationRequest(BaseModel):
    """
    Request payload for deterministic numerical answer verification.
    """
    llm_text: str = Field(..., description="LLM-generated answer text to verify.")
    evidence_list: List[EvidenceItem] = Field(..., description="List of structured EvidenceItem objects to verify against.")
    tolerance: Optional[float] = Field(
        default=0.05,
        ge=0.0,
        le=0.10,
        description="Explicit numerical comparison tolerance for rounded values (maximum allowable: 0.10, default: 0.05)."
    )


class VerificationResponse(BaseModel):
    """
    Deterministic numerical answer verification response.
    Adheres to the core principle: 'AI for reasoning, code for correctness.'
    """
    status: Literal["PASS", "FAIL"] = Field(
        ...,
        description="Overall verification status: 'PASS' if all detected numerical claims are verified, 'FAIL' otherwise."
    )
    verified: List[VerificationClaim] = Field(
        default_factory=list,
        description="List of verified numerical claims matching structured evidence."
    )
    unverified: List[VerificationClaim] = Field(
        default_factory=list,
        description="List of unverified numerical claims missing compatible evidence support."
    )
    total_claims: int = Field(default=0, description="Total count of relevant numerical claims detected.")
    verified_count: int = Field(default=0, description="Count of successfully verified claims.")
    unverified_count: int = Field(default=0, description="Count of unverified/unsupported claims.")
    summary: str = Field(..., description="Concise summary of verification findings.")
    disclaimer: str = Field(
        default="Deterministic numerical verification against provided evidence. Qualitative interpretations and non-numerical assertions are not evaluated.",
        description="Scope limitation disclaimer."
    )
    execution_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Execution metadata including timing and tolerance settings."
    )
