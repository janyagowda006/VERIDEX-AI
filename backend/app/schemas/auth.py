from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    ANALYST = "ANALYST"
    REVIEWER = "REVIEWER"
    AUDITOR = "AUDITOR"
    ADMIN = "ADMIN"


class UserCreate(BaseModel):
    email: str = Field(..., description="User email address.")
    password: str = Field(..., min_length=6, description="User password.")
    full_name: str = Field(..., description="User full name.")
    role: UserRole = Field(default=UserRole.ANALYST, description="User RBAC role.")


class UserRead(BaseModel):
    user_id: str = Field(..., description="Unique user identifier.")
    email: str = Field(..., description="User email address.")
    full_name: str = Field(..., description="User full name.")
    role: str = Field(..., description="User RBAC role.")
    is_active: bool = Field(default=True, description="Account active status.")
    created_at: datetime = Field(..., description="UTC creation timestamp.")

    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    email: str = Field(..., description="User email address.")
    password: str = Field(..., description="User password.")


class Token(BaseModel):
    access_token: str = Field(..., description="JWT access token string.")
    token_type: str = Field(default="bearer", description="Token type.")
    user: UserRead = Field(..., description="Authenticated user object.")


class TokenData(BaseModel):
    user_id: str
    email: str
    role: str
    exp: Optional[int] = None
