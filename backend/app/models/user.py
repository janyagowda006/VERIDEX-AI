from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from app.models.business_data import Base


def utcnow():
    return datetime.now(timezone.utc)


def generate_uuid():
    return str(uuid.uuid4())


class User(Base):
    """
    SQLAlchemy ORM model for VERIDEX-AI authenticated users.
    Supports RBAC roles: ANALYST, REVIEWER, AUDITOR, ADMIN.
    """
    __tablename__ = "users"

    user_id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(128), nullable=False)
    role = Column(String(32), nullable=False, default="ANALYST", index=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    # Relationships
    investigations = relationship("Investigation", back_populates="owner", foreign_keys="Investigation.owner_id")
    reviews = relationship("InvestigationReview", primaryjoin="User.user_id==foreign(InvestigationReview.reviewer_id)", overlaps="reviewer")
