from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime


class AuditLogResponse(BaseModel):
    """
    Pydantic schema for audit log entry responses.
    Exposes immutable audit log metadata to AUDITOR and ADMIN users.
    Guarantees no passwords, JWT tokens, or credentials are returned.
    """
    id: str = Field(..., description="Audit log entry UUID.")
    timestamp: datetime = Field(..., description="UTC timestamp of the audit event.")
    user_id: Optional[str] = Field(None, description="User ID performing the action.")
    user_role: Optional[str] = Field(None, description="Role of the user performing the action.")
    action_type: str = Field(..., description="Security or governance action type.")
    resource_id: Optional[str] = Field(None, description="ID of affected resource.")
    status: str = Field(..., description="Status outcome (e.g. SUCCESS, FAILURE, BLOCKED).")
    ip_address: Optional[str] = Field(None, description="Request client IP address.")
    details: Optional[str] = Field(None, description="Non-sensitive event metadata.")

    model_config = ConfigDict(from_attributes=True)
