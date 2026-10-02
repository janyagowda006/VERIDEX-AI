from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
from app.schemas.ai import AskResponse


class InvestigationStatus(str, Enum):
    """
    Lifecycle status of an investigation execution.
    """
    IN_PROGRESS = "IN_PROGRESS"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"
    LIMIT_REACHED = "LIMIT_REACHED"


class InvestigationReviewStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    FLAGGED = "FLAGGED"


class ReviewStatus(str, Enum):
    """
    Human review status for an actionable recommendation.
    """
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    FLAGGED = "FLAGGED"


class ReviewDecision(str, Enum):
    """
    Permitted human review decision submissions.
    """
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    FLAGGED = "FLAGGED"


class InvestigationCreate(BaseModel):
    """
    Schema for creating a new persistent investigation.
    """
    question: str = Field(..., description="Business question in natural language.")
    max_turns: Optional[int] = Field(default=3, ge=1, le=5, description="Maximum orchestration turns.")


class InvestigationSummary(BaseModel):
    """
    Lightweight investigation summary schema for history listing and overview views.
    """
    investigation_id: str = Field(..., description="Unique investigation identifier.")
    question: str = Field(..., description="Business question in natural language.")
    status: str = Field(default="COMPLETED", description="Lifecycle status (IN_PROGRESS, COMPLETED, FAILED, REQUIRES_REVIEW).")
    created_at: Any = Field(..., description="UTC creation timestamp.")
    completed_at: Optional[Any] = Field(None, description="UTC completion timestamp.")
    execution_time_ms: Optional[float] = Field(None, description="Backend execution duration in milliseconds.")
    turns_used: int = Field(default=0, description="Total turns executed.")
    tool_calls_count: int = Field(default=0, description="Total tool calls executed.")
    evidence_count: int = Field(default=0, description="Total evidence items collected.")
    claims_count: int = Field(default=0, description="Total claims generated.")
    robustness_status: Optional[str] = Field(None, description="Robustness evaluation (STABLE, SENSITIVE, INSUFFICIENT_EVIDENCE).")
    review_status: str = Field(default="PENDING", description="Current human review state.")
    top_finding: Optional[str] = Field(default=None, description="Short summary or leading finding.")
    owner_id: Optional[str] = Field(None, description="Owner user identifier.")

    model_config = ConfigDict(from_attributes=True)

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("question must not be blank.")
        return v.strip()


