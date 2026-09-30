from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator
from app.schemas.ai import AskResponse


class InvestigationStatus(str, Enum):
    """
    Lifecycle status of an investigation execution.
    """
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RUNNING = "RUNNING"
    LIMIT_REACHED = "LIMIT_REACHED"


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


class InvestigationSummary(BaseModel):
    """
    Lightweight summary representation for investigation history lists and dashboards.
    """
    investigation_id: str = Field(..., description="Unique investigation identifier (UUID).")
    question: str = Field(..., min_length=1, description="Original business question.")
    created_at: str = Field(..., description="ISO-8601 UTC creation timestamp.")
    completed_at: Optional[str] = Field(default=None, description="ISO-8601 UTC completion timestamp.")
    status: str = Field(default=InvestigationStatus.COMPLETED.value, description="Execution status.")
    robustness_status: Optional[str] = Field(default=None, description="STABLE, SENSITIVE, or INSUFFICIENT_EVIDENCE.")
    review_status: str = Field(default=ReviewStatus.PENDING.value, description="Current human review state.")
    top_finding: Optional[str] = Field(default=None, description="Short summary or leading finding.")

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("question must not be blank.")
        return v.strip()


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


class InvestigationAuditLogEntry(BaseModel):
    """
    Audit log entry representing a lifecycle or review event.
    """
    audit_id: str = Field(..., description="Unique audit event identifier.")
    investigation_id: str = Field(..., description="Associated investigation ID.")
    event_type: str = Field(..., description="Event type descriptor.")
    review_status: Optional[str] = Field(default=None, description="Associated review status.")
    reviewer_notes: Optional[str] = Field(default=None, description="Notes captured at event time.")
    created_at: str = Field(..., description="ISO-8601 UTC event timestamp.")
    event_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Metadata associated with event.")


class InvestigationDetailResponse(BaseModel):
    """
    Complete investigation detail response combining persistent metadata with the reconstructed AskResponse.
    Preserves 100% compatibility with the existing AskResponse schema.
    """
    investigation_id: str = Field(..., description="Unique investigation identifier (UUID).")
    question: str = Field(..., min_length=1, description="Original business question.")
    status: str = Field(..., description="Execution status.")
    review_status: str = Field(..., description="Human review status.")
    created_at: str = Field(..., description="ISO-8601 UTC creation timestamp.")
    completed_at: Optional[str] = Field(default=None, description="ISO-8601 UTC completion timestamp.")
    response: AskResponse = Field(..., description="Reconstructed complete AskResponse.")
    reviewer_notes: Optional[str] = Field(default=None, description="Latest human review notes.")
    audit_trail: List[InvestigationAuditLogEntry] = Field(default_factory=list, description="Chronological audit events.")

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("question must not be blank.")
        return v.strip()
