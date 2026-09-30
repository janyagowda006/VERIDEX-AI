from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.models.business_data import Base


def utcnow():
    return datetime.now(timezone.utc)


class Investigation(Base):
    """
    SQLAlchemy ORM model for persistent decision intelligence investigations.
    Tracks investigation lifecycle state, timestamps, summary counts, robustness evaluation,
    and full AskResponse JSON payload.
    """
    __tablename__ = "investigations"

    investigation_id = Column(String(36), primary_key=True, index=True)
    question = Column(Text, nullable=False)
    status = Column(String(32), nullable=False, index=True, default="IN_PROGRESS")  # IN_PROGRESS, COMPLETED, FAILED, REQUIRES_REVIEW
    created_at = Column(DateTime(timezone=True), nullable=False, index=True, default=utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    execution_time_ms = Column(Float, nullable=True)
    turns_used = Column(Integer, nullable=True, default=0)
    tool_calls_count = Column(Integer, nullable=True, default=0)
    evidence_count = Column(Integer, nullable=True, default=0)
    claims_count = Column(Integer, nullable=True, default=0)
    robustness_status = Column(String(32), nullable=True, index=True)  # STABLE, SENSITIVE, INSUFFICIENT_EVIDENCE
    result_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)

    owner_id = Column(String(36), ForeignKey("users.user_id"), nullable=True, index=True)

    reviews = relationship("InvestigationReview", back_populates="investigation", cascade="all, delete-orphan", order_by="desc(InvestigationReview.reviewed_at)")
    turns = relationship("InvestigationTurn", back_populates="investigation", cascade="all, delete-orphan", order_by="InvestigationTurn.turn_number.asc()")
    owner = relationship("User", back_populates="investigations", foreign_keys=[owner_id])


class InvestigationReview(Base):
    """
    SQLAlchemy ORM model for persistent append-only Human-in-the-Loop investigation reviews.
    Stores reviewer decision (APPROVED, REJECTED, FLAGGED), metadata, notes, and timestamp.
    """
    __tablename__ = "investigation_reviews"

    review_id = Column(String(36), primary_key=True, index=True)
    investigation_id = Column(String(36), ForeignKey("investigations.investigation_id"), nullable=False, index=True)
    review_status = Column(String(32), nullable=False, index=True)  # APPROVED, REJECTED, FLAGGED
    reviewer_id = Column(String(64), nullable=False, index=True)
    review_notes = Column(Text, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=False, index=True, default=utcnow)

    investigation = relationship("Investigation", back_populates="reviews")
    reviewer = relationship("User", primaryjoin="foreign(InvestigationReview.reviewer_id)==User.user_id")


class InvestigationTurn(Base):
    """
    SQLAlchemy ORM model for persistent append-only multi-turn conversation turns.
    Stores sequential turn number, user question, execution duration, timestamp, and AskResponse JSON payload.
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