class InvestigationReviewCreate(BaseModel):
    """
    Schema for submitting a Human-in-the-Loop review for an investigation.
    """
    review_status: InvestigationReviewStatus = Field(..., description="Review decision (APPROVED, REJECTED, FLAGGED).")
    reviewer_id: Optional[str] = Field(None, description="Identity of human reviewer (populated by server if omitted).")
    review_notes: Optional[str] = Field(None, max_length=2000, description="Optional reviewer notes or rationale (up to 2000 chars).")

    @field_validator("reviewer_id")
    @classmethod
    def validate_reviewer_id(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError("reviewer_id must be a string.")
        s = v.strip()
        if not s:
            raise ValueError("reviewer_id cannot be empty or whitespace only.")
        if len(s) > 64:
            raise ValueError("reviewer_id cannot exceed 64 characters.")
        return s


class InvestigationReviewRequest(BaseModel):
    """
    Request payload to record an executive decision approval or rejection.
    """
    status: ReviewDecision = Field(..., description="Decision approval state: APPROVED, REJECTED, or FLAGGED.")
    reviewer_notes: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Optional justification, business context, or operational notes."
    )

    @field_validator("reviewer_notes")
    @classmethod
    def sanitize_notes(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            stripped = v.strip()
            return stripped if stripped else None
        return None


class InvestigationReviewResponse(BaseModel):
    """
    Schema for representing a persisted Human-in-the-Loop review record.
    """
    review_id: str = Field(..., description="Unique review identifier.")
    investigation_id: str = Field(..., description="Associated investigation identifier.")
    review_status: str = Field(..., description="Review decision (APPROVED, REJECTED, FLAGGED).")
    reviewer_id: str = Field(..., description="Identifier of human reviewer.")
    review_notes: Optional[str] = Field(None, description="Optional reviewer notes.")
    reviewed_at: Any = Field(..., description="UTC timestamp of review submission.")

    model_config = ConfigDict(from_attributes=True)


class InvestigationTurnResponse(BaseModel):
    """
    Schema for representing a persistent multi-turn conversation turn.
    """
    turn_id: str = Field(..., description="Unique turn identifier.")
    investigation_id: str = Field(..., description="Associated investigation identifier.")
    turn_number: int = Field(..., description="1-indexed sequential turn number.")
    user_question: str = Field(..., description="User question for this turn.")
    execution_time_ms: Optional[float] = Field(None, description="Backend execution duration in milliseconds.")
    result_json: Optional[str] = Field(None, description="Serialized AskResponse JSON result for this turn.")
    created_at: Any = Field(..., description="UTC timestamp of turn creation.")

    model_config = ConfigDict(from_attributes=True)


class InvestigationAuditLogEntry(BaseModel):
    """
    Audit log entry representing a lifecycle or review event.
    """
    audit_id: str = Field(..., description="Unique audit event identifier.")
    investigation_id: str = Field(..., description="Associated investigation ID.")
    event_type: str = Field(..., description="Event type descriptor.")
    review_status: Optional[str] = Field(default=None, description="Associated review status.")
    reviewer_notes: Optional[str] = Field(default=None, description="Notes captured at event time.")
    created_at: Any = Field(..., description="ISO-8601 UTC event timestamp.")
    event_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Metadata associated with event.")

    model_config = ConfigDict(from_attributes=True)


class InvestigationDetail(InvestigationSummary):
    """
    Detailed investigation schema including full AskResponse JSON payload, error context,
    Human-in-the-Loop review history, and conversation turn history.
    """
    result_json: Optional[str] = Field(None, description="Serialized AskResponse JSON result.")
    error_message: Optional[str] = Field(None, description="Error message if status is FAILED.")
    latest_review: Optional[InvestigationReviewResponse] = Field(None, description="Most recent human review record if present.")
    review_count: int = Field(default=0, description="Total number of human reviews submitted.")
    turns: List[InvestigationTurnResponse] = Field(default_factory=list, description="Ordered conversation turn records.")

    model_config = ConfigDict(from_attributes=True)


class InvestigationDetailResponse(BaseModel):
    """
    Complete investigation detail response combining persistent metadata with the reconstructed AskResponse.
    Preserves 100% compatibility with the existing AskResponse schema.
    """
    investigation_id: str = Field(..., description="Unique investigation identifier (UUID).")
    question: str = Field(..., min_length=1, description="Original business question.")
    status: str = Field(..., description="Execution status.")
    review_status: str = Field(..., description="Human review status.")
    created_at: Any = Field(..., description="ISO-8601 UTC creation timestamp.")
    completed_at: Optional[Any] = Field(default=None, description="ISO-8601 UTC completion timestamp.")
    response: AskResponse = Field(..., description="Reconstructed complete AskResponse.")
    reviewer_notes: Optional[str] = Field(default=None, description="Latest human review notes.")
    audit_trail: List[InvestigationAuditLogEntry] = Field(default_factory=list, description="Chronological audit events.")

    model_config = ConfigDict(from_attributes=True)

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("question must not be blank.")
        return v.strip()


class InvestigationReassessRequest(BaseModel):
    """
    Schema for requesting dynamic robustness re-assessment on an existing investigation.
    """
    scenario_shift_pct: float = Field(
        default=10.0,
        gt=0.0,
        le=100.0,
        description="Percentage shift for metric sensitivity stress testing (e.g. 5, 10, 15, 20, 25, 30)."
    )


class InvestigationReassessResponse(BaseModel):
    """
    Schema representing the deterministic robustness re-assessment result.
    """
    investigation_id: str = Field(..., description="Target investigation identifier.")
    question: str = Field(..., description="Original business question.")
    original_scenario_shift_pct: float = Field(default=10.0, description="Original baseline scenario shift percentage.")
    requested_scenario_shift_pct: float = Field(..., description="Requested scenario shift percentage.")
    baseline_top_candidate: Optional[str] = Field(None, description="Baseline top candidate name/region if available.")
    baseline_metric_name: Optional[str] = Field(None, description="Primary metric column evaluated.")
    robustness_check: Dict[str, Any] = Field(..., description="Reassessed deterministic RobustnessCheck schema object.")
    reassessed_at: Any = Field(..., description="UTC timestamp of re-assessment execution.")

    model_config = ConfigDict(from_attributes=True)


class InvestigationMetricsSummary(BaseModel):
    """
    Schema for global investigation metrics summary analytics.
    """
    total_investigations: int = Field(default=0, description="Total persisted investigation count.")
    total_reviews: int = Field(default=0, description="Total persisted human review count.")
    status_counts: Dict[str, int] = Field(..., description="Investigation count grouped by status.")
    review_counts: Dict[str, int] = Field(..., description="Review count grouped by review_status.")
    robustness_counts: Dict[str, int] = Field(..., description="Investigation count grouped by robustness_status.")
    average_execution_time_ms: Optional[float] = Field(None, description="Average execution duration in milliseconds.")

    model_config = ConfigDict(from_attributes=True)
