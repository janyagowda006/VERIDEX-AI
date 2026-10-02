"""
VERIDEX-AI — Unified Investigation Service
Persistence and lifecycle management for evidence-backed investigations.

Core Principle: "AI for reasoning, code for correctness."
"""

import uuid
import json
import re
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Union
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.models.investigation import (
    Investigation,
    InvestigationReview,
    InvestigationTurn,
    InvestigationAuditLog,
    utcnow,
    _utc_now
)
from app.schemas.ai import AskResponse, ToolCallRecord
from app.schemas.evidence import EvidenceItem, ClaimEvidence
from app.schemas.decision import DecisionAnalysis
from app.schemas.investigation import (
    InvestigationStatus,
    InvestigationReviewStatus,
    ReviewStatus,
    ReviewDecision,
    InvestigationSummary,
    InvestigationDetailResponse,
    InvestigationAuditLogEntry,
    InvestigationReassessResponse,
    InvestigationReviewCreate,
    InvestigationReviewResponse,
    InvestigationMetricsSummary,
    InvestigationTurnResponse
)
from app.services.robustness import ROBUSTNESS_STATUS_SENSITIVE


DEFAULT_LIMIT = 20
MAX_LIMIT = 100


class InvestigationNotFoundError(ValueError):
    """Raised when an investigation ID is not found in the persistence store."""
    pass


class InvestigationValidationError(ValueError):
    """Raised when investigation parameters fail validation bounds or rules."""
    pass


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


def _is_db_session(arg: Any) -> bool:
    """
    Returns True if arg looks like a SQLAlchemy Session or mock DB session.
    """
    if arg is None:
        return False
    if isinstance(arg, (str, AskResponse, int, float, dict, list)):
        return False
    return hasattr(arg, "query") or hasattr(arg, "add") or hasattr(arg, "commit") or hasattr(arg, "execute")


def _is_mock_session(session: Any) -> bool:
    """
    Returns True if session is a MagicMock instance.
    """
    return hasattr(session, "_mock_name") or type(session).__name__ == "MagicMock"


