from datetime import date, datetime
from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field, model_validator
from app.schemas.evidence import EvidenceItem


class PeriodRange(BaseModel):
    """
    Validated date range for a comparison period.
    Supports ISO date strings, dicts, lists/tuples, or date objects.
    """
    start_date: str = Field(..., description="Start date (YYYY-MM-DD).")
    end_date: str = Field(..., description="End date (YYYY-MM-DD).")

    @model_validator(mode="before")
    @classmethod
    def parse_period(cls, data: Any) -> Any:
        if isinstance(data, (list, tuple)) and len(data) == 2:
            return {"start_date": str(data[0]), "end_date": str(data[1])}
        if isinstance(data, str):
            # Parse 'YYYY-MM-DD:YYYY-MM-DD' or 'YYYY-MM-DD to YYYY-MM-DD'
            cleaned = data.replace(" to ", ":").replace("/", "-")
            if ":" in cleaned:
                parts = cleaned.split(":")
                return {"start_date": parts[0].strip(), "end_date": parts[1].strip()}
        if isinstance(data, dict):
            s = data.get("start_date") or data.get("start")
            e = data.get("end_date") or data.get("end")
            if s and e:
                return {"start_date": str(s), "end_date": str(e)}
        return data

    @model_validator(mode="after")
    def validate_dates(self) -> "PeriodRange":
        try:
            sd = datetime.strptime(self.start_date, "%Y-%m-%d").date()
            ed = datetime.strptime(self.end_date, "%Y-%m-%d").date()
        except ValueError as err:
            raise ValueError(f"Invalid date format in PeriodRange (must be YYYY-MM-DD): {err}")
        if sd > ed:
            raise ValueError(f"start_date ({self.start_date}) cannot be after end_date ({self.end_date}).")
        return self


class DriverItem(BaseModel):
    """
    Single driver contribution within a dimension.
    """
    label: str = Field(..., description="Group label (e.g. region name, category, customer).")
    dimension: str = Field(..., description="Dimension name (e.g. region, category, segment, customer).")
    revenue_a: float = Field(..., description="Revenue in Period A.")
    revenue_b: float = Field(..., description="Revenue in Period B.")
    delta_amount: float = Field(..., description="Absolute change: revenue_b - revenue_a.")
    percent_of_total_change: float = Field(..., description="(delta_amount / total_change) * 100. 0.0 if total_change is 0.")
    percent_change_within_group: Optional[float] = Field(
        default=None,
        description="Percentage change within this group: ((rev_b - rev_a) / rev_a) * 100. Safe against zero baseline."
    )
    status: str = Field(..., description="Driver status: 'normal', 'new' (exists only in B), or 'lost' (exists only in A).")


class WaterfallItem(BaseModel):
    """
    Chart-ready item for waterfall visualization.
    """
    label: str = Field(..., description="Driver or milestone label.")
    value: float = Field(..., description="Incremental delta value (or baseline value for start).")
    cumulative: float = Field(..., description="Running cumulative total up to this item.")


class DimensionDecomposition(BaseModel):
    """
    Decomposition results along a single dimension.
    """
    dimension: str = Field(..., description="Dimension name.")
    drivers: List[DriverItem] = Field(default_factory=list, description="List of drivers sorted by contribution.")
    sum_driver_deltas: float = Field(..., description="Sum of all driver delta amounts.")
    reconciled: bool = Field(..., description="True if sum(driver_deltas) == total_change within tolerance.")
    waterfall: List[WaterfallItem] = Field(default_factory=list, description="Waterfall chart series for this dimension.")


class DecompositionRequest(BaseModel):
    """
    Request model for POST /tools/decompose.
    """
    metric: str = Field(default="revenue", description="Metric to decompose. Supported: 'revenue'.")
    period_a: Union[PeriodRange, Dict[str, Any], List[str]] = Field(
        ...,
        description="First comparison period (start_date, end_date)."
    )
    period_b: Union[PeriodRange, Dict[str, Any], List[str]] = Field(
        ...,
        description="Second comparison period (start_date, end_date)."
    )
    dimensions: Optional[List[str]] = Field(
        default=None,
        description="Dimensions to decompose by. Allowed: 'region', 'category', 'segment', 'customer'."
    )
    top_n: Optional[int] = Field(
        default=10,
        ge=1,
        le=100,
        description="Top N items for high-cardinality dimensions (e.g. customer). Remaining are grouped into 'Other'."
    )
    include_baseline: Optional[bool] = Field(
        default=False,
        description="If True, includes starting baseline and ending total in top-level waterfall array."
    )


class DecompositionResponse(BaseModel):
    """
    Structured, authoritative response for driver decomposition.
    """
    success: bool = Field(default=True, description="Execution status.")
    metric: str = Field(..., description="Analyzed metric name.")
    period_a: Dict[str, str] = Field(..., description="Period A date bounds.")
    period_b: Dict[str, str] = Field(..., description="Period B date bounds.")
    total_revenue_a: float = Field(..., description="Total verified revenue in Period A.")
    total_revenue_b: float = Field(..., description="Total verified revenue in Period B.")
    total_change: float = Field(..., description="Total delta: total_revenue_b - total_revenue_a.")
    percent_change: Optional[float] = Field(default=None, description="Total overall percentage change.")
    dimensions: List[str] = Field(default_factory=list, description="Dimensions evaluated.")
    primary_dimension: str = Field(..., description="Primary dimension used for top-level waterfall.")
    breakdowns: Dict[str, DimensionDecomposition] = Field(
        default_factory=dict,
        description="Hierarchical breakdown mapped by dimension name."
    )
    waterfall: List[WaterfallItem] = Field(
        default_factory=list,
        description="Chart-ready waterfall JSON array for the primary dimension."
    )
    revenue_bridge: List[WaterfallItem] = Field(
        default_factory=list,
        description="Complete bridge waterfall starting with Period A baseline and ending at Period B total."
    )
    evidence: List[EvidenceItem] = Field(
        default_factory=list,
        description="DERIVED_FACT evidence items verifying every mathematical calculation."
    )
    assumptions: List[str] = Field(
        default_factory=list,
        description="Explicit analytical assumptions and boundary filters applied."
    )
    reconciliation_tolerance: float = Field(
        default=0.01,
        description="Floating-point tolerance used for the sum(driver_deltas) == total_change invariant."
    )
    execution_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Execution timing and row statistics."
    )
