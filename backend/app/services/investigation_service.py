import uuid
import json
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.investigation import Investigation, utcnow
from app.schemas.investigation import (
    InvestigationStatus,
    InvestigationSummary,
    InvestigationDetail
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
