from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.models.business_data import Base


def utcnow():
    return datetime.now(timezone.utc)


def _utc_now():
    return datetime.now(timezone.utc)


class Investigation(Base):
    """
    SQLAlchemy persistence model for an investigation session.
    Stores scalar metadata alongside structured JSON columns for lossless AskResponse reconstruction.
    """
    __tablename__ = "investigations"

    investigation_id = Column(String(36), primary_key=True, index=True)
    question = Column(Text, nullable=False)
    status = Column(String(32), nullable=False, index=True, default="IN_PROGRESS")
    robustness_status = Column(String(32), nullable=True, index=True)
    review_status = Column(String(32), nullable=False, default="PENDING", index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, index=True, default=utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    execution_time_ms = Column(Float, nullable=True)
    turns_used = Column(Integer, nullable=True, default=0)
    tool_calls_count = Column(Integer, nullable=True, default=0)
    evidence_count = Column(Integer, nullable=True, default=0)
    claims_count = Column(Integer, nullable=True, default=0)
    result_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)

    owner_id = Column(String(36), ForeignKey("users.user_id"), nullable=True, index=True)
    answer = Column(Text, nullable=True)

    # Structured JSON columns for lossless AskResponse reconstruction
    claims_json = Column(JSON, nullable=True, default=list)
    evidence_json = Column(JSON, nullable=True, default=list)
    analysis_json = Column(JSON, nullable=True)
    tool_calls_json = Column(JSON, nullable=True, default=list)
    metadata_json = Column(JSON, nullable=True, default=dict)

    reviews = relationship("InvestigationReview", back_populates="investigation", cascade="all, delete-orphan", order_by="desc(InvestigationReview.reviewed_at)")
    turns = relationship("InvestigationTurn", back_populates="investigation", cascade="all, delete-orphan", order_by="InvestigationTurn.turn_number.asc()")
    owner = relationship("User", back_populates="investigations", foreign_keys=[owner_id])
    audit_logs = relationship(
        "InvestigationAuditLog",
        back_populates="investigation",
        cascade="all, delete-orphan",
        order_by="InvestigationAuditLog.created_at.desc()"
    )


class InvestigationReview(Base):
    """
    SQLAlchemy ORM model for persistent append-only Human-in-the-Loop investigation reviews.
    """
    __tablename__ = "investigation_reviews"

    review_id = Column(String(36), primary_key=True, index=True)
    investigation_id = Column(String(36), ForeignKey("investigations.investigation_id"), nullable=False, index=True)
    review_status = Column(String(32), nullable=False, index=True)
    reviewer_id = Column(String(64), nullable=False, index=True)
    review_notes = Column(Text, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=False, index=True, default=utcnow)

    investigation = relationship("Investigation", back_populates="reviews")
    reviewer = relationship("User", primaryjoin="foreign(InvestigationReview.reviewer_id)==User.user_id")


class InvestigationTurn(Base):
    """
    SQLAlchemy ORM model for persistent append-only multi-turn conversation turns.
    """
    __tablename__ = "investigation_turns"

    turn_id = Column(String(36), primary_key=True, index=True)
    investigation_id = Column(String(36), ForeignKey("investigations.investigation_id"), nullable=False, index=True)
    turn_number = Column(Integer, nullable=False, default=1, index=True)
    user_question = Column(Text, nullable=False)
    execution_time_ms = Column(Float, nullable=True)
    result_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, index=True, default=utcnow)

    investigation = relationship("Investigation", back_populates="turns")


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
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)
    event_metadata_json = Column(JSON, nullable=True, default=dict)

    investigation = relationship("Investigation", back_populates="audit_logs")
