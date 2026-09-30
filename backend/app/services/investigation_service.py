import uuid
import json
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.models.investigation import Investigation, InvestigationReview, utcnow
from app.schemas.investigation import (
    InvestigationStatus,
    InvestigationSummary,
    InvestigationDetail,
    InvestigationReviewCreate,
    InvestigationReviewStatus,
    InvestigationMetricsSummary
)
from app.schemas.ai import AskResponse
from app.services.robustness import ROBUSTNESS_STATUS_SENSITIVE


def _sanitize_error_text(error_msg: str) -> str:
    """
    Sanitizes sensitive credential patterns (API keys, bearer tokens) from error strings.
    """
    if not error_msg:
        return ""
    cleaned = re.sub(r'api_key=[^&\s"\']+', 'api_key=***', error_msg, flags=re.IGNORECASE)
    cleaned = re.sub(r'bearer\s+[a-zA-Z0-9_\-\.]+', 'Bearer ***', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'key=[a-zA-Z0-9_\-\.]+', 'key=***', cleaned, flags=re.IGNORECASE)
    return cleaned


class InvestigationService:
    """
    Persistence service layer managing database transactions for Investigation models.
    Connects investigation orchestration to durable database storage.
    """

    @staticmethod
    def generate_investigation_id() -> str:
        """Generates a unique investigation identifier with 'inv_' prefix."""
        return f"inv_{uuid.uuid4().hex[:12]}"

    @classmethod
    def create_investigation(
        cls,
        db: Session,
        question: str,
        investigation_id: Optional[str] = None
    ) -> Investigation:
        """
        Creates and persists a new Investigation record in IN_PROGRESS state.
        """
        inv_id = investigation_id or cls.generate_investigation_id()
        investigation = Investigation(
            investigation_id=inv_id,
            question=question,
            status=InvestigationStatus.IN_PROGRESS.value,
            created_at=utcnow()
        )
        try:
            db.add(investigation)
            db.commit()
            db.refresh(investigation)
            return investigation
        except Exception:
            db.rollback()
            raise

    @classmethod
    def update_investigation_success(
        cls,
        db: Session,
        investigation_id: str,
        response: AskResponse,
        execution_time_ms: float
    ) -> Optional[Investigation]:
        """
        Updates an existing Investigation record after successful investigation completion.
        Maps robustness status (SENSITIVE -> REQUIRES_REVIEW, STABLE/INSUFFICIENT -> COMPLETED).
        """
        investigation = db.query(Investigation).filter(Investigation.investigation_id == investigation_id).first()
        if not investigation:
            return None

        # Determine robustness status and lifecycle status
        robustness_status_str = None
        target_status = InvestigationStatus.COMPLETED.value

        if response.analysis and response.analysis.robustness:
            robustness_status_str = response.analysis.robustness.status
        elif response.metadata and "robustness_status" in response.metadata:
            robustness_status_str = str(response.metadata["robustness_status"])

        if robustness_status_str and robustness_status_str.upper() == ROBUSTNESS_STATUS_SENSITIVE.upper():
            target_status = InvestigationStatus.REQUIRES_REVIEW.value

        # Serialize AskResponse to JSON
        result_json_str = response.model_dump_json() if hasattr(response, "model_dump_json") else json.dumps(response.model_dump(), default=str)

        investigation.status = target_status
        investigation.completed_at = utcnow()
        investigation.execution_time_ms = round(execution_time_ms, 2)
        investigation.turns_used = response.metadata.get("total_turns", 1) if response.metadata else 1
        investigation.tool_calls_count = len(response.tool_calls) if response.tool_calls else 0
        investigation.evidence_count = len(response.evidence) if response.evidence else 0
        investigation.claims_count = len(response.claims) if response.claims else 0
        investigation.robustness_status = robustness_status_str
        investigation.result_json = result_json_str
        investigation.error_message = None

        try:
            db.commit()
            db.refresh(investigation)
            return investigation
        except Exception:
            db.rollback()
            raise

    @classmethod
    def update_investigation_failure(
        cls,
        db: Session,
        investigation_id: str,
        error_message: str,
        execution_time_ms: Optional[float] = None
    ) -> Optional[Investigation]:
        """
        Updates an Investigation record to FAILED status with sanitized error details.
        """
        investigation = db.query(Investigation).filter(Investigation.investigation_id == investigation_id).first()
        if not investigation:
            return None

        sanitized_error = _sanitize_error_text(error_message)

        investigation.status = InvestigationStatus.FAILED.value
        investigation.completed_at = utcnow()
        if execution_time_ms is not None:
            investigation.execution_time_ms = round(execution_time_ms, 2)
        investigation.error_message = sanitized_error

        try:
            db.commit()
            db.refresh(investigation)
            return investigation
        except Exception:
            db.rollback()
            raise

    @classmethod
    def list_investigations(
        cls,
        db: Session,
        limit: int = 20,
        offset: int = 0
    ) -> List[Investigation]:
        """
        Retrieves lightweight Investigation summary records ordered by created_at DESC.
        """
        return (
            db.query(Investigation)
            .order_by(desc(Investigation.created_at))
            .offset(offset)
            .limit(limit)
            .all()
        )

    @classmethod
    def get_investigation_by_id(
        cls,
        db: Session,
        investigation_id: str
    ) -> Optional[Investigation]:
        """
        Retrieves a specific Investigation record by investigation_id.
        """
        return db.query(Investigation).filter(Investigation.investigation_id == investigation_id).first()

    @classmethod
    def reassess_investigation(
        cls,
        db: Session,
        investigation_id: str,
        scenario_shift_pct: float = 10.0
    ) -> InvestigationReassessResponse:
        """
        Deterministically re-evaluates multi-scenario robustness for an existing persisted investigation
        using a caller-specified scenario shift percentage.
        Does NOT invoke the LLM or execute new database SQL queries.
        """
        from app.schemas.investigation import InvestigationReassessResponse
        from app.services.robustness import RobustnessEngine
        from app.ai.orchestrator import _evaluate_orchestrated_robustness, _is_valid_finite_number

        investigation = cls.get_investigation_by_id(db=db, investigation_id=investigation_id)
        if not investigation:
            raise ValueError(f"Investigation with ID '{investigation_id}' not found.")

        if not investigation.result_json:
            raise ValueError(f"Investigation '{investigation_id}' contains no stored result payload to reassess.")

        try:
            result_data = json.loads(investigation.result_json)
            ask_resp = AskResponse.model_validate(result_data)
        except Exception as err:
            raise ValueError(f"Failed to parse stored result payload for investigation '{investigation_id}': {str(err)}")

        # Extract last successful query data and evidence items
        query_data: Optional[List[Dict[str, Any]]] = None
        if ask_resp.tool_calls:
            for tc in reversed(ask_resp.tool_calls):
                if tc.result and tc.result.success and tc.result.data:
                    query_data = tc.result.data
                    break

        evidence_items = ask_resp.evidence or []
        robustness_engine = RobustnessEngine()

        reassessed_check = _evaluate_orchestrated_robustness(
            robustness_engine=robustness_engine,
            evidence_items=evidence_items,
            query_data=query_data,
            scenario_shift_pct=scenario_shift_pct
        )

        baseline_top: Optional[str] = None
        baseline_metric: Optional[str] = None

        if query_data and len(query_data) > 0 and isinstance(query_data[0], dict) and query_data[0]:
            first_row = query_data[0]
            key_col = next(
                (c for c in ["candidate_id", "candidate", "name", "id", "region", "product_name", "customer_name", "category"] if c in first_row),
                list(first_row.keys())[0] if first_row else ""
            )
            baseline_top = str(first_row.get(key_col)) if first_row.get(key_col) is not None else None

            non_key = [c for c in first_row.keys() if c != key_col]
            for c in non_key:
                if any(_is_valid_finite_number(r.get(c)) for r in query_data if isinstance(r, dict)):
                    baseline_metric = c
                    break

        return InvestigationReassessResponse(
            investigation_id=investigation.investigation_id,
            question=investigation.question,
            original_scenario_shift_pct=10.0,
            requested_scenario_shift_pct=scenario_shift_pct,
            baseline_top_candidate=baseline_top,
            baseline_metric_name=baseline_metric,
            robustness_check=reassessed_check.model_dump(),
            reassessed_at=datetime.now(timezone.utc)
        )

    @staticmethod
    def generate_review_id() -> str:
        """Generates a unique review identifier with 'rev_' prefix."""
        return f"rev_{uuid.uuid4().hex[:12]}"

    @classmethod
    def create_review(
        cls,
        db: Session,
        investigation_id: str,
        review_data: InvestigationReviewCreate
    ) -> InvestigationReview:
        """
        Creates and persists a new append-only Human-in-the-Loop review record for an investigation.
        Does NOT invoke the LLM or execute analytical SQL queries.
        Does NOT mutate original investigation result_json or robustness findings.
        """
        investigation = cls.get_investigation_by_id(db=db, investigation_id=investigation_id)
        if not investigation:
            raise ValueError(f"Investigation with ID '{investigation_id}' not found.")

        if investigation.status == InvestigationStatus.IN_PROGRESS.value:
            raise ValueError(f"Cannot submit review for investigation '{investigation_id}' while status is IN_PROGRESS.")

        status_str = review_data.review_status.value if hasattr(review_data.review_status, "value") else str(review_data.review_status)
        reviewer_id_str = review_data.reviewer_id.strip()

        review = InvestigationReview(
            review_id=cls.generate_review_id(),
            investigation_id=investigation_id,
            review_status=status_str,
            reviewer_id=reviewer_id_str,
            review_notes=review_data.review_notes,
            reviewed_at=utcnow()
        )

        try:
            db.add(review)
            db.commit()
            db.refresh(review)
            return review
        except Exception:
            db.rollback()
            raise

    @classmethod
    def list_reviews_for_investigation(
        cls,
        db: Session,
        investigation_id: str
    ) -> List[InvestigationReview]:
        """
        Retrieves all persistent review records for an investigation ordered newest-first (reviewed_at DESC).
        """
        return (
            db.query(InvestigationReview)
            .filter(InvestigationReview.investigation_id == investigation_id)
            .order_by(desc(InvestigationReview.reviewed_at))
            .all()
        )

    @classmethod
    def get_latest_review(
        cls,
        db: Session,
        investigation_id: str
    ) -> Optional[InvestigationReview]:
        """
        Retrieves the most recent persistent review record for an investigation.
        """
        return (
            db.query(InvestigationReview)
            .filter(InvestigationReview.investigation_id == investigation_id)
            .order_by(desc(InvestigationReview.reviewed_at))
            .first()
        )

    @classmethod
    def get_metrics_summary(cls, db: Session) -> InvestigationMetricsSummary:
        """
        Calculates and returns global aggregate metrics across all persisted investigations and reviews.
        """
        total_investigations = db.query(func.count(Investigation.investigation_id)).scalar() or 0
        total_reviews = db.query(func.count(InvestigationReview.review_id)).scalar() or 0

        status_counts: Dict[str, int] = {
            "COMPLETED": 0,
            "REQUIRES_REVIEW": 0,
            "FAILED": 0,
            "IN_PROGRESS": 0
        }
        status_rows = db.query(Investigation.status, func.count(Investigation.investigation_id)).group_by(Investigation.status).all()
        for st, count in status_rows:
            if st:
                status_counts[st] = count

        review_counts: Dict[str, int] = {
            "APPROVED": 0,
            "REJECTED": 0,
            "FLAGGED": 0
        }
        review_rows = db.query(InvestigationReview.review_status, func.count(InvestigationReview.review_id)).group_by(InvestigationReview.review_status).all()
        for r_st, count in review_rows:
            if r_st:
                review_counts[r_st] = count

        robustness_counts: Dict[str, int] = {
            "STABLE": 0,
            "SENSITIVE": 0,
            "INSUFFICIENT_EVIDENCE": 0
        }
        rob_rows = db.query(Investigation.robustness_status, func.count(Investigation.investigation_id)).group_by(Investigation.robustness_status).all()
        for rob_st, count in rob_rows:
            if rob_st:
                robustness_counts[rob_st] = count

        avg_ms = db.query(func.avg(Investigation.execution_time_ms)).filter(Investigation.execution_time_ms.isnot(None)).scalar()
        avg_exec_time = round(float(avg_ms), 2) if avg_ms is not None else None

        return InvestigationMetricsSummary(
            total_investigations=total_investigations,
            total_reviews=total_reviews,
            status_counts=status_counts,
            review_counts=review_counts,
            robustness_counts=robustness_counts,
            average_execution_time_ms=avg_exec_time
        )
