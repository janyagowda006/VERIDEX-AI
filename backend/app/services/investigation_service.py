"""
VERIDEX-AI — Investigation Service (Phase 9.2B)
Persistence and lifecycle management for evidence-backed investigations.

Core Principle: "AI for reasoning, code for correctness."
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Union
from sqlalchemy.orm import Session

from app.models.investigation import Investigation, InvestigationAuditLog
from app.schemas.ai import AskResponse
from app.schemas.investigation import (
    InvestigationStatus,
    ReviewStatus,
    ReviewDecision,
    InvestigationSummary,
    InvestigationDetailResponse,
    InvestigationAuditLogEntry,
)


DEFAULT_LIMIT = 20
MAX_LIMIT = 100


class InvestigationNotFoundError(ValueError):
    """Raised when an investigation ID is not found in the persistence store."""
    pass


class InvestigationValidationError(ValueError):
    """Raised when investigation parameters fail validation bounds or rules."""
    pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class InvestigationService:
    """
    Persistence and business-logic service for VERIDEX investigations, review workflows,
    and audit trails. Operates on an injected or method-provided SQLAlchemy Session.
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

    def create_investigation(
        self,
        *args,
        db: Optional[Session] = None,
        question: Optional[str] = None,
        response: Optional[AskResponse] = None,
        investigation_id: Optional[str] = None,
        **kwargs
    ) -> Investigation:
        """
        Persists a completed AskResponse and associated metadata as a durable investigation record.
        Saves claims, evidence, analysis, tool calls, and metadata losslessly.
        Creates an initial lifecycle audit record in a single atomic transaction.
        """
        session = db
        q = question
        resp = response
        inv_id = investigation_id

        if len(args) == 1:
            if isinstance(args[0], Session):
                session = args[0]
            elif isinstance(args[0], str):
                q = args[0]
        elif len(args) == 2:
            if isinstance(args[0], Session):
                session = args[0]
                if isinstance(args[1], str):
                    q = args[1]
                elif isinstance(args[1], AskResponse):
                    resp = args[1]
            else:
                q = args[0]
                resp = args[1]
        elif len(args) >= 3:
            if isinstance(args[0], Session):
                session = args[0]
                q = args[1]
                resp = args[2]
                if len(args) >= 4 and isinstance(args[3], str):
                    inv_id = args[3]
            else:
                q = args[0]
                resp = args[1]
                if isinstance(args[2], Session):
                    session = args[2]
                elif isinstance(args[2], str):
                    inv_id = args[2]

        resolved_session = self._resolve_session(session)

        if not q or not str(q).strip():
            raise InvestigationValidationError("Question must not be empty or blank.")
        clean_question = str(q).strip()

        if resp is None or not isinstance(resp, AskResponse):
            raise InvestigationValidationError("A valid AskResponse instance is required to create an investigation.")

        target_inv_id = inv_id or f"inv_{uuid.uuid4().hex[:28]}"

        # Determine lifecycle status
        if resp.metadata and resp.metadata.get("limit_reached"):
            lifecycle_status = InvestigationStatus.LIMIT_REACHED.value
        elif resp.success:
            lifecycle_status = InvestigationStatus.COMPLETED.value
        else:
            lifecycle_status = InvestigationStatus.FAILED.value

        # Extract robustness status deterministically
        robustness_status: Optional[str] = None
        if resp.analysis and resp.analysis.robustness:
            robustness_status = resp.analysis.robustness.status
        elif resp.metadata and "robustness_status" in resp.metadata:
            robustness_status = str(resp.metadata["robustness_status"])

        # Serialize Pydantic components to JSON-compatible primitives
        claims_json = [c.model_dump(mode="json") for c in resp.claims]
        evidence_json = [e.model_dump(mode="json") for e in resp.evidence]
        analysis_json = resp.analysis.model_dump(mode="json") if resp.analysis else None
        tool_calls_json = [t.model_dump(mode="json") for t in resp.tool_calls]

        # Preserve response-level state in metadata for lossless AskResponse reconstruction
        metadata_json = dict(resp.metadata or {})
        metadata_json["_response_state"] = {
            "success": resp.success,
            "error": resp.error
        }

        now = _utc_now()
        is_finished = lifecycle_status in (
            InvestigationStatus.COMPLETED.value,
            InvestigationStatus.FAILED.value,
            InvestigationStatus.LIMIT_REACHED.value
        )
        completed_at = now if is_finished else None

        investigation = Investigation(
            investigation_id=target_inv_id,
            question=clean_question,
            status=lifecycle_status,
            robustness_status=robustness_status,
            review_status=ReviewStatus.PENDING.value,
            created_at=now,
            completed_at=completed_at,
            answer=resp.answer,
            claims_json=claims_json,
            evidence_json=evidence_json,
            analysis_json=analysis_json,
            tool_calls_json=tool_calls_json,
            metadata_json=metadata_json
        )

        initial_audit = InvestigationAuditLog(
            audit_id=f"audit_{uuid.uuid4().hex[:28]}",
            investigation_id=target_inv_id,
            event_type="INVESTIGATION_COMPLETED" if resp.success else "INVESTIGATION_FAILED",
            review_status=ReviewStatus.PENDING.value,
            reviewer_notes=None,
            created_at=now,
            event_metadata_json={
                "success": resp.success,
                "tool_calls_count": len(resp.tool_calls),
                "robustness_status": robustness_status
            }
        )

        try:
            resolved_session.add(investigation)
            resolved_session.add(initial_audit)
            resolved_session.commit()
            resolved_session.refresh(investigation)
            return investigation
        except Exception:
            resolved_session.rollback()
            raise

    def get_investigation(
        self,
        *args,
        db: Optional[Session] = None,
        investigation_id: Optional[str] = None
    ) -> Optional[Investigation]:
        """
        Retrieves an Investigation by primary key ID.
        Returns None if not found; does not silently create records.
        """
        session = db
        target_id = investigation_id

        if len(args) == 1:
            if isinstance(args[0], Session):
                session = args[0]
            else:
                target_id = args[0]
        elif len(args) >= 2:
            if isinstance(args[0], Session):
                session = args[0]
                target_id = args[1]
            else:
                target_id = args[0]
                if isinstance(args[1], Session):
                    session = args[1]

        resolved_session = self._resolve_session(session)
        if not target_id:
            return None

        return (
            resolved_session.query(Investigation)
            .filter(Investigation.investigation_id == str(target_id).strip())
            .first()
        )

    def list_investigations(
        self,
        *args,
        db: Optional[Session] = None,
        limit: int = DEFAULT_LIMIT,
        offset: int = 0
    ) -> List[Investigation]:
        """
        Lists investigations with deterministic newest-first ordering and bounded pagination.
        Enforces 0 <= offset and 1 <= limit <= MAX_LIMIT.
        """
        session = db
        lim = limit
        off = offset

        if len(args) == 1:
            if isinstance(args[0], Session):
                session = args[0]
            elif isinstance(args[0], int):
                lim = args[0]
        elif len(args) == 2:
            if isinstance(args[0], Session):
                session = args[0]
                lim = args[1]
            else:
                lim = args[0]
                off = args[1]
        elif len(args) >= 3:
            if isinstance(args[0], Session):
                session = args[0]
                lim = args[1]
                off = args[2]
            else:
                lim = args[0]
                off = args[1]
                if isinstance(args[2], Session):
                    session = args[2]

        resolved_session = self._resolve_session(session)

        if off < 0:
            raise InvestigationValidationError(f"Pagination offset must be non-negative, got {off}.")
        if lim < 1:
            raise InvestigationValidationError(f"Pagination limit must be at least 1, got {lim}.")
        if lim > MAX_LIMIT:
            raise InvestigationValidationError(f"Pagination limit cannot exceed {MAX_LIMIT}, got {lim}.")

        return (
            resolved_session.query(Investigation)
            .order_by(Investigation.created_at.desc(), Investigation.investigation_id.desc())
            .offset(off)
            .limit(lim)
            .all()
        )

    def reconstruct_ask_response(self, investigation: Investigation) -> AskResponse:
        """
        Deserializes persisted JSON columns and reconstructs the original AskResponse
        using Pydantic validation. Reconstitutes nested claims, evidence, analysis, and tool calls.
        """
        if investigation is None:
            raise InvestigationValidationError("Investigation instance cannot be None.")

        metadata_dict = dict(investigation.metadata_json or {})
        resp_state = metadata_dict.pop("_response_state", {})

        success = resp_state.get("success")
        if success is None:
            success = (investigation.status != InvestigationStatus.FAILED.value)

        error = resp_state.get("error")

        payload = {
            "success": success,
            "question": investigation.question,
            "answer": investigation.answer or "",
            "claims": investigation.claims_json or [],
            "evidence": investigation.evidence_json or [],
            "analysis": investigation.analysis_json,
            "tool_calls": investigation.tool_calls_json or [],
            "metadata": metadata_dict,
            "error": error
        }

        return AskResponse.model_validate(payload)

    def get_investigation_detail(
        self,
        *args,
        db: Optional[Session] = None,
        investigation_id: Optional[str] = None
    ) -> Optional[InvestigationDetailResponse]:
        """
        Retrieves the complete investigation detail combining scalar metadata,
        reconstructed AskResponse, and chronological audit history.
        """
        inv = self.get_investigation(*args, db=db, investigation_id=investigation_id)
        if inv is None:
            return None

        ask_response = self.reconstruct_ask_response(inv)

        audit_trail: List[InvestigationAuditLogEntry] = []
        latest_notes: Optional[str] = None

        # Build chronological audit trail (earliest first)
        sorted_logs = sorted(inv.audit_logs, key=lambda l: l.created_at) if inv.audit_logs else []
        for log in sorted_logs:
            created_str = (
                log.created_at.isoformat()
                if hasattr(log.created_at, "isoformat")
                else str(log.created_at)
            )
            audit_trail.append(
                InvestigationAuditLogEntry(
                    audit_id=log.audit_id,
                    investigation_id=log.investigation_id,
                    event_type=log.event_type,
                    review_status=log.review_status,
                    reviewer_notes=log.reviewer_notes,
                    created_at=created_str,
                    event_metadata=log.event_metadata_json or {}
                )
            )
            if log.reviewer_notes:
                latest_notes = log.reviewer_notes

        inv_created_str = (
            inv.created_at.isoformat()
            if hasattr(inv.created_at, "isoformat")
            else str(inv.created_at)
        )
        inv_completed_str = (
            inv.completed_at.isoformat()
            if inv.completed_at and hasattr(inv.completed_at, "isoformat")
            else None
        )

        return InvestigationDetailResponse(
            investigation_id=inv.investigation_id,
            question=inv.question,
            status=inv.status,
            review_status=inv.review_status,
            created_at=inv_created_str,
            completed_at=inv_completed_str,
            response=ask_response,
            reviewer_notes=latest_notes,
            audit_trail=audit_trail
        )

    def create_audit_log(
        self,
        *args,
        db: Optional[Session] = None,
        investigation_id: Optional[str] = None,
        event_type: Optional[str] = None,
        review_status: Optional[str] = None,
        reviewer_notes: Optional[str] = None,
        event_metadata: Optional[Dict[str, Any]] = None,
    ) -> InvestigationAuditLog:
        """
        Constructs and adds an InvestigationAuditLog entry to the active session.
        Does not commit independently to support multi-operation atomic transactions.
        """
        session = db
        target_inv_id = investigation_id
        ev_type = event_type
        rev_status = review_status
        notes = reviewer_notes
        metadata = event_metadata

        if len(args) == 1:
            if isinstance(args[0], Session):
                session = args[0]
            else:
                target_inv_id = args[0]
        elif len(args) == 2:
            if isinstance(args[0], Session):
                session = args[0]
                target_inv_id = args[1]
            else:
                target_inv_id = args[0]
                ev_type = args[1]
        elif len(args) >= 3:
            if isinstance(args[0], Session):
                session = args[0]
                target_inv_id = args[1]
                ev_type = args[2]
                if len(args) >= 4:
                    rev_status = args[3]
                if len(args) >= 5:
                    notes = args[4]
            else:
                target_inv_id = args[0]
                ev_type = args[1]
                rev_status = args[2]
                if len(args) >= 4:
                    notes = args[3]

        resolved_session = self._resolve_session(session)

        if not target_inv_id:
            raise InvestigationValidationError("investigation_id is required for audit log.")
        if not ev_type:
            raise InvestigationValidationError("event_type is required for audit log.")

        clean_notes = str(notes).strip() if notes and str(notes).strip() else None

        entry = InvestigationAuditLog(
            audit_id=f"audit_{uuid.uuid4().hex[:28]}",
            investigation_id=str(target_inv_id).strip(),
            event_type=str(ev_type).strip(),
            review_status=rev_status,
            reviewer_notes=clean_notes,
            created_at=_utc_now(),
            event_metadata_json=metadata or {}
        )
        resolved_session.add(entry)
        return entry

    def update_review(
        self,
        *args,
        db: Optional[Session] = None,
        investigation_id: Optional[str] = None,
        review_decision: Optional[Union[ReviewDecision, str]] = None,
        reviewer_notes: Optional[str] = None,
    ) -> Investigation:
        """
        Updates the human review status of an investigation, adds an audit entry,
        and atomically commits the transaction. Rejects invalid review decisions
        or nonexistent investigations.
        """
        session = db
        target_inv_id = investigation_id
        decision = review_decision
        notes = reviewer_notes

        if len(args) == 2:
            target_inv_id = args[0]
            decision = args[1]
        elif len(args) == 3:
            if isinstance(args[0], Session):
                session = args[0]
                target_inv_id = args[1]
                decision = args[2]
            else:
                target_inv_id = args[0]
                decision = args[1]
                notes = args[2]
        elif len(args) >= 4:
            session = args[0]
            target_inv_id = args[1]
            decision = args[2]
            notes = args[3]

        resolved_session = self._resolve_session(session)

        # Validate review decision enum
        if isinstance(decision, ReviewDecision):
            validated_decision = decision
        elif isinstance(decision, str):
            try:
                validated_decision = ReviewDecision(decision.strip().upper())
            except (ValueError, KeyError, AttributeError):
                raise InvestigationValidationError(
                    f"Invalid review decision '{decision}'. Allowed: {[d.value for d in ReviewDecision]}"
                )
        else:
            raise InvestigationValidationError(
                f"Review decision must be a string or ReviewDecision enum, got {type(decision)}"
            )

        # Retrieve investigation
        inv = (
            resolved_session.query(Investigation)
            .filter(Investigation.investigation_id == str(target_inv_id).strip())
            .first()
        )
        if inv is None:
            raise InvestigationNotFoundError(f"Investigation '{target_inv_id}' not found.")

        # Sanitize and validate notes
        clean_notes = str(notes).strip() if notes and str(notes).strip() else None
        if clean_notes and len(clean_notes) > 2000:
            raise InvestigationValidationError("Reviewer notes exceed maximum length of 2000 characters.")

        # Update investigation state
        inv.review_status = validated_decision.value

        # Create audit entry (appended, never overwriting historical audit entries)
        self.create_audit_log(
            db=resolved_session,
            investigation_id=inv.investigation_id,
            event_type="HUMAN_REVIEW_UPDATED",
            review_status=validated_decision.value,
            reviewer_notes=clean_notes,
            event_metadata={"decision": validated_decision.value}
        )

        try:
            resolved_session.commit()
            resolved_session.refresh(inv)
            return inv
        except Exception:
            resolved_session.rollback()
            raise

    def to_summary(self, investigation: Investigation) -> InvestigationSummary:
        """
        Maps an Investigation model into an InvestigationSummary schema.
        Exposes only high-level summary fields; does not return raw evidence payload.
        Safely derives top_finding without inventing non-existent data.
        """
        if investigation is None:
            raise InvestigationValidationError("Investigation instance cannot be None.")

        top_finding: Optional[str] = None
        if investigation.analysis_json and isinstance(investigation.analysis_json, dict):
            rec = investigation.analysis_json.get("recommendation")
            if isinstance(rec, dict) and rec.get("action_title"):
                top_finding = rec["action_title"]
            elif investigation.analysis_json.get("summary"):
                top_finding = investigation.analysis_json["summary"]

        if not top_finding and investigation.claims_json and isinstance(investigation.claims_json, list):
            if len(investigation.claims_json) > 0 and isinstance(investigation.claims_json[0], dict):
                top_finding = investigation.claims_json[0].get("claim_text")

        if not top_finding and investigation.answer:
            answer_clean = investigation.answer.strip().split("\n")[0]
            top_finding = answer_clean[:120] + ("..." if len(answer_clean) > 120 else "")

        created_str = (
            investigation.created_at.isoformat()
            if hasattr(investigation.created_at, "isoformat")
            else str(investigation.created_at)
        )
        completed_str = (
            investigation.completed_at.isoformat()
            if investigation.completed_at and hasattr(investigation.completed_at, "isoformat")
            else None
        )

        return InvestigationSummary(
            investigation_id=investigation.investigation_id,
            question=investigation.question,
            created_at=created_str,
            completed_at=completed_str,
            status=investigation.status,
            robustness_status=investigation.robustness_status,
            review_status=investigation.review_status,
            top_finding=top_finding
        )

    def list_summaries(
        self,
        *args,
        db: Optional[Session] = None,
        limit: int = DEFAULT_LIMIT,
        offset: int = 0
    ) -> List[InvestigationSummary]:
        """
        Lists investigations mapped to lightweight InvestigationSummary representations.
        """
        investigations = self.list_investigations(*args, db=db, limit=limit, offset=offset)
        return [self.to_summary(inv) for inv in investigations]
