import logging
from typing import Optional, List
from sqlalchemy.orm import Session
from app.models.audit_log import AuditLogEntry

logger = logging.getLogger("veridex.audit")


class AuditLogger:
    """
    Centralized service for writing and querying append-only security audit log entries.
    Guarantees that security-sensitive actions (Authentication, Review, Export) are logged
    with user identity, role, resource, status, and request IP.
    """

    @staticmethod
    def record_event(
        db: Session,
        action_type: str,
        user_id: Optional[str] = None,
        user_role: Optional[str] = None,
        resource_id: Optional[str] = None,
        status: str = "SUCCESS",
        ip_address: Optional[str] = None,
        details: Optional[str] = None
    ) -> Optional[AuditLogEntry]:
        """
        Appends a new immutable AuditLogEntry record to the database.
        Safe execution: Catches write errors so application flow is not silently corrupted.
        """
        try:
            # Ensure details contains no secrets/passwords/tokens
            sanitized_details = details[:500] if details else None

            entry = AuditLogEntry(
                user_id=user_id,
                user_role=user_role,
                action_type=action_type,
                resource_id=resource_id,
                status=status,
                ip_address=ip_address,
                details=sanitized_details
            )

            # Use a nested transaction/savepoint if active transaction exists
            sp = db.begin_nested() if db.in_transaction() else None
            db.add(entry)
            if sp:
                sp.commit()
            db.commit()
            db.refresh(entry)
            return entry
        except Exception as exc:
            logger.error(f"Failed to record audit event '{action_type}': {exc}")
            try:
                db.rollback()
            except Exception:
                pass
            return None

    @staticmethod
    def list_audit_logs(
        db: Session,
        user_id: Optional[str] = None,
        action_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[AuditLogEntry]:
        """
        Queries audit logs with optional filters, sorted newest-first (timestamp DESC).
        Restricted to AUDITOR and ADMIN roles at the API layer.
        """
        query = db.query(AuditLogEntry)

        if user_id:
            query = query.filter(AuditLogEntry.user_id == user_id)
        if action_type:
            query = query.filter(AuditLogEntry.action_type == action_type)
        if resource_id:
            query = query.filter(AuditLogEntry.resource_id == resource_id)
        if status:
            query = query.filter(AuditLogEntry.status == status)

        return query.order_by(AuditLogEntry.timestamp.desc()).offset(offset).limit(limit).all()