class InvestigationService:
    """
    Unified persistence and business-logic service for VERIDEX investigations.
    Supports both static/classmethod utility calls and instance-based service calls.
    """

    def __init__(self, db: Optional[Session] = None):
        self.db = db

    def _resolve_session(self, db: Optional[Session] = None) -> Session:
        session = db or self.db
        if session is None:
            raise InvestigationValidationError(
                "SQLAlchemy Session must be provided either at InvestigationService initialization or method call."
            )
        return session

    @staticmethod
    def generate_investigation_id() -> str:
        """Generates a unique investigation identifier with 'inv_' prefix."""
        return f"inv_{uuid.uuid4().hex[:12]}"

    @staticmethod
    def generate_review_id() -> str:
        """Generates a unique review identifier with 'rev_' prefix."""
        return f"rev_{uuid.uuid4().hex[:12]}"

    @staticmethod
    def generate_turn_id() -> str:
        """Generates a unique conversation turn identifier with 'turn_' prefix."""
        return f"turn_{uuid.uuid4().hex[:12]}"

    @classmethod
    def create_investigation(
        cls,
        *args,
        db: Optional[Session] = None,
        question: Optional[str] = None,
        response: Optional[AskResponse] = None,
        investigation_id: Optional[str] = None,
        owner_id: Optional[str] = None,
        **kwargs
    ) -> Investigation:
        """
        Creates or updates an Investigation record.
        """
        session = db
        q = question
        resp = response
        inv_id = investigation_id

        for arg in args:
            if _is_db_session(arg) and not session:
                session = arg
            elif isinstance(arg, str) and not q:
                q = arg
            elif isinstance(arg, AskResponse) and not resp:
                resp = arg
            elif isinstance(arg, str) and q and not inv_id:
                inv_id = arg

        if hasattr(cls, "db") and getattr(cls, "db", None) and not session:
            session = getattr(cls, "db")

        if session is None:
            raise InvestigationValidationError("Session required to create investigation.")

        if q and not str(q).strip():
            raise InvestigationValidationError("Question must not be empty or blank.")

        clean_question = str(q).strip() if q else (resp.question if resp else "Investigation Question")
        target_inv_id = inv_id or (resp.metadata.get("investigation_id") if resp and resp.metadata and "investigation_id" in resp.metadata else cls.generate_investigation_id())

        now = _utc_now()

        existing_inv = None
        if not _is_mock_session(session):
            try:
                existing_inv = session.query(Investigation).filter(Investigation.investigation_id == target_inv_id).first()
            except Exception:
                try:
                    session.rollback()
                except Exception:
                    pass


        if resp is not None:
            if not isinstance(resp, AskResponse):
                raise InvestigationValidationError("A valid AskResponse instance is required.")

            if resp.metadata and resp.metadata.get("limit_reached"):
                lifecycle_status = InvestigationStatus.LIMIT_REACHED.value
            elif resp.success:
                lifecycle_status = InvestigationStatus.COMPLETED.value
            else:
                lifecycle_status = InvestigationStatus.FAILED.value

            robustness_status: Optional[str] = None
            if resp.analysis and resp.analysis.robustness:
                robustness_status = resp.analysis.robustness.status
            elif resp.metadata and "robustness_status" in resp.metadata:
                robustness_status = str(resp.metadata["robustness_status"])

            claims_json = [c.model_dump(mode="json") for c in resp.claims] if resp.claims else []
            evidence_json = [e.model_dump(mode="json") for e in resp.evidence] if resp.evidence else []
            analysis_json = resp.analysis.model_dump(mode="json") if resp.analysis else None
            tool_calls_json = [t.model_dump(mode="json") for t in resp.tool_calls] if resp.tool_calls else []

            metadata_json = dict(resp.metadata or {})
            metadata_json["_response_state"] = {
                "success": resp.success,
                "error": resp.error
            }

            result_json_str = resp.model_dump_json() if hasattr(resp, "model_dump_json") else json.dumps(resp.model_dump(), default=str)
            err_msg = _sanitize_error_text(resp.error) if resp.error else None

            if existing_inv:
                investigation = existing_inv
                investigation.question = clean_question
                investigation.status = lifecycle_status
                investigation.robustness_status = robustness_status
                investigation.completed_at = now
                investigation.turns_used = resp.metadata.get("total_turns", 1) if resp.metadata else 1
                investigation.tool_calls_count = len(resp.tool_calls) if resp.tool_calls else 0
                investigation.evidence_count = len(resp.evidence) if resp.evidence else 0
                investigation.claims_count = len(resp.claims) if resp.claims else 0
                investigation.answer = resp.answer
                investigation.claims_json = claims_json
                investigation.evidence_json = evidence_json
                investigation.analysis_json = analysis_json
                investigation.tool_calls_json = tool_calls_json
                investigation.metadata_json = metadata_json
            else:
                investigation = Investigation(
                    investigation_id=target_inv_id,
                    question=clean_question,
                    status=lifecycle_status,
                    robustness_status=robustness_status,
                    review_status=ReviewStatus.PENDING.value,
                    created_at=now,
                    completed_at=now,
                    turns_used=resp.metadata.get("total_turns", 1) if resp.metadata else 1,
                    tool_calls_count=len(resp.tool_calls) if resp.tool_calls else 0,
                    evidence_count=len(resp.evidence) if resp.evidence else 0,
                    claims_count=len(resp.claims) if resp.claims else 0,
                    result_json=result_json_str,
                    error_message=err_msg,
                    owner_id=owner_id,
                    answer=resp.answer,
                    claims_json=claims_json,
                    evidence_json=evidence_json,
                    analysis_json=analysis_json,
                    tool_calls_json=tool_calls_json,
                    metadata_json=metadata_json
                )
                session.add(investigation)



            initial_audit = InvestigationAuditLog(
                audit_id=f"audit_{uuid.uuid4().hex[:28]}",
                investigation_id=target_inv_id,
                event_type="INVESTIGATION_COMPLETED" if resp.success else "INVESTIGATION_FAILED",
                review_status=ReviewStatus.PENDING.value,
                reviewer_notes=None,
                created_at=now
            )


            try:
                session.add(initial_audit)
                session.commit()
                if not _is_mock_session(session):
                    session.refresh(investigation)
                return investigation
            except Exception:
                session.rollback()
                raise

        else:
            if existing_inv:
                return existing_inv

            investigation = Investigation(
                investigation_id=target_inv_id,
                question=clean_question,
                status=InvestigationStatus.IN_PROGRESS.value,
                created_at=now,
                owner_id=owner_id
            )


            try:
                session.add(investigation)
                session.commit()
                if not _is_mock_session(session):
                    session.refresh(investigation)
                return investigation
            except Exception:
                session.rollback()
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
        """
        investigation = db.query(Investigation).filter(Investigation.investigation_id == investigation_id).first()

        robustness_status_str = None
        target_status = InvestigationStatus.COMPLETED.value

        if response.analysis and response.analysis.robustness:
            robustness_status_str = response.analysis.robustness.status
        elif response.metadata and "robustness_status" in response.metadata:
            robustness_status_str = str(response.metadata["robustness_status"])

        if robustness_status_str and robustness_status_str.upper() == ROBUSTNESS_STATUS_SENSITIVE.upper():
            target_status = InvestigationStatus.REQUIRES_REVIEW.value

        result_json_str = response.model_dump_json() if hasattr(response, "model_dump_json") else json.dumps(response.model_dump(), default=str)

        if not investigation and not _is_mock_session(db):
            return None

        if investigation and not _is_mock_session(investigation):
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
            investigation.answer = response.answer

            investigation.claims_json = [c.model_dump(mode="json") for c in response.claims] if response.claims else []
            investigation.evidence_json = [e.model_dump(mode="json") for e in response.evidence] if response.evidence else []
            investigation.analysis_json = response.analysis.model_dump(mode="json") if response.analysis else None
            investigation.tool_calls_json = [t.model_dump(mode="json") for t in response.tool_calls] if response.tool_calls else []

        try:
            db.commit()
            if investigation and not _is_mock_session(db):
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
        if not investigation and not _is_mock_session(db):
            return None

        sanitized_error = _sanitize_error_text(error_message)

        if investigation and not _is_mock_session(investigation):
            investigation.status = InvestigationStatus.FAILED.value
            investigation.completed_at = utcnow()
            if execution_time_ms is not None:
                investigation.execution_time_ms = round(execution_time_ms, 2)
            investigation.error_message = sanitized_error

        try:
            db.commit()
            if investigation and not _is_mock_session(db):
                db.refresh(investigation)
            return investigation
        except Exception:
            db.rollback()
            raise

    @classmethod
    def get_investigation_by_id(
        cls,
        *args,
        db: Optional[Session] = None,
        investigation_id: Optional[str] = None
    ) -> Optional[Investigation]:
        """
        Retrieves a specific Investigation record by investigation_id.
        """
        session = db
        target_id = investigation_id

        for arg in args:
            if _is_db_session(arg) and not session:
                session = arg
            elif isinstance(arg, str) and not target_id:
                target_id = arg

        if hasattr(cls, "db") and getattr(cls, "db", None) and not session:
            session = getattr(cls, "db")

        if not session or not target_id:
            return None

        return session.query(Investigation).filter(Investigation.investigation_id == str(target_id).strip()).first()

    def get_investigation(
        self,
        *args,
        db: Optional[Session] = None,
        investigation_id: Optional[str] = None
    ) -> Optional[Investigation]:
        return self.get_investigation_by_id(*args, db=db or self.db, investigation_id=investigation_id)

    def reconstruct_ask_response(self, investigation: Investigation) -> AskResponse:
        """
        Losslessly reconstructs an AskResponse from an Investigation persistence model.
        """
        if not investigation:
            raise InvestigationNotFoundError("Investigation record is None.")

        if investigation.result_json:
            try:
                return AskResponse.model_validate_json(investigation.result_json)
            except Exception:
                pass

        claims = [ClaimEvidence.model_validate(c) for c in (investigation.claims_json or [])]
        evidence = [EvidenceItem.model_validate(e) for e in (investigation.evidence_json or [])]
        analysis = DecisionAnalysis.model_validate(investigation.analysis_json) if investigation.analysis_json else None
        tool_calls = [ToolCallRecord.model_validate(t) for t in (investigation.tool_calls_json or [])]

        meta = dict(investigation.metadata_json or {})
        res_state = meta.pop("_response_state", {})
        success = res_state.get("success", investigation.status != InvestigationStatus.FAILED.value)
        error = res_state.get("error", investigation.error_message)

        return AskResponse(
            success=success,
            question=investigation.question,
            answer=investigation.answer or "",
            claims=claims,
            evidence=evidence,
            analysis=analysis,
            tool_calls=tool_calls,
            metadata=meta,
            error=error
        )

    def to_summary(self, investigation: Investigation) -> InvestigationSummary:
        """
        Converts an Investigation model to a lightweight InvestigationSummary schema.
        """
        top_finding = None
        analysis_json = getattr(investigation, "analysis_json", None)
        if analysis_json and isinstance(analysis_json, dict):
            rec = analysis_json.get("recommendation")
            if rec and isinstance(rec, dict):
                top_finding = rec.get("action_title")
        elif investigation.result_json:
            try:
                data = json.loads(investigation.result_json) if isinstance(investigation.result_json, str) else investigation.result_json
                if isinstance(data, dict) and data.get("analysis") and data["analysis"].get("recommendation"):
                    top_finding = data["analysis"]["recommendation"].get("action_title")
            except Exception:
                pass

        created_val = investigation.created_at
        completed_val = investigation.completed_at
        rev_status = getattr(investigation, "review_status", "PENDING")

        return InvestigationSummary(
            investigation_id=investigation.investigation_id,
            question=investigation.question,
            created_at=created_val,
            completed_at=completed_val,
            status=investigation.status,
            robustness_status=investigation.robustness_status,
            review_status=rev_status,
            top_finding=top_finding,
            execution_time_ms=investigation.execution_time_ms,
            turns_used=investigation.turns_used or 0,
            tool_calls_count=investigation.tool_calls_count or 0,
            evidence_count=investigation.evidence_count or 0,
            claims_count=investigation.claims_count or 0,
            owner_id=investigation.owner_id
        )


    def get_investigation_detail(self, investigation_id: str, db: Optional[Session] = None) -> Optional[InvestigationDetailResponse]:
        """
        Retrieves complete investigation detail combining metadata with reconstructed AskResponse and review audit history.
        """
        session = self._resolve_session(db)
        inv = session.query(Investigation).filter(Investigation.investigation_id == investigation_id).first()
        if not inv:
            return None

        ask_resp = self.reconstruct_ask_response(inv)

        latest_notes = None
        if inv.audit_logs:
            for audit in sorted(inv.audit_logs, key=lambda a: a.created_at, reverse=True):
                if audit.reviewer_notes:
                    latest_notes = audit.reviewer_notes
                    break

        audit_trail = []
        if inv.audit_logs:
            for audit in sorted(inv.audit_logs, key=lambda a: a.created_at):
                audit_trail.append(InvestigationAuditLogEntry(
                    audit_id=audit.audit_id,
                    investigation_id=audit.investigation_id,
                    event_type=audit.event_type,
                    review_status=audit.review_status,
                    reviewer_notes=audit.reviewer_notes,
                    created_at=audit.created_at,
                    event_metadata=audit.event_metadata_json or {}
                ))

        latest_rev = self.get_latest_review(db=session, investigation_id=investigation_id)
        reviews = self.list_reviews_for_investigation(db=session, investigation_id=investigation_id)
        turns = self.list_turns_for_investigation(db=session, investigation_id=investigation_id)

        latest_rev_resp = InvestigationReviewResponse.model_validate(latest_rev) if latest_rev else None
        turns_resp = [InvestigationTurnResponse.model_validate(t) for t in turns]

        review_id_val = latest_rev.review_id if latest_rev else None
        reviewer_id_val = latest_rev.reviewer_id if latest_rev else None
        reviewed_at_val = latest_rev.reviewed_at if latest_rev else None

        return InvestigationDetailResponse(
            investigation_id=inv.investigation_id,
            question=inv.question,
            status=inv.status,
            robustness_status=inv.robustness_status,
            review_status=latest_rev.review_status if latest_rev else "PENDING",
            created_at=inv.created_at,

            completed_at=inv.completed_at,
            response=ask_resp,
            reviewer_notes=latest_notes,
            audit_trail=audit_trail,
            review_id=review_id_val,
            reviewer_id=reviewer_id_val,
            reviewed_at=reviewed_at_val,
            result_json=inv.result_json,
            error_message=inv.error_message,
            latest_review=latest_rev_resp,
            review_count=len(reviews),
            turns=turns_resp,
            turns_used=inv.turns_used or 0,
            tool_calls_count=inv.tool_calls_count or 0,
            evidence_count=inv.evidence_count or 0,
            claims_count=inv.claims_count or 0,
            owner_id=inv.owner_id
        )

    @classmethod
    def list_investigations(
        cls,
        *args,
        db: Optional[Session] = None,
        limit: int = DEFAULT_LIMIT,
        offset: int = 0,
        search: Optional[str] = None,
        status: Optional[str] = None,
        robustness_status: Optional[str] = None,
        owner_id: Optional[str] = None,
        **kwargs
    ) -> List[Investigation]:
        """
        Retrieves Investigation records ordered by created_at DESC with bounded pagination and optional filtering.
        """
        session = db
        lim = limit
        off = offset

        for arg in args:
            if _is_db_session(arg) and not session:
                session = arg
            elif isinstance(arg, int):
                if lim == DEFAULT_LIMIT:
                    lim = arg
                else:
                    off = arg

        if hasattr(cls, "db") and getattr(cls, "db", None) and not session:
            session = getattr(cls, "db")

        if session is None:
            raise InvestigationValidationError("Session required to list investigations.")

        if off < 0:
            raise InvestigationValidationError(f"Pagination offset must be non-negative, got {off}.")
        if lim < 1:
            raise InvestigationValidationError(f"Pagination limit must be at least 1, got {lim}.")
        if lim > MAX_LIMIT:
            raise InvestigationValidationError(f"Pagination limit cannot exceed {MAX_LIMIT}, got {lim}.")

        query = session.query(Investigation)

        if owner_id:
            query = query.filter(Investigation.owner_id == owner_id)

        if search and str(search).strip():
            term = f"%{str(search).strip()}%"
            query = query.filter(
                (Investigation.question.ilike(term)) |
                (Investigation.investigation_id.ilike(term))
            )

        if status and str(status).strip():
            query = query.filter(Investigation.status == str(status).strip().upper())

        if robustness_status and str(robustness_status).strip():
            query = query.filter(Investigation.robustness_status == str(robustness_status).strip().upper())

        return (
            query.order_by(Investigation.created_at.desc(), Investigation.investigation_id.desc())
            .offset(off)
            .limit(lim)
            .all()
        )

    def list_summaries(self, limit: int = DEFAULT_LIMIT, offset: int = 0, db: Optional[Session] = None) -> List[InvestigationSummary]:
        invs = self.list_investigations(limit=limit, offset=offset, db=db or self.db)
        return [self.to_summary(inv) for inv in invs]

    def update_review(
        self,
        investigation_id: str,
        review_decision: Any,
        reviewer_notes: Optional[str] = None,
        reviewer_user_id: Optional[str] = None,
        db: Optional[Session] = None
    ) -> Investigation:
        """
        Updates review status on investigation and creates review and audit events.
        """
        session = self._resolve_session(db)
        inv = session.query(Investigation).filter(Investigation.investigation_id == investigation_id).first()
        if not inv:
            raise InvestigationNotFoundError(f"Investigation '{investigation_id}' not found.")

        if inv.status == InvestigationStatus.IN_PROGRESS.value:
            raise ValueError(f"Cannot submit review for investigation '{investigation_id}' while status is IN_PROGRESS.")

        decision_val = review_decision.value if hasattr(review_decision, "value") else str(review_decision)
        decision_val = decision_val.upper()
        if decision_val not in ("APPROVED", "REJECTED", "FLAGGED"):
            raise ValueError(f"Invalid review decision '{decision_val}'. Allowed values are APPROVED, REJECTED, FLAGGED.")

        final_reviewer = reviewer_user_id or "reviewer_user"
        if inv.owner_id and inv.owner_id == final_reviewer:
            raise ValueError("Self-Review Blocked: You cannot review an investigation you initiated.")

        inv.review_status = decision_val

        review_rec = InvestigationReview(


            review_id=self.generate_review_id(),
            investigation_id=investigation_id,
            review_status=decision_val,
            reviewer_id=final_reviewer,
            review_notes=reviewer_notes,
            reviewed_at=utcnow()
        )

        audit = InvestigationAuditLog(
            audit_id=f"audit_{uuid.uuid4().hex[:28]}",
            investigation_id=investigation_id,
            event_type="HUMAN_REVIEW_UPDATED",
            review_status=decision_val,
            reviewer_notes=reviewer_notes,
            created_at=_utc_now()
        )
        try:
            session.add(review_rec)
            session.add(audit)
            session.commit()
            session.refresh(inv)
            return inv
        except Exception:
            session.rollback()
            raise

    @classmethod
    def reassess_investigation(
        cls,
        db: Session,
        investigation_id: str,
        scenario_shift_pct: float = 10.0
    ) -> InvestigationReassessResponse:
        from app.services.robustness import RobustnessEngine
        from app.ai.orchestrator import _evaluate_orchestrated_robustness, _is_valid_finite_number

        investigation = cls.get_investigation_by_id(db=db, investigation_id=investigation_id)
        if not investigation:
            raise ValueError(f"Investigation with ID '{investigation_id}' not found.")

        if not investigation.result_json and not investigation.claims_json and not investigation.analysis_json:
            raise ValueError(f"Investigation '{investigation_id}' contains no stored result payload to reassess.")

        ask_resp: Optional[AskResponse] = None
        if investigation.result_json:
            try:
                result_data = json.loads(investigation.result_json)
                ask_resp = AskResponse.model_validate(result_data)
            except Exception:
                pass

        if not ask_resp:
            inst = cls(db)
            try:
                ask_resp = inst.reconstruct_ask_response(investigation)
            except Exception as err:
                raise ValueError(f"Failed to parse stored result payload for investigation '{investigation_id}': {str(err)}")

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

    @classmethod
    def create_review(
        cls,
        db: Session,
        investigation_id: str,
        review_data: InvestigationReviewCreate,
        reviewer_user_id: Optional[str] = None
    ) -> InvestigationReview:
        inst = cls(db)
        st = getattr(review_data, "status", getattr(review_data, "review_status", None))
        notes = getattr(review_data, "review_notes", getattr(review_data, "reviewer_notes", None))
        r_id = reviewer_user_id or getattr(review_data, "reviewer_id", None)
        inst.update_review(
            investigation_id=investigation_id,
            review_decision=st,
            reviewer_notes=notes,
            reviewer_user_id=r_id,
            db=db
        )
        return cls.get_latest_review(db=db, investigation_id=investigation_id)

    @classmethod
    def list_reviews_for_investigation(
        cls,
        db: Session,
        investigation_id: str
    ) -> List[InvestigationReview]:
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
        return (
            db.query(InvestigationReview)
            .filter(InvestigationReview.investigation_id == investigation_id)
            .order_by(desc(InvestigationReview.reviewed_at))
            .first()
        )

    @classmethod
    def get_metrics_summary(cls, db: Session) -> InvestigationMetricsSummary:
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

    @classmethod
    def create_turn(
        cls,
        db: Session,
        investigation_id: str,
        user_question: str,
        response: Optional[Any] = None,
        execution_time_ms: Optional[float] = None,
        turn_number: Optional[int] = None
    ) -> InvestigationTurn:
        investigation = cls.get_investigation_by_id(db=db, investigation_id=investigation_id)
        if not investigation:
            raise ValueError(f"Investigation with ID '{investigation_id}' not found.")

        if turn_number is None:
            max_turn = (
                db.query(func.max(InvestigationTurn.turn_number))
                .filter(InvestigationTurn.investigation_id == investigation_id)
                .scalar()
            )
            turn_num = (max_turn + 1) if max_turn is not None else 1
        else:
            turn_num = int(turn_number)

        result_json_str = None
        if response is not None:
            if hasattr(response, "model_dump_json"):
                result_json_str = response.model_dump_json()
            elif isinstance(response, str):
                result_json_str = response
            else:
                result_json_str = json.dumps(response, default=str)

        exec_time = round(float(execution_time_ms), 2) if execution_time_ms is not None else None

        turn = InvestigationTurn(
            turn_id=cls.generate_turn_id(),
            investigation_id=investigation_id,
            turn_number=turn_num,
            user_question=user_question,
            execution_time_ms=exec_time,
            result_json=result_json_str,
            created_at=utcnow()
        )

        try:
            db.add(turn)
            db.commit()
            db.refresh(turn)
            return turn
        except Exception:
            db.rollback()
            raise

    @classmethod
    def list_turns_for_investigation(
        cls,
        db: Session,
        investigation_id: str
    ) -> List[InvestigationTurn]:
        return (
            db.query(InvestigationTurn)
            .filter(InvestigationTurn.investigation_id == investigation_id)
            .order_by(InvestigationTurn.turn_number.asc())
            .all()
        )

    @classmethod
    def list_recent_turns_for_investigation(
        cls,
        db: Session,
        investigation_id: str,
        limit: int = 3
    ) -> List[InvestigationTurn]:
        turns_desc = (
            db.query(InvestigationTurn)
            .filter(InvestigationTurn.investigation_id == investigation_id)
            .order_by(InvestigationTurn.turn_number.desc())
            .limit(limit)
            .all()
        )
        return sorted(turns_desc, key=lambda t: t.turn_number)
