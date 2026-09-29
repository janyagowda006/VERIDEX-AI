from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


class DecisionCriterion(BaseModel):
    """
    Deterministic criterion evaluation for business decisions.
    """
    criterion_id: str = Field(..., description="Unique criterion identifier (e.g. crit_1).")
    criterion_name: str = Field(..., description="Name of business criterion (e.g., Minimum Revenue Threshold).")
    metric_name: str = Field(..., description="Metric evaluated (e.g. gross_revenue).")
    operator: str = Field(..., description="Comparison operator (>=, <=, ==, !=, >, <, top_n).")
    threshold_value: Any = Field(..., description="Target threshold value.")
    actual_value: Any = Field(..., description="Observed actual metric value.")
    is_met: bool = Field(..., description="Whether criterion condition was satisfied.")
    explanation: str = Field(..., description="Human-readable criterion evaluation summary.")


class Recommendation(BaseModel):
    """
    Traceable action recommendation backed by verified evidence and robustness evaluation.
    """
    recommendation_id: str = Field(..., description="Unique recommendation identifier (e.g. rec_1).")
    action_title: str = Field(..., description="Short actionable recommendation title.")
    rationale: str = Field(..., description="Evidence-backed business rationale.")
    supporting_evidence_ids: List[str] = Field(default_factory=list, description="Supporting Fact/Derived evidence IDs.")
    relevant_claim_ids: List[str] = Field(default_factory=list, description="IDs of related AskResponse claims.")
    limitations: List[str] = Field(default_factory=list, description="Known limitations or boundaries.")
    robustness_status: str = Field(..., description="Robustness classification: STABLE, SENSITIVE, or INSUFFICIENT_EVIDENCE.")


class RobustnessScenario(BaseModel):
    """
    Evaluates finding stability under alternate scenario assumptions.
    """
    scenario_name: str = Field(..., description="Scenario identifier (e.g., baseline_completed, alternate_all_orders).")
    assumptions: Dict[str, Any] = Field(default_factory=dict, description="Scenario assumptions and parameters.")
    result_summary: Dict[str, Any] = Field(default_factory=dict, description="Observed metric results under scenario.")
    is_recommendation_changed: bool = Field(default=False, description="Whether alternate scenario alters baseline recommendation/ranking.")


class RobustnessCheck(BaseModel):
    """
    Deterministic robustness assessment testing finding sensitivity across scenarios.
    """
    check_id: str = Field(..., description="Unique robustness check identifier (e.g. rob_1).")
    status: str = Field(..., description="Classification: STABLE, SENSITIVE, or INSUFFICIENT_EVIDENCE.")
    baseline_scenario: RobustnessScenario = Field(..., description="Baseline scenario results.")
    alternate_scenarios: List[RobustnessScenario] = Field(default_factory=list, description="Alternate scenario test results.")
    explanation: str = Field(..., description="Detailed explanation of sensitivity finding.")
    supporting_evidence_ids: List[str] = Field(default_factory=list, description="Evidence IDs evaluated.")


class DecisionAnalysis(BaseModel):
    """
    Complete Decision Intelligence Analysis object combining criteria, rankings, recommendations, and robustness.
    """
    analysis_id: str = Field(..., description="Unique analysis identifier (e.g. anal_1).")
    summary: str = Field(..., description="High-level decision intelligence summary.")
    criteria_evaluated: List[DecisionCriterion] = Field(default_factory=list, description="Evaluated decision criteria.")
    rankings: List[Dict[str, Any]] = Field(default_factory=list, description="Deterministic candidate rankings.")
    recommendation: Optional[Recommendation] = Field(default=None, description="Actionable evidence-backed recommendation.")
    robustness: Optional[RobustnessCheck] = Field(default=None, description="Deterministic sensitivity & robustness assessment.")
