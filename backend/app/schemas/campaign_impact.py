from datetime import date
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from app.schemas.evidence import EvidenceItem


class CampaignImpactRequest(BaseModel):
    """
    Request payload for deterministic Difference-in-Differences campaign impact analysis.
    """
    campaign_id: str = Field(..., description="Unique identifier of the campaign (e.g. 'CMP-2025-Q3-SOUTH').")
    min_sample_size: Optional[int] = Field(
        default=15,
        ge=1,
        description="Minimum customer sample size threshold per group for substantive statistical inference (default: 15)."
    )


class CampaignImpactResponse(BaseModel):
    """
    Deterministic Difference-in-Differences observational campaign impact response.
    Adheres strictly to the VERIDEX principle: 'AI for reasoning, code for correctness.'
    All numerical outputs and inferences are computed deterministically in code.
    """
    campaign_id: str = Field(..., description="Identifier of evaluated campaign.")
    campaign_name: Optional[str] = Field(default=None, description="Descriptive campaign name.")
    target_region: Optional[str] = Field(default=None, description="Target geographical region.")
    
    # Customer counts
    exposed_n: int = Field(..., description="Number of unique qualifying customers in exposed cohort.")
    control_n: int = Field(..., description="Number of unique qualifying customers in control cohort.")
    
    # Customer-level averages
    exposed_before: float = Field(..., description="Average revenue per customer in exposed cohort during before window.")
    exposed_after: float = Field(..., description="Average revenue per customer in exposed cohort during after window.")
    control_before: float = Field(..., description="Average revenue per customer in control cohort during before window.")
    control_after: float = Field(..., description="Average revenue per customer in control cohort during after window.")
    
    # Changes
    exposed_change: float = Field(..., description="Absolute change in exposed average revenue: exposed_after - exposed_before.")
    control_change: float = Field(..., description="Absolute change in control average revenue: control_after - control_before.")
    
    # Difference-in-Differences
    did: float = Field(..., description="Difference-in-Differences estimate: exposed_change - control_change.")
    control_standard_error: Optional[float] = Field(
        default=None,
        description="Standard error of the control group mean difference computed from customer-level observations."
    )
    
    # Status & Inference
    status: str = Field(
        ...,
        description="Execution status: 'SUCCESS' or 'INSUFFICIENT_DATA' (if either group has < min_sample_size customers)."
    )
    inference: str = Field(
        ...,
        description="Deterministic observational inference: 'Supported by evidence', 'Weak support', or 'Not supported'."
    )
    
    # Mandatory disclaimer
    disclaimer: str = Field(
        default="Observational evidence; causation not proven.",
        description="Mandatory observational evidence disclaimer."
    )
    
    # Robustness research checks
    what_would_change_my_mind: List[str] = Field(
        ...,
        description="Deterministic research validation checks required before making causal or policy decisions."
    )
    
    # Lineage & Traceability
    time_windows: Optional[Dict[str, Dict[str, str]]] = Field(
        default=None,
        description="Date ranges evaluated for before, exposure, and after windows."
    )
    evidence: List[EvidenceItem] = Field(
        default_factory=list,
        description="Deterministic DERIVED_FACT evidence items tracing all group averages, changes, and DiD."
    )
    assumptions: List[str] = Field(
        default_factory=list,
        description="Documented analytical assumptions and cohort definitions."
    )
    execution_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Technical execution metadata (runtime, query counts, timestamps)."
    )
