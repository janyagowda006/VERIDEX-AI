from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.models.business_data import Base


def _utc_now():
    return datetime.now(timezone.utc)


class Investigation(Base):
    """
    SQLAlchemy persistence model for an investigation session.
    Stores indexable scalar metadata alongside structured JSON columns for complete
    lossless reconstruction of AskResponse (claims, evidence, analysis, tool_calls).
    """
    __tablename__ = "investigations"

    investigation_id = Column(String(36), primary_key=True, index=True)
    question = Column(Text, nullable=False)
    status = Column(String(32), nullable=False, default="COMPLETED", index=True)
    robustness_status = Column(String(32), nullable=True, index=True)
    review_status = Column(String(32), nullable=False, default="PENDING", index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now, index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    answer = Column(Text, nullable=True)

    # Structured JSON columns for lossless AskResponse reconstruction
    claims_json = Column(JSON, nullable=False, default=list)
    evidence_json = Column(JSON, nullable=False, default=list)
    analysis_json = Column(JSON, nullable=True)
    tool_calls_json = Column(JSON, nullable=False, default=list)
    metadata_json = Column(JSON, nullable=False, default=dict)

    # Relational audit trail
    audit_logs = relationship(
        "InvestigationAuditLog",
        back_populates="investigation",
        cascade="all, delete-orphan",
        order_by="InvestigationAuditLog.created_at.desc()"
    )


class InvestigationAuditLog(Base):
    """
    Audit log tracking lifecycle transitions, approval/rejection decisions, and human reviewer notes.
    """
    __tablename__ = "investigation_audit_logs"

    audit_id = Column(String(36), primary_key=True, index=True)
    investigation_id = Column(
        String(36),
        ForeignKey("investigations.investigation_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    event_type = Column(String(64), nullable=False, index=True)
    review_status = Column(String(32), nullable=True)
    reviewer_notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now, index=True)
    event_metadata_json = Column(JSON, nullable=True, default=dict)

    investigation = relationship("Investigation", back_populates="audit_logs")
