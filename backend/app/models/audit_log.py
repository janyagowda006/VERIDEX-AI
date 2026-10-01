from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, DateTime
from app.models.business_data import Base


def utcnow():
    return datetime.now(timezone.utc)


def generate_uuid():
    return str(uuid.uuid4())


class AuditLogEntry(Base):
    """
    SQLAlchemy ORM model for enterprise append-only security audit log entries.
    Records security-sensitive and governance events for auditability.
    """
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)
    user_id = Column(String(36), nullable=True, index=True)
    user_role = Column(String(32), nullable=True, index=True)
    action_type = Column(String(64), nullable=False, index=True)
    resource_id = Column(String(64), nullable=True, index=True)
    status = Column(String(32), nullable=False, default="SUCCESS", index=True)
    ip_address = Column(String(45), nullable=True)
    details = Column(String(512), nullable=True)
